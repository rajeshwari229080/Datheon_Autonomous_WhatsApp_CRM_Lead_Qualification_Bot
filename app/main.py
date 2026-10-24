"""Main FastAPI Application Entrypoint."""

import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.escalation import router as escalation_router
from app.api.routes.health import router as health_router
from app.api.routes.whatsapp_webhook import router as whatsapp_router
from app.core.config import settings
from app.core.logging import get_correlation_id, logger, set_correlation_id, setup_logging
from app.db.session import close_db, init_db

# Setup structured logging
setup_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown hooks."""
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode...")
    # Initialize DB schema for dev / sqlite environments
    if "sqlite" in settings.DATABASE_URL:
        await init_db()
    yield
    logger.info("Shutting down application...")
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Enterprise-grade WhatsApp Lead Qualification, Booking & Escalation Engine",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Assigns or propagates a unique correlation ID for every inbound HTTP request."""
    cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    set_correlation_id(cid)
    response: Response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


# Register API Routers
app.include_router(health_router)
app.include_router(whatsapp_router)
app.include_router(escalation_router)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "online",
        "environment": settings.ENVIRONMENT,
    }
