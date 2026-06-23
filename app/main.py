from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.config_yaml import parse_strategy_config_yaml, render_strategy_config_yaml
from app.core.jobs import AsyncJobManager
from app.core.logging import configure_logging, logger, set_request_id
from app.core.schema import ApiError, ExperimentCreate, FeedbackRequest, SessionCreate, SetupSessionRequest
from app.core.tracing import TraceRecorder
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.frontend_trace import FrontendTraceEvent
from app.updaters.critique_weighted_pref import CRITIQUE_TAGS
from app.feedback.taste_profile import compute_taste_profile

configure_logging()
templates = Jinja2Templates(directory=str(Path("app/frontend/templates")))

_STOP_WORDS = {"a","an","the","of","in","on","at","to","and","or","with","from","by","for","is","are","was","were"}
_STYLE_DIMENSIONS = ["lighting", "color", "mood", "style", "realism", "composition", "detail"]

def extract_prompt_dimensions(prompt: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]+", prompt.lower())
    content_dims = [w for w in words if w not in _STOP_WORDS and len(w) > 3][:4]
    return list(dict.fromkeys(content_dims + _STYLE_DIMENSIONS[:3]))


def humanize_token(value: object) -> str:
    """Turn enum values and slugs into readable UI labels."""

    if value is None:
        return ""
    raw = getattr(value, "value", str(value))
    return raw.replace("_", " ").replace("-", " ").strip().title()


def humanize_feedback_mode(value: object) -> str:
    mapping = {
        "scalar_rating": "Star ratings",
        "pairwise": "Pairwise winner vs loser",
        "top_k": "Top-k ranking",
        "winner_only": "Single winner",
        "approve_reject": "Approve / reject",
    }
    raw = getattr(value, "value", str(value))
    return mapping.get(raw, humanize_token(raw))


def humanize_session_status(value: object) -> str:
    mapping = {
        "created": "Created",
        "ready": "Ready for the next round",
        "awaiting_feedback": "Waiting for feedback",
        "updating": "Applying feedback",
        "completed": "Completed",
        "failed": "Needs attention",
        "paused": "Paused",
    }
    raw = getattr(value, "value", str(value))
    return mapping.get(raw, humanize_token(raw))


templates.env.globals["humanize_token"] = humanize_token
templates.env.globals["humanize_feedback_mode"] = humanize_feedback_mode
templates.env.globals["humanize_session_status"] = humanize_session_status


def initialize_app_state(application: FastAPI) -> None:
    """Build the runtime services for the web app.

    The default app runtime is GPU-only. Tests can inject their own orchestrator
    and trace recorder before startup to bypass heavyweight initialization.
    """

    if getattr(application.state, "job_manager", None) is None:
        application.state.job_manager = AsyncJobManager()

    if getattr(application.state, "orchestrator", None) is not None and getattr(application.state, "trace_recorder", None) is not None:
        return

    if settings.enforce_gpu_runtime and settings.generation_backend != "diffusers":
        raise RuntimeError(
            "StableSteering is configured to run only with GPU-backed Diffusers inference. "
            "Set STABLE_STEERING_GENERATION_BACKEND=diffusers or disable STABLE_STEERING_ENFORCE_GPU_RUNTIME "
            "only for test-only mock runs."
        )

    trace_recorder = TraceRecorder()
    application.state.trace_recorder = trace_recorder
    application.state.orchestrator = Orchestrator(
        generator=build_generation_engine(),
        trace_recorder=trace_recorder,
    )


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize services once the ASGI app starts."""

    initialize_app_state(application)
    try:
        yield
    finally:
        job_manager = getattr(application.state, "job_manager", None)
        if job_manager is not None:
            job_manager.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/frontend/static"), name="static")
app.mount("/artifacts", StaticFiles(directory=str(settings.artifacts_dir)), name="artifacts")


def api_error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Return a stable structured error payload for JSON API routes."""

    payload = ApiError(error_code=error_code, message=message).model_dump(mode="json")
    return JSONResponse(status_code=status_code, content=payload)


