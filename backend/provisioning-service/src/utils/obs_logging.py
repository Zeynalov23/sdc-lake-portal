"""
JSON logging, with a request id carried through the call.

Plain text logs are only greppable on one pod. Once they are shipped to a
central store the format is what decides whether you can ask a question of
them: `space_id = "marketing-eu"` is a query, a regex over a message is a
guess.

The request id is held in a ContextVar rather than passed down through every
function. A ContextVar is per-task in asyncio, so two requests handled
concurrently see their own value - a module-level global would not.
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# Everything LogRecord sets on itself. Anything outside this set arrived
# through `extra={...}` at the call site and belongs in the output.
_RESERVED = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        rid = request_id.get()
        if rid:
            payload["request_id"] = rid

        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # default=str so an unexpected object in `extra` degrades to its
        # repr instead of throwing inside the logging call.
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Replace the root handlers. Call once, before anything logs."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn installs its own handlers and would otherwise emit a second,
    # unstructured copy of every access line.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
