"""API Routes package."""

from app.api.routes.whatsapp_webhook import router as whatsapp_router

__all__ = ["whatsapp_router"]
