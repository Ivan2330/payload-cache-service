"""Database engine, session factory and schema creation."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cache_service.config import settings
from cache_service.models import Base

engine: AsyncEngine = create_async_engine(settings.database_url, future=True)

# expire_on_commit=False: after commit the handler still reads attributes off
# the objects, and a refresh round trip there would be wasted.
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Create tables if missing. A shortcut; Alembic in production - see README."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, always closed."""
    async with SessionFactory() as session:
        yield session
