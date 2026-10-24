"""Pydantic schemas for Meta WhatsApp Cloud API webhooks."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WhatsAppWebhookVerification(BaseModel):
    """Query parameters sent by Meta during Webhook verification handshake."""

    hub_mode: str = Field(alias="hub.mode")
    hub_verify_token: str = Field(alias="hub.verify_token")
    hub_challenge: str = Field(alias="hub.challenge")

    model_config = ConfigDict(populate_by_name=True)


class WhatsAppProfile(BaseModel):
    name: Optional[str] = None


class WhatsAppContact(BaseModel):
    profile: Optional[WhatsAppProfile] = None
    wa_id: str


class WhatsAppText(BaseModel):
    body: str


class WhatsAppInteractiveReply(BaseModel):
    id: str
    title: str
    description: Optional[str] = None


class WhatsAppInteractive(BaseModel):
    type: str  # "button_reply" or "list_reply"
    button_reply: Optional[WhatsAppInteractiveReply] = None
    list_reply: Optional[WhatsAppInteractiveReply] = None


class WhatsAppStatusError(BaseModel):
    code: int
    title: str
    message: Optional[str] = None
    error_data: Optional[Dict[str, Any]] = None


class WhatsAppStatus(BaseModel):
    id: str
    status: str  # "sent", "delivered", "read", "failed"
    timestamp: str
    recipient_id: str
    errors: Optional[List[WhatsAppStatusError]] = None


class WhatsAppMessage(BaseModel):
    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: str  # "text", "interactive", "button", "location", etc.
    text: Optional[WhatsAppText] = None
    interactive: Optional[WhatsAppInteractive] = None

    model_config = ConfigDict(populate_by_name=True)

    def get_text_content(self) -> str:
        """Extract user-visible text from either standard text or interactive clicks."""
        if self.type == "text" and self.text:
            return self.text.body.strip()
        if self.type == "interactive" and self.interactive:
            if self.interactive.button_reply:
                return self.interactive.button_reply.title.strip()
            if self.interactive.list_reply:
                return self.interactive.list_reply.title.strip()
        return ""


class WhatsAppMetadata(BaseModel):
    display_phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: Optional[WhatsAppMetadata] = None
    contacts: Optional[List[WhatsAppContact]] = None
    messages: Optional[List[WhatsAppMessage]] = None
    statuses: Optional[List[WhatsAppStatus]] = None


class WhatsAppChange(BaseModel):
    field: str
    value: WhatsAppValue


class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """Top-level inbound webhook payload from Meta WhatsApp Cloud API."""

    object: str
    entry: List[WhatsAppEntry]

    def extract_messages(self) -> List[tuple[WhatsAppContact, WhatsAppMessage]]:
        """Helper to extract all inbound messages paired with contact info."""
        results = []
        for entry in self.entry:
            for change in entry.changes:
                if change.field == "messages" and change.value.messages:
                    contacts_map = {
                        c.wa_id: c
                        for c in (change.value.contacts or [])
                    }
                    for msg in change.value.messages:
                        contact = contacts_map.get(
                            msg.from_,
                            WhatsAppContact(wa_id=msg.from_, profile=WhatsAppProfile(name="Customer")),
                        )
                        results.append((contact, msg))
        return results

    def extract_statuses(self) -> List[WhatsAppStatus]:
        """Helper to extract delivery/read status notifications."""
        statuses = []
        for entry in self.entry:
            for change in entry.changes:
                if change.field == "messages" and change.value.statuses:
                    statuses.extend(change.value.statuses)
        return statuses
