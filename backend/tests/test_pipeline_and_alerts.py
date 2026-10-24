import pytest
from backend.config import load_config
from backend.db.session import create_async_session_factory
from backend.db.repository import AuditRepository
from backend.pipeline.alerts import evaluate_alerts_for_transition
from backend.schemas.token_report import TokenAuditReport


@pytest.mark.asyncio
async def test_pipeline_rescan_detects_verdict_change_and_liquidity_drop_alert(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    session_factory = await create_async_session_factory(db_url)
    repo = AuditRepository(session_factory)
    cfg = load_config()

    await repo.add_to_watchlist(
        chain="solana",
        address="MintWatch1",
        symbol="W1",
        name="Watch 1",
        alert_liquidity_drop_pct=20.0,
    )

    snap1 = TokenAuditReport(
        token={"chain": "solana", "address": "MintWatch1", "symbol": "W1", "name": "Watch 1"},
        scanned_at="2026-10-24T20:00:00+07:00",
        market={"price_usd": 0.01, "liquidity_usd": 60000.0, "market_cap": 300000.0, "volume_24h": 120000.0, "pair_age_minutes": 50},
        risk_score=20,
        verdict="PROMISING",
        confidence="high",
        breakdown={"contract": 0, "holders": 10, "volume_integrity": 4, "liquidity": 4, "social": 2},
        flags=[],
        summary_id="Awal yang sehat.",
    )
    delta1 = await repo.save_audit_report(snap1)
    assert delta1.verdict_changed is False

    snap2 = snap1.model_copy(deep=True)
    snap2.scanned_at = "2026-10-24T20:03:00+07:00"
    snap2.market.liquidity_usd = 40000.0  # -33.3% drop (> 20% threshold)
    snap2.risk_score = 58
    snap2.verdict = "HIGH RISK"
    delta2 = await repo.save_audit_report(snap2)
    assert delta2.verdict_changed is True
    assert delta2.previous_verdict == "PROMISING"

    alerts = await evaluate_alerts_for_transition(repo, snap2, delta2, cfg)
    alert_types = {a.alert_type for a in alerts}
    assert "VERDICT_CHANGED" in alert_types
    assert "LIQUIDITY_DROP" in alert_types
