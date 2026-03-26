from __future__ import annotations

import logging
from contextvars import ContextVar

from rich.logging import RichHandler


_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Attach the active request id to all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


def set_request_id(request_id: str) -> None:
    """Store the active request id in task-local context."""

    _request_id_var.set(request_id)


def get_request_id() -> str:
    """Return the current request id or a placeholder."""

    return _request_id_var.get()


def configure_logging(level: int = logging.INFO) -> None:
    """Configure a Rich-backed root logger once for the app process."""

    root = logging.getLogger()
    if any(getattr(handler, "_stable_steering_rich", False) for handler in root.handlers):
        return

    handler = RichHandler(rich_tracebacks=True, show_time=True, show_level=True, show_path=False)
    handler._stable_steering_rich = True  # type: ignore[attr-defined]
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(logging.Formatter("%(message)s [request_id=%(request_id)s]"))
    root.setLevel(level)
    root.addHandler(handler)


logger = logging.getLogger("stablesteering")
