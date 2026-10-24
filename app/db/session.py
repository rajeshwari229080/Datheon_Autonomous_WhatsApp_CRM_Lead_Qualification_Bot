"""Async database engine lifecycle and session management."""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base

# Engine configuration with connection pooling
engine_kwargs = {
    "echo": False,
    "future": True,
}

if "sqlite" in settings.DATABASE_URL:
    # SQLite-specific settings
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL settings
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_pre_ping"] = True

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an async database session."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables for development/testing environments."""
    logger.info("Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized successfully.")


async def close_db() -> None:
    """Close the database engine connections cleanly."""
    logger.info("Closing database engine pool...")
    await engine.dispose()
    logger.info("Database engine closed.")
