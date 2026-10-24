"""Human escalation administration and agent handoff resolution endpoints."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.constants import ConversationStage
from app.core.logging import logger
from app.db.repositories.conversation_repository import ConversationRepository
from app.db.session import get_db
from app.models.escalation import EscalationEvent

router = APIRouter(prefix="/api/v1/escalations", tags=["Escalation Administration"])


class EscalationResolveRequest(BaseModel):
    agent_name: str
    resolution_notes: str
    resume_automation: bool = False


@router.get("", status_code=status.HTTP_200_OK)
async def list_pending_escalations(db: AsyncSession = Depends(get_db)):
    """List all unresolved customer escalations requiring human attention."""
    stmt = (
        select(EscalationEvent)
        .where(EscalationEvent.is_resolved == False)  # noqa: E712
        .order_by(EscalationEvent.created_at.desc())
    )
    res = await db.execute(stmt)
    events = res.scalars().all()
    return [e.to_dict() for e in events]


@router.post("/{conversation_id}/resolve", status_code=status.HTTP_200_OK)
async def resolve_escalation(
    conversation_id: str,
    payload: EscalationResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Allows a human agent to mark an escalation resolved and optionally resume AI automation."""
    stmt = (
        select(EscalationEvent)
        .where(EscalationEvent.conversation_id == conversation_id)
        .order_by(EscalationEvent.created_at.desc())
    )
    res = await db.execute(stmt)
    event = res.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="No escalation found for this conversation.")

    event.is_resolved = True
    event.resolved_by = payload.agent_name
    event.resolved_at = datetime.now(timezone.utc)
    event.resolution_notes = payload.resolution_notes

    conv_repo = ConversationRepository(db)
    if payload.resume_automation:
        await conv_repo.set_autonomous_state(conversation_id, is_active=True)
        await conv_repo.update_stage(conversation_id, ConversationStage.QUALIFICATION)
        logger.info(f"Agent {payload.agent_name} resolved escalation and resumed automation for {conversation_id}.")
    else:
        await conv_repo.update_stage(conversation_id, ConversationStage.CLOSED)
        logger.info(f"Agent {payload.agent_name} resolved escalation and closed conversation {conversation_id}.")

    await db.flush()
    return {"status": "resolved", "conversation_id": conversation_id, "resumed": payload.resume_automation}
