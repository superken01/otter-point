import pytest
from httpx import ASGITransport, AsyncClient
from psycopg import AsyncConnection

from app.main import app, get_db_conn


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def conn():
    async_conn = await AsyncConnection.connect()
    await async_conn.execute("SELECT 1")

    async def mock_get_db_conn():
        async with async_conn.transaction():
            yield async_conn

    app.dependency_overrides[get_db_conn] = mock_get_db_conn
    yield async_conn
    del app.dependency_overrides[get_db_conn]

    await async_conn.rollback()  # ROLLBACK


@pytest.fixture
async def client(conn: AsyncConnection):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as async_client:
        yield async_client
