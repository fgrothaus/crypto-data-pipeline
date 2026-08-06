import pytest
import pytest_asyncio
import httpx

from main import app
from database.database import (
    init_db,
    save_price_update,
    get_coin_price_history,
    cleanup_old_prices,
    engine
)
from models import PriceUpdate, CoinMetrics


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield
    await engine.dispose()


class TestDatabaseIntegration:

    @pytest.mark.asyncio
    async def test_save_and_get_price_history(self):
        coin_id = "bitcoin"

        payload = PriceUpdate(
            coins={
                coin_id: CoinMetrics(
                    eur=65000.50,
                    eur_24h_change=2.5
                )
            }
        )

        await save_price_update(payload)

        history = await get_coin_price_history(coin_id)

        assert len(history) > 0
        latest_entry = history[-1]
        assert "price_eur" in latest_entry
        assert float(latest_entry["price_eur"]) == 65000.50

    @pytest.mark.asyncio
    async def test_cleanup_old_prices(self):
        coin_id = "bitcoin"

        for i in range(15):
            payload = PriceUpdate(
                coins={
                    coin_id: CoinMetrics(
                        eur=50000.0 + i,
                        eur_24h_change=1.0
                    )
                }
            )
            await save_price_update(payload)

        await cleanup_old_prices(max_records=10)

        history_after = await get_coin_price_history(coin_id)
        assert len(history_after) == 10


class TestApiEndpoints:

    @pytest_asyncio.fixture
    async def client(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_liveness_check(self, client):
        response = await client.get("/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_readiness_check_with_real_redis(self, client):
        response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "redis": "connected"}

    @pytest.mark.asyncio
    async def test_get_history_not_found(self, client):
        response = await client.get("/prices/history/unknown_coin")
        assert response.status_code == 404
        assert "No price history found" in response.json()["detail"]