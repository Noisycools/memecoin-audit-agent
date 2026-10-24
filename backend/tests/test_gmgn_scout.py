from backend.config import load_config
from backend.schemas.token_report import MarketMetrics, TokenIdentity
from backend.clients.rugcheck import RugCheckReport, RugCheckHolder, RugCheckKnownAccount, RugCheckRisk
from backend.adapters.base import EnrichedTokenData
from backend.scout.gmgn_scout import run_gmgn_scout


def test_holders_excludes_lp_and_burn_accounts_from_concentration():
    cfg = load_config()
    rug = RugCheckReport(
        mint="MintSafe",
        mint_authority=None,
        freeze_authority=None,
        rugged=False,
        top_holders=[
            RugCheckHolder(address="RaydiumVault", pct=45.0, insider=False),
            RugCheckHolder(address="BurnAddr1111", pct=20.0, insider=False),
            RugCheckHolder(address="UserWallet1", pct=4.5, insider=False),
            RugCheckHolder(address="UserWallet2", pct=3.5, insider=False),
        ],
        known_accounts={
            "RaydiumVault": RugCheckKnownAccount(name="Raydium Vault", type="AMM"),
            "BurnAddr1111": RugCheckKnownAccount(name="Burn", type="BURN"),
        },
        lp_locked_pct=99.0,
    )
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintSafe", symbol="SAFE", name="Safe"),
        market=MarketMetrics(price_usd=0.01, liquidity_usd=50000.0, volume_24h=100000.0, pair_age_minutes=60, pair_address="RaydiumVault"),
        rugcheck=rug,
        social_meta={"has_website": True, "has_twitter": True},
        repeated_wallet_wash=None,
    )
    res = run_gmgn_scout(data, cfg)
    codes = {f.code for f in res.flags}
    assert "TOP10_CONCENTRATION" not in codes
    assert "SINGLE_HOLDER_CONCENTRATION" not in codes
    assert res.metrics["top10_pct_ex_lp"] == 8.0


def test_wash_trade_zero_liquidity_or_zero_txns_returns_unknown_without_zero_division():
    cfg = load_config()
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintZero", symbol="ZERO", name="Zero"),
        market=MarketMetrics(price_usd=0.001, liquidity_usd=0.0, volume_24h=5000.0, txns_h1_buys=0, txns_h1_sells=0, pair_age_minutes=10),
        rugcheck=None,
        social_meta={},
        repeated_wallet_wash=None,
    )
    res = run_gmgn_scout(data, cfg)
    assert res.unknown_signals > 0
    assert res.evaluated_signals >= res.unknown_signals


def test_contract_flags_active_mint_and_freeze_as_critical():
    cfg = load_config()
    rug = RugCheckReport(
        mint="MintTrap",
        mint_authority="MintAuthPubkey",
        freeze_authority="FreezeAuthPubkey",
        rugged=True,
        risks=[RugCheckRisk(name="Rugged", level="danger", score=1000)],
    )
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintTrap", symbol="TRAP", name="Trap"),
        market=MarketMetrics(price_usd=0.001, liquidity_usd=30000.0, volume_24h=10000.0, pair_age_minutes=30),
        rugcheck=rug,
    )
    res = run_gmgn_scout(data, cfg)
    crit_codes = {f.code for f in res.flags if f.category == "contract" and f.severity == "critical"}
    assert "MINT_AUTHORITY_ACTIVE" in crit_codes
    assert "FREEZE_AUTHORITY_ACTIVE" in crit_codes
    assert "RUGCHECK_DANGER_OR_RUGGED" in crit_codes
