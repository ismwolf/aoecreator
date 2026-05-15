"""Health endpoint smoke tests — proves the scaffold wires together."""

from httpx import AsyncClient


async def test_health_live_returns_alive(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "alive"
    assert "version" in payload
    assert "timestamp" in payload
    assert "uptime_seconds" in payload


async def test_health_ready_returns_ready(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"] == {}
