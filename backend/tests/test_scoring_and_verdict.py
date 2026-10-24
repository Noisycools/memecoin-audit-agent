from backend.config import load_config
from backend.schemas.token_report import MarketMetrics, TokenIdentity
from backend.clients.rugcheck import RugCheckReport, RugCheckHolder
from backend.adapters.base import EnrichedTokenData
from backend.scout.gmgn_scout import run_gmgn_scout
from backend.scoring.verdict import evaluate_token_score


def test_contract_critical_flag_forces_avoid_override_even_when_score_is_low():
    cfg = load_config()
    rug = RugCheckReport(
        mint="MintOverride",
        mint_authority="StillActiveAuth",
        freeze_authority=None,
        rugged=False,
        top_holders=[RugCheckHolder(address="User1", pct=2.0)],
        lp_locked_pct=100.0,
    )
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintOverride", symbol="OVR", name="Override"),
        market=MarketMetrics(price_usd=0.05, liquidity_usd=80000.0, market_cap=400000.0, volume_24h=150000.0, pair_age_minutes=120),
        rugcheck=rug,
        social_meta={"has_website": True, "has_twitter": True},
    )
    scout = run_gmgn_scout(data, cfg)
    res = evaluate_token_score(data, scout, cfg)
    assert res.risk_score < 70
    assert res.verdict == "AVOID"
    assert res.is_shortlisted_for_ai is False


def test_promising_downgrades_to_watch_when_liquidity_under_25k_or_rugcheck_missing():
    cfg = load_config()
    rug = RugCheckReport(mint="MintLowLiq", mint_authority=None, freeze_authority=None, rugged=False, lp_locked_pct=100.0)
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintLowLiq", symbol="LOW", name="LowLiq"),
        market=MarketMetrics(price_usd=0.01, liquidity_usd=18000.0, market_cap=100000.0, volume_24h=30000.0, pair_age_minutes=90),
        rugcheck=rug,
        social_meta={"has_website": True, "has_twitter": True},
    )
    scout = run_gmgn_scout(data, cfg)
    res = evaluate_token_score(data, scout, cfg)
    assert res.risk_score <= 29
    assert res.verdict == "WATCH"
    assert res.is_shortlisted_for_ai is True


def test_missing_rugcheck_sets_low_confidence_and_never_promising():
    cfg = load_config()
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintNoRug", symbol="NORUG", name="NoRug"),
        market=MarketMetrics(price_usd=0.01, liquidity_usd=60000.0, market_cap=300000.0, volume_24h=90000.0, pair_age_minutes=60),
        rugcheck=None,
        social_meta={"has_website": True, "has_twitter": True},
    )
    scout = run_gmgn_scout(data, cfg)
    res = evaluate_token_score(data, scout, cfg)
    assert res.confidence == "low"
    assert res.verdict != "PROMISING"


def test_rubric_flags_low_liq_to_mcap_ratio_under_5_percent():
    cfg = load_config()
    rug = RugCheckReport(mint="MintRatio", mint_authority=None, freeze_authority=None, rugged=False, lp_locked_pct=100.0)
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintRatio", symbol="RAT", name="Ratio"),
        market=MarketMetrics(price_usd=0.01, liquidity_usd=40000.0, market_cap=1000000.0, volume_24h=80000.0, pair_age_minutes=60),
        rugcheck=rug,
        social_meta={"has_website": True, "has_twitter": True},
    )
    scout = run_gmgn_scout(data, cfg)
    res = evaluate_token_score(data, scout, cfg)
    codes = {f.code for f in res.all_flags}
    assert "LOW_LIQ_TO_MCAP_RATIO" in codes

