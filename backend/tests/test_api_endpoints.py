import pytest
from httpx import AsyncClient, ASGITransport
from backend.api.main import create_app


@pytest.mark.asyncio
async def test_api_health_tokens_and_settings_endpoints(tmp_path):
    app = await create_app(db_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}", enable_scheduler=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        health = await ac.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["nine_router"]["model"] == "gemini-3.8-flash-high"

        tokens = await ac.get("/api/v1/tokens")
        assert tokens.status_code == 200
        assert "items" in tokens.json()
        assert "top_ai_picks" in tokens.json()

        settings_res = await ac.put("/api/v1/settings", json={"min_liquidity_usd": 7500.0})
        assert settings_res.status_code == 200
        assert settings_res.json()["thresholds"]["prefilter"]["min_liquidity_usd"] == 7500.0


def test_uvicorn_factory_loads_create_app_synchronously(tmp_path, monkeypatch):
    from fastapi import FastAPI
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'sync_factory.db'}")
    app = create_app(enable_scheduler=False)
    assert isinstance(app, FastAPI)

