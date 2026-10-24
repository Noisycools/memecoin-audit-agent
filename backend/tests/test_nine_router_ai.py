import pytest
import httpx
from backend.config import load_config
from backend.schemas.token_report import TokenAuditReport, ScoutFlag
from backend.ai.nine_router import NineRouterClient


def _sample_promising_report() -> TokenAuditReport:
    return TokenAuditReport(
        token={"chain": "solana", "address": "MintPromising1", "symbol": "BONKAI", "name": "Bonk Agent"},
        scanned_at="2026-10-24T20:00:00+07:00",
        market={"price_usd": 0.0041, "liquidity_usd": 68000.0, "market_cap": 410000.0, "volume_24h": 520000.0, "pair_age_minutes": 42},
        risk_score=18,
        verdict="PROMISING",
        confidence="high",
        breakdown={"contract": 0, "holders": 8, "volume_integrity": 4, "liquidity": 4, "social": 2},
        flags=[ScoutFlag(category="holders", severity="warn", code="CREATOR_HOLDINGS", value=0.024, threshold=0.05, source="rugcheck")],
        summary_id="Placeholder",
    )


@pytest.mark.asyncio
async def test_nine_router_handles_markdown_fences_and_falls_back_on_timeout():
    cfg = load_config()
    fenced_json = """```json
    {
      "health_status": "HEALTHY",
      "buyer_quality": "ORGANIC",
      "conviction_score": 84,
      "momentum_phase": "EARLY_ACCUMULATION",
      "liquidity_stress": {
        "rating": "STRONG",
        "lp_to_top10_ratio": 0.79,
        "note_id": "Likuiditas $68K sanggup menyerap tekanan jual Top 10."
      },
      "narrative_quality": "SOLID",
      "summary_id": "Token memiliki struktur kontrak aman tanpa otoritas mint/freeze. Distribusi holder sehat dengan arus pembeli organik. Pantau pergerakan wallet creator yang masih memegang 2.4% suplai.",
      "decision_brief": {
        "bull_case_id": "Kontrak bersih dan rasio pembelian organik kuat di 62%.",
        "red_flag_id": "Umur pair baru 42 menit.",
        "invalidation_trigger_id": "Batalkan pantauan jika likuiditas turun di bawah $45.000."
      },
      "shortlist_rank_reason_id": "Kandidat paling sehat karena likuiditas tebal dan minim bot."
    }
    ```"""

    def ok_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:20128/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": fenced_json}}]})

    client = NineRouterClient(config=cfg, http_client=httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)))
    report = _sample_promising_report()
    ai_res = await client.analyze_token(report)
    assert ai_res.status == "completed"
    assert ai_res.model == "gemini-3.8-flash-high"
    assert ai_res.health_status == "HEALTHY"
    assert ai_res.buyer_quality == "ORGANIC"
    assert "45.000" in ai_res.decision_brief.invalidation_trigger_id

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("9router timed out")

    offline_client = NineRouterClient(config=cfg, http_client=httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)))
    fallback_res = await offline_client.analyze_token(report)
    assert fallback_res.status == "unavailable"
    assert fallback_res.health_status in ("HEALTHY", "MIXED", "UNHEALTHY")
    assert len(fallback_res.summary_id) > 20
