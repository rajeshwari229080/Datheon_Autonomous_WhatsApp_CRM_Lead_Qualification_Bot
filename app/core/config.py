"""Application configuration and settings schema using Pydantic Settings."""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.core.constants import (
    CalendarProviderType,
    CRMProviderType,
    LLMProviderType,
    NotificationProviderType,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application & Environment
    APP_NAME: str = "Datheon WhatsApp AI Qualification Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    LOG_LEVEL: str = "INFO"

    # Meta WhatsApp Cloud API Credentials
    WHATSAPP_VERIFY_TOKEN: str = "test_meta_webhook_verify_token"
    WHATSAPP_APP_SECRET: str = "test_meta_app_secret_12345"
    WHATSAPP_PHONE_NUMBER_ID: str = "test_phone_number_id"
    WHATSAPP_ACCESS_TOKEN: str = "test_meta_access_token"
    WHATSAPP_API_VERSION: str = "v20.0"

    # Database Persistence
    DATABASE_URL: str = "sqlite+aiosqlite:///./datheon_platform.db"

    # LLM Provider Configuration
    LLM_PROVIDER: LLMProviderType = LLMProviderType.MOCK
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Lead Qualification Thresholds
    QUALIFICATION_MIN_BUDGET: float = 1000.0
    QUALIFICATION_DEFAULT_CURRENCY: str = "USD"
    QUALIFICATION_MIN_COMPANY_SIZE: int = 5
    REQUIRE_DECISION_MAKER: bool = True

    # Calendar Integration Configuration
    CALENDAR_PROVIDER: CalendarProviderType = CalendarProviderType.MOCK
    BUSINESS_TIMEZONE: str = "UTC"
    BUSINESS_HOURS_START: str = "09:00"
    BUSINESS_HOURS_END: str = "18:00"
    MEETING_DURATION_MINUTES: int = 30
    MEETING_BUFFER_MINUTES: int = 15
    MINIMUM_NOTICE_HOURS: int = 2

    # Cal.com & Google Calendar Credentials
    CALCOM_API_KEY: Optional[str] = None
    CALCOM_EVENT_TYPE_ID: Optional[str] = None
    GOOGLE_CALENDAR_CREDENTIALS_JSON: Optional[str] = None
    GOOGLE_CALENDAR_ID: str = "primary"

    # CRM Integration Configuration
    CRM_PROVIDER: CRMProviderType = CRMProviderType.MOCK
    AIRTABLE_API_KEY: Optional[str] = None
    AIRTABLE_BASE_ID: Optional[str] = None
    AIRTABLE_TABLE_NAME: str = "Leads"
    CRM_WEBHOOK_URL: Optional[str] = None

    # Escalation & Notification Channels
    NOTIFICATION_PROVIDER: NotificationProviderType = NotificationProviderType.MOCK
    SLACK_WEBHOOK_URL: Optional[str] = None
    FALLBACK_HUMAN_PHONE: str = "+15550001234"

    @field_validator("DATABASE_URL")
    @classmethod
    def ensure_async_driver(cls, v: str) -> str:
        if v.startswith("sqlite://"):
            return v.replace("sqlite://", "sqlite+aiosqlite://")
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v


settings = Settings()
