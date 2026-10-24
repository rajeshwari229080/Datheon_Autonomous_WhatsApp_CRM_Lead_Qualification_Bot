"""FastAPI routes for Meta WhatsApp Cloud API webhook verification and event ingestion."""

import json
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.core.security import verify_webhook_signature
from app.db.session import get_db
from app.schemas.whatsapp import WhatsAppWebhookPayload
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/api/v1/whatsapp", tags=["WhatsApp Webhook"])


@router.get("/webhook", response_class=Response)
async def verify_meta_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """GET /api/v1/whatsapp/webhook

    Meta WhatsApp Webhook Verification handshake endpoint.
    Meta validates subscription by challenging this endpoint with configured verify_token.
    """
    logger.info(
        f"Received Meta webhook challenge with mode={hub_mode}",
        extra={"hub_mode": hub_mode},
    )

    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Meta webhook verification challenge succeeded.")
        # Return the challenge value directly as plain text (HTTP 200)
        return Response(content=hub_challenge, media_type="text/plain", status_code=200)

    logger.warning(
        "Meta webhook verification challenge failed: invalid verify token or mode.",
        extra={"provided_mode": hub_mode},
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch or invalid mode",
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def ingest_meta_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    db: AsyncSession = Depends(get_db),
):
    """POST /api/v1/whatsapp/webhook

    Ingests incoming WhatsApp events (messages and status receipts) from Meta.
    Verifies authenticity using HMAC-SHA256 over raw request body with Meta App Secret.
    """
    raw_body = await request.body()

    # 1. Cryptographic HMAC-SHA256 Signature Verification
    if not verify_webhook_signature(
        raw_body=raw_body,
        signature_header=x_hub_signature_256,
        app_secret=settings.WHATSAPP_APP_SECRET,
    ):
        logger.warning("Rejecting unauthorized webhook: Invalid or missing HMAC signature.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature",
        )

    # 2. Parse JSON Payload
    try:
        raw_json = json.loads(raw_body.decode("utf-8"))
        payload = WhatsAppWebhookPayload.model_validate(raw_json)
    except Exception as exc:
        logger.error(
            f"Failed to parse WhatsApp webhook payload: {exc}",
            extra={"raw_body_snippet": raw_body[:200].decode("utf-8", errors="ignore")},
        )
        # Even on malformed payloads, return 200 to prevent Meta webhook retries after logging
        return {"status": "error", "message": "Malformed payload"}

    conv_service = ConversationService(db)

    # 3. Handle Status Updates (sent, delivered, read, failed)
    statuses = payload.extract_statuses()
    for st in statuses:
        await conv_service.handle_status_update(
            provider_message_id=st.id,
            status_name=st.status,
        )

    # 4. Handle Inbound Customer Messages
    messages = payload.extract_messages()
    for contact, msg in messages:
        await conv_service.process_inbound_message(
            contact=contact,
            message=msg,
            raw_payload=raw_json,
        )

    return {"status": "success", "processed_messages": len(messages), "processed_statuses": len(statuses)}
