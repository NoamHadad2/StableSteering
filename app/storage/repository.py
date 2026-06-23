from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock

from app.core.config import settings
from app.core.schema import Experiment, Round, Session


class SQLiteRepository:
    """SQLite-backed repository for local research workflows.

    The repository preserves the existing application contract while replacing
    file-per-record JSON persistence with a small local SQLite database.
    Full entity payloads are still stored as JSON so schema evolution remains
    simple, while indexed columns keep common reads fast.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or settings.data_dir
        self.artifacts_dir = self.data_dir / settings.artifacts_dir_name
        self.traces_dir = self.data_dir / settings.traces_dir_name
        self.db_path = self.data_dir / "stablesteering.db"
        self._lock = Lock()
        self._ensure_dirs()
        self._initialize_database()

    def _ensure_dirs(self) -> None:
        """Create the directory layout used by the repository."""

        for path in [
            self.data_dir,
            self.artifacts_dir,
            self.traces_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with row access helpers enabled."""

        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialize_database(self) -> None:
        """Create the SQLite schema if it does not already exist."""

        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rounds (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    round_index INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_experiment_id
                    ON sessions (experiment_id);

                CREATE INDEX IF NOT EXISTS idx_rounds_session_id_round_index
                    ON rounds (session_id, round_index);
                """
            )

    @staticmethod
    def _dump_payload(model) -> str:
        """Serialize a Pydantic model to a stable JSON string."""

        return json.dumps(model.model_dump(mode="json"), sort_keys=True)

    @staticmethod
    def _load_payload(payload_json: str) -> dict:
        """Deserialize one JSON payload from SQLite storage."""

        return json.loads(payload_json)

    def save_experiment(self, experiment: Experiment) -> Experiment:
        """Persist an experiment snapshot."""

        payload_json = self._dump_payload(experiment)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO experiments (id, created_at, updated_at, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (
                    experiment.id,
                    experiment.created_at.isoformat(),
                    experiment.updated_at.isoformat(),
                    payload_json,
                ),
            )
        return experiment

    def list_experiments(self) -> list[Experiment]:
        """Return all stored experiments in ascending creation order."""

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM experiments ORDER BY created_at ASC, id ASC"
            ).fetchall()
        return [Experiment.model_validate(self._load_payload(row["payload_json"])) for row in rows]

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        """Load one experiment if it exists."""

        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM experiments WHERE id = ?",
                (experiment_id,),
            ).fetchone()
        if row is None:
            return None
        return Experiment.model_validate(self._load_payload(row["payload_json"]))

    def save_session(self, session: Session) -> Session:
        """Persist session state after creation or update."""

        payload_json = self._dump_payload(session)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, experiment_id, created_at, updated_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    experiment_id = excluded.experiment_id,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (
                    session.id,
                    session.experiment_id,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    payload_json,
                ),
            )
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Load one session if it exists."""

        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return Session.model_validate(self._load_payload(row["payload_json"]))

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its rounds from storage."""

        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM rounds WHERE session_id = ?", (session_id,))
            connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def list_sessions(self) -> list[Session]:
        """Return all stored sessions with newest activity first."""

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM sessions
                ORDER BY updated_at DESC, created_at DESC, id DESC
                """
            ).fetchall()
        return [Session.model_validate(self._load_payload(row["payload_json"])) for row in rows]

    def save_round(self, round_obj: Round) -> Round:
        """Persist one generated round."""

        payload_json = self._dump_payload(round_obj)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rounds (id, session_id, round_index, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    session_id = excluded.session_id,
                    round_index = excluded.round_index,
                    created_at = excluded.created_at,
                    payload_json = excluded.payload_json
                """,
                (
                    round_obj.id,
                    round_obj.session_id,
                    round_obj.round_index,
                    round_obj.created_at.isoformat(),
                    payload_json,
                ),
            )
        return round_obj

    def get_round(self, round_id: str) -> Round | None:
        """Load one round if it exists."""

        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM rounds WHERE id = ?",
                (round_id,),
            ).fetchone()
        if row is None:
            return None
        return Round.model_validate(self._load_payload(row["payload_json"]))

    def list_rounds_for_session(self, session_id: str) -> list[Round]:
        """Return all rounds for a session in ascending round order."""

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM rounds
                WHERE session_id = ?
                ORDER BY round_index ASC, created_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
        return [Round.model_validate(self._load_payload(row["payload_json"])) for row in rows]


# Backward-compatible alias while the rest of the app still imports JsonRepository.
JsonRepository = SQLiteRepository
