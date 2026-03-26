from __future__ import annotations

from app.core.schema import (
    Experiment,
    ExperimentCreate,
    FeedbackRequest,
    FeedbackResponse,
    RenderStatus,
    Round,
    RoundResponse,
    Session,
    SessionCreate,
    SessionStatus,
    utc_now,
)
from app.core.logging import logger
from app.core.tracing import TraceRecorder
from app.feedback.normalization import normalize_feedback
from app.samplers.exploit_orthogonal import ExploitOrthogonalSampler
from app.samplers.random_local import RandomLocalSampler
from app.samplers.uncertainty import UncertaintyGuidedSampler
from app.storage.repository import JsonRepository
from app.updaters.linear_pref import LinearPreferenceUpdater
from app.updaters.winner_average import WinnerAverageUpdater
from app.updaters.winner_copy import WinnerCopyUpdater
from app.engine.generation import GenerationEngine, build_generation_engine


class Orchestrator:
    """Application service that coordinates experiments, sessions, and rounds."""

    def __init__(
        self,
        repository: JsonRepository | None = None,
        generator: GenerationEngine | None = None,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        self.repository = repository or JsonRepository()
        self.generator = generator or build_generation_engine()
        self.trace_recorder = trace_recorder or TraceRecorder(self.repository.traces_dir)
        self.samplers = {
            "random_local": RandomLocalSampler(),
            "exploit_orthogonal": ExploitOrthogonalSampler(),
            "uncertainty_guided": UncertaintyGuidedSampler(),
        }
        self.updaters = {
            "winner_copy": WinnerCopyUpdater(),
            "winner_average": WinnerAverageUpdater(),
            "linear_preference": LinearPreferenceUpdater(),
        }

    def create_experiment(self, request: ExperimentCreate) -> Experiment:
        """Create and persist a reusable experiment definition."""

        experiment = Experiment(name=request.name, description=request.description, config=request.config)
        logger.info("Creating experiment %s", experiment.id)
        self.trace_recorder.append_backend(
            "experiment.created",
            {"experiment_id": experiment.id, "name": experiment.name, "sampler": experiment.config.sampler},
        )
        return self.repository.save_experiment(experiment)

    def list_experiments(self) -> list[Experiment]:
        """Return all stored experiments."""

        return self.repository.list_experiments()

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        """Load one experiment by identifier."""

        return self.repository.get_experiment(experiment_id)

    def create_session(self, request: SessionCreate) -> Session:
        """Create a session from an experiment or direct configuration."""

        config = request.config
        experiment_id = request.experiment_id
        if experiment_id:
            experiment = self.repository.get_experiment(experiment_id)
            if experiment is None:
                raise KeyError(f"Experiment not found: {experiment_id}")
            config = experiment.config
        if config is None:
            raise ValueError("Session creation requires experiment_id or config")

        session = Session(
            experiment_id=experiment_id or "ad_hoc",
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            model_name=config.model_name,
            config=config,
            status=SessionStatus.ready,
        )
        logger.info("Created session %s for experiment %s", session.id, session.experiment_id)
        self.trace_recorder.append_backend(
            "session.created",
            {"session_id": session.id, "experiment_id": session.experiment_id, "prompt": session.prompt},
        )
        return self.repository.save_session(session)

    def get_session(self, session_id: str) -> Session | None:
        """Load one session by identifier."""

        return self.repository.get_session(session_id)

    def get_session_rounds(self, session_id: str) -> list[Round]:
        """Return ordered rounds for a given session."""

        return self.repository.list_rounds_for_session(session_id)

    def generate_round(self, session_id: str) -> RoundResponse:
        """Propose, render, persist, and return the next round of candidates."""

        session = self._require_session(session_id)
        if session.status == SessionStatus.awaiting_feedback:
            raise RuntimeError("Cannot generate a new round while feedback for the current round is still pending")
        seed = 1000 + session.current_round
        sampler = self.samplers[session.config.sampler]
        round_index = session.current_round + 1
        round_obj = Round(
            session_id=session.id,
            round_index=round_index,
            incumbent_z=session.current_z,
            trust_radius=session.config.trust_radius,
            seed_policy=session.config.seed_policy,
        )
        logger.info("Generating round %s for session %s", round_index, session.id)
        self.trace_recorder.append_backend(
            "round.generation.started",
            {"session_id": session.id, "round_index": round_index, "sampler": session.config.sampler},
        )
        candidates = sampler.propose(session, seed)
        # Render each candidate independently so future versions can tolerate
        # partial round failures without changing the orchestration contract.
        for candidate in candidates:
            candidate.round_id = round_obj.id
            candidate.seed = seed
            candidate = self.generator.render_candidate(session, candidate)
            candidate.render_status = RenderStatus.succeeded
        round_obj.candidates = candidates
        round_obj.render_status = RenderStatus.succeeded
        round_obj.latency_ms = 15 * len(candidates)
        session.current_round = round_index
        session.status = SessionStatus.awaiting_feedback
        session.updated_at = utc_now()
        self.repository.save_round(round_obj)
        self.repository.save_session(session)
        self.trace_recorder.append_backend(
            "round.generation.completed",
            {
                "session_id": session.id,
                "round_id": round_obj.id,
                "round_index": round_index,
                "candidate_count": len(round_obj.candidates),
            },
        )
        return RoundResponse(
            round_id=round_obj.id,
            candidate_metadata=round_obj.candidates,
            image_urls=[candidate.image_path or "" for candidate in round_obj.candidates],
            state_summary={
                "session_id": session.id,
                "round_index": round_index,
                "current_z": session.current_z,
            },
        )

    def submit_feedback(self, round_id: str, request: FeedbackRequest) -> FeedbackResponse:
        """Normalize feedback, update state, and persist the new incumbent."""

        round_obj = self.repository.get_round(round_id)
        if round_obj is None:
            raise KeyError(f"Round not found: {round_id}")
        session = self._require_session(round_obj.session_id)
        if session.status != SessionStatus.awaiting_feedback:
            raise RuntimeError("Session is not currently awaiting feedback for this round")
        if round_obj.feedback_events:
            raise RuntimeError("Feedback has already been submitted for this round")
        feedback = normalize_feedback(round_id, request)
        self._validate_feedback_against_round(round_obj, feedback)
        updater = self.updaters[session.config.updater]
        next_z, update_summary = updater.update(session, round_obj.candidates, feedback)
        round_obj.feedback_events.append(feedback)
        round_obj.update_summary = update_summary
        session.current_z = next_z
        session.incumbent_candidate_id = update_summary["winner_candidate_id"]
        session.status = SessionStatus.ready
        session.updated_at = utc_now()
        self.repository.save_round(round_obj)
        self.repository.save_session(session)
        logger.info("Applied feedback to round %s for session %s", round_obj.id, session.id)
        self.trace_recorder.append_backend(
            "round.feedback.applied",
            {
                "session_id": session.id,
                "round_id": round_obj.id,
                "feedback_type": request.feedback_type,
                "winner_candidate_id": update_summary["winner_candidate_id"],
            },
        )
        return FeedbackResponse(update_summary=update_summary, next_incumbent_state=next_z)

    def export_replay(self, session_id: str) -> dict:
        """Return a replay-ready export bundle for one session."""

        session = self._require_session(session_id)
        experiment = self.repository.get_experiment(session.experiment_id)
        rounds = self.repository.list_rounds_for_session(session.id)
        return {
            "experiment": experiment.model_dump(mode="json") if experiment else None,
            "session": session.model_dump(mode="json"),
            "rounds": [item.model_dump(mode="json") for item in rounds],
        }

    def _require_session(self, session_id: str) -> Session:
        """Load a session or raise a lookup error."""

        session = self.repository.get_session(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def _validate_feedback_against_round(self, round_obj: Round, feedback) -> None:
        """Ensure feedback references candidates that exist in the target round."""

        candidate_ids = {candidate.id for candidate in round_obj.candidates}
        winner_id = feedback.normalized_payload.get("winner_candidate_id")
        if winner_id not in candidate_ids:
            raise ValueError(f"Feedback references unknown winner candidate: {winner_id}")

        loser_id = feedback.normalized_payload.get("loser_candidate_id")
        if loser_id is not None and loser_id not in candidate_ids:
            raise ValueError(f"Feedback references unknown loser candidate: {loser_id}")

        ranking = feedback.normalized_payload.get("ranking", [])
        unknown_ranked = [candidate_id for candidate_id in ranking if candidate_id not in candidate_ids]
        if unknown_ranked:
            raise ValueError(f"Feedback ranking references unknown candidates: {', '.join(unknown_ranked)}")
