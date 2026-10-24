"""Core application constants and enumerations."""

from enum import Enum


class ConversationStage(str, Enum):
    NEW = "NEW"
    GREETING = "GREETING"
    QUALIFICATION = "QUALIFICATION"
    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    BOOKING = "BOOKING"
    BOOKED = "BOOKED"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    CLOSED = "CLOSED"


class MessageDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class MessageStatus(str, Enum):
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    RECEIVED = "RECEIVED"


class UrgencyLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class DecisionMakerStatus(str, Enum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class QualificationStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"


class BookingStatus(str, Enum):
    PENDING_SELECTION = "PENDING_SELECTION"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"
    FAILED = "FAILED"


class CRMSyncStatus(str, Enum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    RECONCILED = "RECONCILED"


class LLMProviderType(str, Enum):
    MOCK = "mock"
    OLLAMA = "ollama"
    OPENAI = "openai"
    GEMINI = "gemini"


class CalendarProviderType(str, Enum):
    MOCK = "mock"
    GOOGLE = "google"
    CALCOM = "calcom"


class CRMProviderType(str, Enum):
    MOCK = "mock"
    AIRTABLE = "airtable"
    WEBHOOK = "webhook"


class NotificationProviderType(str, Enum):
    MOCK = "mock"
    SLACK = "slack"
    WEBHOOK = "webhook"
