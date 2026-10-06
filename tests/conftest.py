"""Test fixtures.

Every test runs against a real database - an in-memory SQLite one - rather
than a mocked session. The caching logic is mostly SQL, and a mock would only
assert that the code calls the functions the test expects, not that the cache
works.
"""

from collections.abc import AsyncIterator, Sequence

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from cache_service.db import get_session
from cache_service.dependencies import get_transformer
from cache_service.main import app
from cache_service.models import Base


class CountingTransformer:
    """A transformer that records what it was asked to do.

    Uppercase, like the real one, but with no latency and with the calls and
    the values it received kept for assertions.
    """

    def __init__(self) -> None:
        self.calls = 0
        self.seen: list[list[str]] = []

    async def __call__(self, values: Sequence[str]) -> list[str]:
        if not values:
            return []
        self.calls += 1
        self.seen.append(list(values))
        return [value.upper() for value in values]


@pytest_asyncio.fixture
async def engine():
    # StaticPool over a shared in-memory database: every connection in the
    # test sees the same tables, which a plain in-memory SQLite would not give.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()


@pytest_asyncio.fixture
async def client(engine, transformer) -> AsyncIterator[AsyncClient]:
    """The app wired to the test database and the counting transformer."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_transformer] = lambda: transformer

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
