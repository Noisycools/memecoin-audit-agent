from pathlib import Path
from backend.config import load_config
from backend.schemas.token_report import TokenAuditReport, ScoutFlag


def test_load_config_reads_default_thresholds_and_weights():
    cfg = load_config()
    assert cfg.thresholds.prefilter.min_liquidity_usd == 5000.0
    assert cfg.thresholds.prefilter.min_pair_age_minutes == 5
    assert cfg.thresholds.prefilter.max_pair_age_minutes == 10080
    assert cfg.weights.contract == 30
    assert cfg.weights.holders == 25
    assert cfg.weights.volume_integrity == 20
    assert cfg.weights.liquidity == 15
    assert cfg.weights.social == 10
    assert cfg.ai.base_url == "http://localhost:20128/v1"
    assert cfg.ai.model == "gemini-3.8-flash-high"


def test_token_audit_report_preserves_unknown_as_none_and_serializes_spec_format():
    report = TokenAuditReport(
        token={"chain": "solana", "address": "So11111111111111111111111111111111111111112", "symbol": "BONKAI", "name": "Bonk Agent"},
        scanned_at="2026-10-24T20:00:00+07:00",
        market={"price_usd": 0.0041, "liquidity_usd": 68000.0, "market_cap": None, "volume_24h": 520000.0, "pair_age_minutes": 42},
        risk_score=18,
        verdict="PROMISING",
        confidence="high",
        breakdown={"contract": 0, "holders": 8, "volume_integrity": 4, "liquidity": 4, "social": 2},
        flags=[ScoutFlag(category="holders", severity="warn", code="TOP10_CONCENTRATION", value=0.32, threshold=0.30, source="rugcheck")],
        summary_id="Kontrak aman dan likuiditas kuat.",
    )
    payload = report.model_dump(mode="json")
    assert payload["market"]["market_cap"] is None
    assert payload["disclaimer"] == "Analisis otomatis, bukan nasihat keuangan."