@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    """Attach request ids and emit request-level backend trace events."""

    request_id = request.headers.get("x-request-id", uuid4().hex[:12])
    request.state.request_id = request_id
    set_request_id(request_id)
    start = perf_counter()
    logger.info("HTTP %s %s started", request.method, request.url.path)
    app.state.trace_recorder.append_backend(
        "http.request.started",
        {"request_id": request_id, "method": request.method, "path": request.url.path},
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((perf_counter() - start) * 1000, 2)
        logger.exception("HTTP %s %s failed in %sms", request.method, request.url.path, duration_ms)
        app.state.trace_recorder.append_backend(
            "http.request.failed",
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration_ms,
                "error_type": exc.__class__.__name__,
            },
        )
        raise
    duration_ms = round((perf_counter() - start) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info("HTTP %s %s completed in %sms", request.method, request.url.path, duration_ms)
    app.state.trace_recorder.append_backend(
        "http.request.completed",
        {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Render the experiment dashboard."""

    experiments = request.app.state.orchestrator.list_experiments()
    sessions = request.app.state.orchestrator.list_sessions()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "experiments": experiments[:20],
            "experiment_count": len(experiments),
            "sessions": sessions[:10],
        },
    )


@app.get("/diagnostics")
def diagnostics():
    """Return runtime diagnostics for the active generation backend."""

    generator = app.state.orchestrator.generator
    payload = generator.diagnostics()
    payload.update(
        {
            "generation_backend_setting": settings.generation_backend,
            "inference_device_setting": settings.inference_device,
            "huggingface_model_id": settings.huggingface_model_id,
            "enforce_gpu_runtime": settings.enforce_gpu_runtime,
        }
    )
    return payload


@app.get("/diagnostics/view", response_class=HTMLResponse)
def diagnostics_page(request: Request) -> HTMLResponse:
    """Render a human-readable diagnostics page for runtime verification."""

    generator = request.app.state.orchestrator.generator
    payload = generator.diagnostics()
    payload.update(
        {
            "generation_backend_setting": settings.generation_backend,
            "inference_device_setting": settings.inference_device,
            "huggingface_model_id": settings.huggingface_model_id,
            "enforce_gpu_runtime": settings.enforce_gpu_runtime,
        }
    )
    return templates.TemplateResponse("diagnostics.html", {"request": request, "diagnostics": payload})


@app.get("/calibration", response_class=HTMLResponse)
def calibration_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("calibration.html", {"request": request})


@app.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> HTMLResponse:
    """Render the session setup page."""

    experiments = request.app.state.orchestrator.list_experiments()
    return templates.TemplateResponse(
        "setup.html",
        {
            "request": request,
            "experiments": experiments,
            "config_yaml": render_strategy_config_yaml(),
        },
    )


@app.get("/setup/config-template")
def setup_config_template():
    """Return the default editable YAML block for per-session configuration."""

    return {"config_yaml": render_strategy_config_yaml()}


@app.get("/sessions/{session_id}/view", response_class=HTMLResponse)
def session_page(request: Request, session_id: str) -> HTMLResponse:
    """Render the interactive session view."""

    session = request.app.state.orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    all_rounds = request.app.state.orchestrator.get_session_rounds(session_id)
    rounds = [r for r in all_rounds if r.round_index > 0]
    current_round = rounds[-1] if rounds else None
    runtime_diagnostics = request.app.state.orchestrator.generator.diagnostics()
    convergence = request.app.state.orchestrator.get_session_convergence(session_id)
    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "session": session,
            "rounds": rounds,
            "current_round": current_round,
            "runtime_diagnostics": runtime_diagnostics,
            "convergence": convergence,
            "critique_tags": CRITIQUE_TAGS,
            "prompt_dimensions": extract_prompt_dimensions(session.prompt),
            "taste_profile": compute_taste_profile(all_rounds),
        },
    )


@app.get("/sessions/{session_id}/replay-view", response_class=HTMLResponse)
def replay_page(request: Request, session_id: str) -> HTMLResponse:
    """Render the replay page for one session."""

    session = request.app.state.orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    rounds = request.app.state.orchestrator.get_session_rounds(session_id)
    return templates.TemplateResponse("replay.html", {"request": request, "session": session, "rounds": rounds})


@app.get("/sessions/{session_id}/trace-report", response_class=HTMLResponse)
def trace_report_page(request: Request, session_id: str) -> HTMLResponse:
    """Render the saved HTML trace report for one session."""

    try:
        report_path = request.app.state.orchestrator.generate_trace_report(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    return HTMLResponse(report_path.read_text(encoding="utf-8"))


@app.post("/experiments")
def create_experiment(request: ExperimentCreate):
    """Create one experiment via the JSON API."""

    return app.state.orchestrator.create_experiment(request)


@app.get("/experiments")
def list_experiments():
    """List all experiments via the JSON API."""

    return app.state.orchestrator.list_experiments()


@app.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str):
    """Fetch one experiment via the JSON API."""

    experiment = app.state.orchestrator.get_experiment(experiment_id)
    if experiment is None:
        return api_error_response(404, "not_found", "Experiment not found")
    return experiment


@app.post("/sessions")
def create_session(request: SessionCreate):
    """Create one session via the JSON API."""

    try:
        return app.state.orchestrator.create_session(request)
    except KeyError as exc:
        return api_error_response(404, "not_found", str(exc))
    except ValueError as exc:
        return api_error_response(400, "invalid_input", str(exc))


@app.post("/setup/session")
def create_session_from_setup(request: SetupSessionRequest):
    """Create one experiment and session from the setup page's YAML config."""

    try:
        config = parse_strategy_config_yaml(request.config_yaml)
        experiment = app.state.orchestrator.create_experiment(
            ExperimentCreate(
                name=request.experiment_name,
                description=request.description,
                config=config,
            )
        )
        session = app.state.orchestrator.create_session(
            SessionCreate(
                experiment_id=experiment.id,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
            )
        )
    except ValueError as exc:
        return api_error_response(400, "invalid_input", str(exc))
    except KeyError as exc:
        return api_error_response(404, "not_found", str(exc))
    except Exception:
        logger.exception("Unexpected failure while creating a session from setup YAML")
        return api_error_response(
            500,
            "internal_error",
            "The session could not be created from this YAML configuration due to an unexpected server error.",
        )
    return {
        "experiment": experiment.model_dump(mode="json"),
        "session": session.model_dump(mode="json"),
    }


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Fetch one session via the JSON API."""

    session = app.state.orchestrator.get_session(session_id)
    if session is None:
        return api_error_response(404, "not_found", "Session not found")
    return session


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    """Delete a session and all its rounds."""

    app.state.orchestrator.delete_session(session_id)


@app.get("/sessions/{session_id}/style-calibration", response_class=HTMLResponse)
def style_calibration_page(request: Request, session_id: str) -> HTMLResponse:
    """Render the style calibration page for a new session."""

    session = app.state.orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    rounds = app.state.orchestrator.get_session_rounds(session_id)
    cal_round = next((r for r in rounds if r.round_index == 0), None)
    return templates.TemplateResponse(
        "style_calibration.html",
        {
            "request": request,
            "session": session,
            "cal_round": cal_round,
        },
    )


@app.post("/sessions/{session_id}/style-calibration/generate/async", status_code=202)
async def style_calibration_generate_async(session_id: str):
    """Kick off async generation of the 15 calibration images."""

    try:
        job = await app.state.job_manager.submit(
            operation=f"calibration_round:{session_id}",
            fn=lambda progress: app.state.orchestrator.generate_calibration_round(session_id, progress),
        )
    except KeyError as exc:
        return api_error_response(404, "not_found", str(exc))
    return {"job_id": job.id, "status_url": f"/jobs/{job.id}", "state": job.state}


@app.post("/sessions/{session_id}/style-calibration/submit")
def style_calibration_submit(session_id: str, body: dict):
    """Accept the user's top picks and set the session's initial z vector."""

    selected_ids = body.get("selected_ids", [])
    try:
        app.state.orchestrator.submit_calibration(session_id, selected_ids)
    except (KeyError, ValueError) as exc:
        return api_error_response(400, "invalid_input", str(exc))
    return {"ok": True}


@app.get("/sessions/{session_id}/convergence", response_class=HTMLResponse)
def get_session_convergence(request: Request, session_id: str) -> HTMLResponse:
    """Render the convergence report page for one session."""

    session = request.app.state.orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    convergence = request.app.state.orchestrator.get_session_convergence(session_id)
    return templates.TemplateResponse(
        "convergence.html",
        {"request": request, "session": session, "convergence": convergence},
    )


@app.get("/sessions/{session_id}/convergence/json")
def get_session_convergence_json(session_id: str):
    """Return the raw convergence report as JSON."""

    try:
        return app.state.orchestrator.get_session_convergence(session_id)
    except KeyError:
        return api_error_response(404, "not_found", "Session not found")


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Return the current status for one asynchronous job."""

    job = await app.state.job_manager.get(job_id)
    if job is None:
        return api_error_response(404, "not_found", "Job not found")
    return job


@app.post("/sessions/{session_id}/rounds/next")
def next_round(session_id: str):
    """Generate the next round for a session."""

    try:
        return app.state.orchestrator.generate_round(session_id)
    except KeyError as exc:
        return api_error_response(404, "not_found", str(exc))
    except RuntimeError as exc:
        return api_error_response(409, "conflict", str(exc))


@app.post("/sessions/{session_id}/rounds/next/async", status_code=202)
async def next_round_async(session_id: str):
    """Start generating the next round asynchronously and return a job handle."""

    try:
        app.state.orchestrator._assert_round_generation_allowed(session_id)
        job = await app.state.job_manager.submit(
            operation=f"generate_round:{session_id}",
            fn=lambda progress: app.state.orchestrator.generate_round(session_id, progress),
        )
    except KeyError as exc:
        return api_error_response(404, "not_found", str(exc))
    except RuntimeError as exc:
        return api_error_response(409, "conflict", str(exc))
    return {"job_id": job.id, "status_url": f"/jobs/{job.id}", "state": job.state}


@app.post("/rounds/{round_id}/feedback")
def submit_feedback(round_id: str, request: FeedbackRequest):
    """Apply user feedback to a round and update session state."""

    try:
        return app.state.orchestrator.submit_feedback(round_id, request)
    except KeyError as exc:
        return api_error_response(404, "not_found", str(exc))
    except ValueError as exc:
        return api_error_response(400, "invalid_input", str(exc))
    except RuntimeError as exc:
        return api_error_response(409, "conflict", str(exc))


@app.post("/rounds/{round_id}/feedback/async", status_code=202)
async def submit_feedback_async(round_id: str, request: FeedbackRequest):
    """Start feedback application asynchronously and return a job handle."""

    try:
        app.state.orchestrator._assert_feedback_submission_allowed(round_id, request)
        job = await app.state.job_manager.submit(
            operation=f"submit_feedback:{round_id}",
            fn=lambda progress: app.state.orchestrator.submit_feedback(round_id, request, progress),
        )
    except KeyError as exc:
        return api_error_response(404, "not_found", str(exc))
    except ValueError as exc:
        return api_error_response(400, "invalid_input", str(exc))
    except RuntimeError as exc:
        return api_error_response(409, "conflict", str(exc))
    return {"job_id": job.id, "status_url": f"/jobs/{job.id}", "state": job.state}


@app.get("/sessions/{session_id}/replay")
def replay(session_id: str):
    """Return replay export data for one session."""

    try:
        return app.state.orchestrator.export_replay(session_id)
    except KeyError as exc:
        return api_error_response(404, "not_found", str(exc))


@app.post("/frontend-events")
def frontend_events(request: FrontendTraceEvent):
    """Accept browser-side trace events and persist them server-side."""

    logger.info("Frontend event %s on %s", request.event, request.page)
    app.state.trace_recorder.append_frontend(
        request.event,
        {
            "page": request.page,
            "session_id": request.session_id,
            "round_id": request.round_id,
            "details": request.details,
        },
    )
    report_url = None
    if request.session_id and app.state.orchestrator.get_session(request.session_id) is not None:
        app.state.orchestrator.generate_trace_report(request.session_id)
        report_url = f"/sessions/{request.session_id}/trace-report"
    return {"ok": True, "report_url": report_url}
