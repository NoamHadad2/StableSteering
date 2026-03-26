from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.logging import configure_logging, logger, set_request_id
from app.core.schema import ExperimentCreate, FeedbackRequest, SessionCreate
from app.core.tracing import TraceRecorder
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.frontend_trace import FrontendTraceEvent

configure_logging()
templates = Jinja2Templates(directory=str(Path("app/frontend/templates")))


def initialize_app_state(application: FastAPI) -> None:
    """Build the runtime services for the web app.

    The default app runtime is GPU-only. Tests can inject their own orchestrator
    and trace recorder before startup to bypass heavyweight initialization.
    """

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
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/frontend/static"), name="static")
app.mount("/artifacts", StaticFiles(directory=str(settings.artifacts_dir)), name="artifacts")


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
    return templates.TemplateResponse("index.html", {"request": request, "experiments": experiments})


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


@app.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> HTMLResponse:
    """Render the session setup page."""

    experiments = request.app.state.orchestrator.list_experiments()
    return templates.TemplateResponse("setup.html", {"request": request, "experiments": experiments})


@app.get("/sessions/{session_id}/view", response_class=HTMLResponse)
def session_page(request: Request, session_id: str) -> HTMLResponse:
    """Render the interactive session view."""

    session = request.app.state.orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    rounds = request.app.state.orchestrator.get_session_rounds(session_id)
    current_round = rounds[-1] if rounds else None
    return templates.TemplateResponse(
        "session.html",
        {"request": request, "session": session, "rounds": rounds, "current_round": current_round},
    )


@app.get("/sessions/{session_id}/replay-view", response_class=HTMLResponse)
def replay_page(request: Request, session_id: str) -> HTMLResponse:
    """Render the replay page for one session."""

    session = request.app.state.orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    rounds = request.app.state.orchestrator.get_session_rounds(session_id)
    return templates.TemplateResponse("replay.html", {"request": request, "session": session, "rounds": rounds})


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
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


@app.post("/sessions")
def create_session(request: SessionCreate):
    """Create one session via the JSON API."""

    try:
        return app.state.orchestrator.create_session(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Fetch one session via the JSON API."""

    session = app.state.orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/sessions/{session_id}/rounds/next")
def next_round(session_id: str):
    """Generate the next round for a session."""

    try:
        return app.state.orchestrator.generate_round(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/rounds/{round_id}/feedback")
def submit_feedback(round_id: str, request: FeedbackRequest):
    """Apply user feedback to a round and update session state."""

    try:
        return app.state.orchestrator.submit_feedback(round_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/sessions/{session_id}/replay")
def replay(session_id: str):
    """Return replay export data for one session."""

    try:
        return app.state.orchestrator.export_replay(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    return {"ok": True}
