"""Unit tests for Meta WhatsApp Webhook security and verification."""

import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import MessageStatus
from app.core.security import generate_hub_signature
from app.models.conversation import Conversation, Message


@pytest.mark.asyncio
async def test_webhook_challenge_success(client: AsyncClient):
    """GET verification challenge succeeds when verify token matches."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
        "hub.challenge": "1158201242",
    }
    response = await client.get("/api/v1/whatsapp/webhook", params=params)
    assert response.status_code == 200
    assert response.text == "1158201242"


@pytest.mark.asyncio
async def test_webhook_challenge_invalid_token(client: AsyncClient):
    """GET verification challenge fails with HTTP 403 when token is incorrect."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_unauthorized_token",
        "hub.challenge": "1158201242",
    }
    response = await client.get("/api/v1/whatsapp/webhook", params=params)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_challenge_invalid_mode(client: AsyncClient):
    """GET verification challenge fails with HTTP 403 when mode is not 'subscribe'."""
    params = {
        "hub.mode": "unsubscribe",
        "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
        "hub.challenge": "1158201242",
    }
    response = await client.get("/api/v1/whatsapp/webhook", params=params)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_post_without_signature_rejected(client: AsyncClient):
    """POST request without X-Hub-Signature-256 header is rejected with HTTP 401."""
    payload = {"object": "whatsapp_business_account", "entry": []}
    response = await client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 401
    assert "Invalid HMAC signature" in response.text


@pytest.mark.asyncio
async def test_webhook_post_with_forged_signature_rejected(client: AsyncClient):
    """POST request with forged signature is rejected with HTTP 401."""
    payload = {"object": "whatsapp_business_account", "entry": []}
    raw_body = json.dumps(payload).encode("utf-8")
    forged_sig = generate_hub_signature(raw_body, "wrong_secret")

    response = await client.post(
        "/api/v1/whatsapp/webhook",
        content=raw_body,
        headers={"X-Hub-Signature-256": forged_sig, "Content-Type": "application/json"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_post_with_valid_hmac_accepted(client: AsyncClient, db_session: AsyncSession):
    """POST request with valid HMAC signature succeeds and stores message."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "10065224525",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "10555"},
                            "contacts": [{"wa_id": "15551234567", "profile": {"name": "Alice Johnson"}}],
                            "messages": [
                                {
                                    "id": "wamid.HBgLMTU1NTEyMzQ1NjcVAgASGBQzQTkyREFDREY0Qz",
                                    "from": "15551234567",
                                    "timestamp": "1729000000",
                                    "type": "text",
                                    "text": {"body": "Hi, I need enterprise lead qualification for my sales team."},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    valid_sig = generate_hub_signature(raw_body, settings.WHATSAPP_APP_SECRET)

    response = await client.post(
        "/api/v1/whatsapp/webhook",
        content=raw_body,
        headers={"X-Hub-Signature-256": valid_sig, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["processed_messages"] == 1

    # Verify conversation created in DB
    result = await db_session.execute(select(Conversation).where(Conversation.wa_id == "15551234567"))
    conv = result.scalars().first()
    assert conv is not None
    assert conv.customer_name == "Alice Johnson"

    # Verify message persisted
    msg_res = await db_session.execute(
        select(Message).where(Message.provider_message_id == "wamid.HBgLMTU1NTEyMzQ1NjcVAgASGBQzQTkyREFDREY0Qz")
    )
    msg = msg_res.scalars().first()
    assert msg is not None
    assert msg.content == "Hi, I need enterprise lead qualification for my sales team."


@pytest.mark.asyncio
async def test_webhook_replay_duplicate_delivery_idempotent(client: AsyncClient, db_session: AsyncSession):
    """Replaying the exact same message delivery is idempotent and does not duplicate records."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "10065224525",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "contacts": [{"wa_id": "15559876543", "profile": {"name": "Bob Smith"}}],
                            "messages": [
                                {
                                    "id": "wamid.REPLAY_TEST_123456",
                                    "from": "15559876543",
                                    "timestamp": "1729000001",
                                    "type": "text",
                                    "text": {"body": "Hello Datheon team"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_hub_signature(raw_body, settings.WHATSAPP_APP_SECRET)
    headers = {"X-Hub-Signature-256": sig, "Content-Type": "application/json"}

    # First delivery
    res1 = await client.post("/api/v1/whatsapp/webhook", content=raw_body, headers=headers)
    assert res1.status_code == 200

    # Second delivery (replay attack or Meta duplicate network retry)
    res2 = await client.post("/api/v1/whatsapp/webhook", content=raw_body, headers=headers)
    assert res2.status_code == 200

    # Verify only 1 message row exists
    msg_res = await db_session.execute(
        select(Message).where(Message.provider_message_id == "wamid.REPLAY_TEST_123456")
    )
    all_msgs = msg_res.scalars().all()
    assert len(all_msgs) == 1


@pytest.mark.asyncio
async def test_webhook_delivery_status_notifications_handled(client: AsyncClient, db_session: AsyncSession):
    """Status updates (delivered, read) update existing message status without sending messages."""
    # First, insert an outbound message
    conv = Conversation(wa_id="15554443333", customer_name="Test Customer")
    db_session.add(conv)
    await db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        provider_message_id="wamid.STATUS_TEST_9999",
        direction="OUTBOUND",
        status=MessageStatus.SENT,
        content="Welcome to Datheon!",
        raw_payload={},
    )
    db_session.add(msg)
    await db_session.commit()

    # Ingest delivered status update from Meta
    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "10065224525",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": "wamid.STATUS_TEST_9999",
                                    "status": "delivered",
                                    "timestamp": "1729000005",
                                    "recipient_id": "15554443333",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(status_payload).encode("utf-8")
    sig = generate_hub_signature(raw_body, settings.WHATSAPP_APP_SECRET)

    response = await client.post(
        "/api/v1/whatsapp/webhook",
        content=raw_body,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["processed_statuses"] == 1

    # Verify status changed to DELIVERED
    await db_session.refresh(msg)
    assert msg.status == MessageStatus.DELIVERED
