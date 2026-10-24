"""Cryptographic security utilities for Meta webhook signature verification."""

import hashlib
import hmac
from typing import Optional
from app.core.logging import logger


def generate_hub_signature(raw_body: bytes, app_secret: str) -> str:
    """Computes the expected X-Hub-Signature-256 header value for a given payload and secret."""
    digest = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    app_secret: str,
) -> bool:
    """Verifies that an incoming Meta webhook POST payload matches the X-Hub-Signature-256 header.

    Uses constant-time comparison to protect against timing attacks.
    """
    if not signature_header:
        logger.warning("Webhook verification rejected: Missing X-Hub-Signature-256 header.")
        return False

    if not signature_header.startswith("sha256="):
        logger.warning(
            "Webhook verification rejected: Malformed X-Hub-Signature-256 header prefix.",
            extra={"signature_header": signature_header},
        )
        return False

    if not app_secret:
        logger.error("Webhook verification failed: Server WHATSAPP_APP_SECRET is not configured.")
        return False

    provided_signature = signature_header[len("sha256=") :]
    expected_signature = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(expected_signature, provided_signature)
    if not is_valid:
        logger.warning(
            "Webhook verification rejected: HMAC signature mismatch.",
            extra={"provided_prefix": provided_signature[:8] + "..."},
        )
    return is_valid
