from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.core.schema import Experiment, Round, Session


class JsonRepository:
    """Simple JSON-backed repository for local research workflows.

    This repository intentionally favors inspectability over performance.
    Each top-level entity type is written to its own directory so a developer
    can read and debug the stored session state without special tooling.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or settings.data_dir
        self.artifacts_dir = self.data_dir / settings.artifacts_dir_name
        self.traces_dir = self.data_dir / settings.traces_dir_name
        self.experiments_dir = self.data_dir / "experiments"
        self.sessions_dir = self.data_dir / "sessions"
        self.rounds_dir = self.data_dir / "rounds"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create the directory layout used by the repository."""

        for path in [
            self.data_dir,
            self.artifacts_dir,
            self.traces_dir,
            self.experiments_dir,
            self.sessions_dir,
            self.rounds_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, payload: dict) -> None:
        """Persist one JSON document using a stable UTF-8 encoding."""

        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def _read_json(self, path: Path) -> dict:
        """Load one JSON document from disk."""

        return json.loads(path.read_text(encoding="utf-8"))

    def save_experiment(self, experiment: Experiment) -> Experiment:
        """Persist an experiment snapshot."""

        self._write_json(self.experiments_dir / f"{experiment.id}.json", experiment.model_dump(mode="json"))
        return experiment

    def list_experiments(self) -> list[Experiment]:
        """Return all stored experiments in filename order."""

        items = []
        for path in sorted(self.experiments_dir.glob("*.json")):
            items.append(Experiment.model_validate(self._read_json(path)))
        return items

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        """Load one experiment if it exists."""

        path = self.experiments_dir / f"{experiment_id}.json"
        if not path.exists():
            return None
        return Experiment.model_validate(self._read_json(path))

    def save_session(self, session: Session) -> Session:
        """Persist session state after creation or update."""

        self._write_json(self.sessions_dir / f"{session.id}.json", session.model_dump(mode="json"))
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Load one session if it exists."""

        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None
        return Session.model_validate(self._read_json(path))

    def save_round(self, round_obj: Round) -> Round:
        """Persist one generated round."""

        self._write_json(self.rounds_dir / f"{round_obj.id}.json", round_obj.model_dump(mode="json"))
        return round_obj

    def get_round(self, round_id: str) -> Round | None:
        """Load one round if it exists."""

        path = self.rounds_dir / f"{round_id}.json"
        if not path.exists():
            return None
        return Round.model_validate(self._read_json(path))

    def list_rounds_for_session(self, session_id: str) -> list[Round]:
        """Return all rounds for a session in ascending round order."""

        rounds = []
        for path in sorted(self.rounds_dir.glob("*.json")):
            round_obj = Round.model_validate(self._read_json(path))
            if round_obj.session_id == session_id:
                rounds.append(round_obj)
        return sorted(rounds, key=lambda item: item.round_index)
