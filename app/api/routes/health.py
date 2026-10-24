"""Health, readiness, and Prometheus-compatible metrics endpoints."""

import time
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_db

router = APIRouter(tags=["Monitoring & Health"])

# Operational Metrics In-Memory Counters
METRICS_DATA = {
    "webhooks_received_total": 0,
    "webhook_auth_failures_total": 0,
    "idempotent_duplicate_events_total": 0,
    "leads_qualified_total": 0,
    "leads_disqualified_total": 0,
    "bookings_confirmed_total": 0,
    "crm_sync_failures_total": 0,
    "human_escalations_total": 0,
}


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """Kubernetes / Docker Liveness probe verifying the service process is up."""
    return {"status": "alive", "timestamp": time.time(), "app": settings.APP_NAME}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """Readiness probe verifying database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "environment": settings.ENVIRONMENT,
            "llm_provider": settings.LLM_PROVIDER.value,
            "calendar_provider": settings.CALENDAR_PROVIDER.value,
            "crm_provider": settings.CRM_PROVIDER.value,
        }
    except Exception as exc:
        logger.error(f"Readiness check failed: Database unreachable: {exc}")
        return Response(
            content='{"status": "degraded", "error": "Database connectivity failed"}',
            media_type="application/json",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@router.get("/metrics", response_class=Response)
async def prometheus_metrics():
    """Prometheus exposition format for operational scraping."""
    lines = [
        "# HELP webhooks_received_total Total WhatsApp webhooks ingested",
        "# TYPE webhooks_received_total counter",
        f"webhooks_received_total {METRICS_DATA['webhooks_received_total']}",
        "# HELP webhook_auth_failures_total Webhook HMAC signature verification rejections",
        "# TYPE webhook_auth_failures_total counter",
        f"webhook_auth_failures_total {METRICS_DATA['webhook_auth_failures_total']}",
        "# HELP idempotent_duplicate_events_total Replay / duplicate message deduplication skips",
        "# TYPE idempotent_duplicate_events_total counter",
        f"idempotent_duplicate_events_total {METRICS_DATA['idempotent_duplicate_events_total']}",
        "# HELP leads_qualified_total Total leads successfully qualified for demo",
        "# TYPE leads_qualified_total counter",
        f"leads_qualified_total {METRICS_DATA['leads_qualified_total']}",
        "# HELP bookings_confirmed_total Confirmed calendar demo bookings",
        "# TYPE bookings_confirmed_total counter",
        f"bookings_confirmed_total {METRICS_DATA['bookings_confirmed_total']}",
        "# HELP human_escalations_total Conversations handed off to human agents",
        "# TYPE human_escalations_total counter",
        f"human_escalations_total {METRICS_DATA['human_escalations_total']}",
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
