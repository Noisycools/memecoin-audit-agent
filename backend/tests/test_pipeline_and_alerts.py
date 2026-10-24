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


@pytest.mark.asyncio
async def test_worker_rescan_reuses_ai_analysis_when_metrics_shift_under_15_percent(tmp_path):
    from backend.adapters.base import ChainAdapter, EnrichedTokenData
    from backend.clients.rugcheck import RugCheckReport
    from backend.pipeline.worker import ScanPipelineWorker
    from backend.schemas.token_report import AIAnalysisResult, MarketMetrics, TokenIdentity

    class DummyAdapter(ChainAdapter):
        chain_id = "solana"
        def __init__(self):
            self.liq = 60000.0
        async def discover_tokens(self):
            return []
        async def enrich_token(self, token_address: str, force_refresh: bool = False):
            return EnrichedTokenData(
                token=TokenIdentity(chain="solana", address=token_address, symbol="STABLE", name="Stable Coin"),
                market=MarketMetrics(price_usd=0.01, liquidity_usd=self.liq, market_cap=300000.0, volume_24h=100000.0, pair_age_minutes=60),
                rugcheck=RugCheckReport(mint=token_address, lp_locked_pct=100.0),
                social_meta={"has_website": True, "has_twitter": True},
            )

    class CountingAIClient:
        def __init__(self):
            self.calls = 0
        async def analyze_token(self, report, recent_snapshots=None):
            self.calls += 1
            return AIAnalysisResult(status="completed", model="gemini-3.8-flash-high", health_status="HEALTHY", buyer_quality="ORGANIC", conviction_score=85, summary_id="Analisis AI pertama.")

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'rescan_ai.db'}"
    session_factory = await create_async_session_factory(db_url)
    repo = AuditRepository(session_factory)
    cfg = load_config()
    adapter = DummyAdapter()
    ai_client = CountingAIClient()
    worker = ScanPipelineWorker(config=cfg, repo=repo, adapter=adapter, ai_client=ai_client)  # type: ignore[arg-type]

    rep1 = await worker.audit_single_token("solana", "MintStable1", force_refresh=True, force_ai=False)
    assert rep1 is not None and ai_client.calls == 1

    # Second background rescan with <15% liquidity change (+5%) should reuse AI analysis
    adapter.liq = 63000.0
    rep2 = await worker.audit_single_token("solana", "MintStable1", force_refresh=True, force_ai=False)
    assert rep2 is not None and ai_client.calls == 1
    assert rep2.ai_analysis is not None and rep2.ai_analysis.status == "completed"

