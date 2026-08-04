import pytest
import httpx


@pytest.mark.asyncio
async def test_coingecko_api_reachability_and_format():

    coingecko_url = "https://api.coingecko.com/api/v3/simple/price"

    params = {
        "ids": "bitcoin,ethereum",
        "vs_currencies": "eur",
        "include_24hr_change": "true"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(coingecko_url, params=params, timeout=10.0)

    assert response.status_code == 200

    data = response.json()

    assert "bitcoin" in data
    assert "ethereum" in data

    # Prüfen, ob die korrekten Keys geliefert werden
    assert "eur" in data["bitcoin"]
    assert "eur_24h_change" in data["bitcoin"]

    # Plausibilitäts-Check
    assert isinstance(data["bitcoin"]["eur"], (int, float))
    assert data["bitcoin"]["eur"] > 0