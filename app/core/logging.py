"""Structured JSON logging with request correlation ID tracking and secret redaction."""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

SENSITIVE_KEYS = {
    "authorization",
    "x-hub-signature-256",
    "whatsapp_access_token",
    "whatsapp_app_secret",
    "openai_api_key",
    "gemini_api_key",
    "calcom_api_key",
    "airtable_api_key",
    "google_calendar_credentials_json",
    "password",
    "secret",
    "token",
}


def get_correlation_id() -> str:
    cid = correlation_id_ctx.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id_ctx.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    correlation_id_ctx.set(cid)


class SensitiveDataScrubber:
    """Recursively redacts sensitive keys from log dictionaries."""

    @classmethod
    def scrub(cls, data: Any) -> Any:
        if isinstance(data, dict):
            scrubbed: Dict[str, Any] = {}
            for k, v in data.items():
                if str(k).lower() in SENSITIVE_KEYS:
                    scrubbed[k] = "[REDACTED]"
                else:
                    scrubbed[k] = cls.scrub(v)
            return scrubbed
        if isinstance(data, list):
            return [cls.scrub(item) for item in data]
        return data


class JSONFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON with correlation IDs."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        log_payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_ctx.get() or None,
            "module": record.module,
            "line": record.lineno,
        }

        # Include custom extra attributes if present
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload["data"] = SensitiveDataScrubber.scrub(record.extra_data)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload, default=str)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configures the root logger to use JSON formatting."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to prevent duplicate lines
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Quiet external noisy loggers
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return root_logger


logger = logging.getLogger("datheon_platform")
