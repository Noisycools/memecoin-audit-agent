from __future__ import annotations

from backend.adapters.base import EnrichedTokenData
from backend.config import AppConfig
from backend.schemas.token_report import ScoreBreakdown, ScoutFlag
from backend.scout.gmgn_scout import ScoutResult


def compute_score_breakdown(
    data: EnrichedTokenData,
    scout: ScoutResult,
    config: AppConfig,
) -> tuple[ScoreBreakdown, list[ScoutFlag]]:
    w = config.weights
    extra_flags: list[ScoutFlag] = []

    # 1. Contract safety (max w.contract = 30)
    contract_pts = 0
    for f in scout.flags:
        if f.category == "contract":
            if f.severity == "critical":
                contract_pts += 25
            elif f.severity == "warn":
                contract_pts += 10
    contract_pts = min(w.contract, contract_pts)

    # 2. Holder distribution (max w.holders = 25)
    holders_pts = 0
    for f in scout.flags:
        if f.category == "holders":
            if f.severity == "critical":
                holders_pts += 15
            elif f.severity == "warn":
                holders_pts += 8
    top10_pct = scout.metrics.get("top10_pct_ex_lp")
    if isinstance(top10_pct, (int, float)) and top10_pct >= 20.0 and holders_pts == 0:
        holders_pts += 4
    holders_pts = min(w.holders, holders_pts)

    # 3. Volume integrity (max w.volume_integrity = 20)
    vol_pts = 0
    for f in scout.flags:
        if f.category == "volume_integrity":
            if f.severity == "critical":
                vol_pts += 15
            elif f.severity == "warn":
                vol_pts += 7
    vol_pts = min(w.volume_integrity, vol_pts)

    # 4. Liquidity (max w.liquidity = 15)
    liq_pts = 0
    liq_usd = data.market.liquidity_usd
    mc_usd = data.market.market_cap or data.market.fdv
    if liq_usd is None:
        liq_pts += 10
    elif liq_usd < 10000.0:
        liq_pts += 12
        extra_flags.append(
            ScoutFlag(
                category="liquidity",
                severity="warn",
                code="LOW_LIQUIDITY_USD",
                value=liq_usd,
                threshold=10000.0,
                source="dexscreener",
                detail_id=f"Likuiditas pool sangat tipis (${liq_usd:,.0f}).",
            )
        )
    elif liq_usd < 25000.0:
        liq_pts += 6
        extra_flags.append(
            ScoutFlag(
                category="liquidity",
                severity="info",
                code="MODERATE_LIQUIDITY_USD",
                value=liq_usd,
                threshold=25000.0,
                source="dexscreener",
                detail_id=f"Likuiditas di bawah ambang aman $25.000 (${liq_usd:,.0f}).",
            )
        )
    elif liq_usd < 50000.0:
        liq_pts += 2

    if liq_usd and mc_usd and mc_usd > 0:
        liq_mc_ratio = round(liq_usd / mc_usd, 4)
        if liq_mc_ratio < 0.05:
            liq_pts += 5
            extra_flags.append(
                ScoutFlag(
                    category="liquidity",
                    severity="warn",
                    code="LOW_LIQ_TO_MCAP_RATIO",
                    value=liq_mc_ratio,
                    threshold=0.05,
                    source="dexscreener",
                    detail_id=f"Rasio likuiditas terhadap market cap tipis ({liq_mc_ratio:.1%}).",
                )
            )
    liq_pts = min(w.liquidity, liq_pts)

    # 5. Social & Metadata (max w.social = 10)
    soc_pts = 0
    has_website = bool(data.social_meta.get("has_website"))
    has_twitter = bool(data.social_meta.get("has_twitter"))
    has_telegram = bool(data.social_meta.get("has_telegram"))

    if not has_website:
        soc_pts += 4
        extra_flags.append(
            ScoutFlag(
                category="social",
                severity="info",
                code="MISSING_WEBSITE",
                value=False,
                threshold=True,
                source="dexscreener",
                detail_id="Tidak ada tautan website resmi di profil DexScreener.",
            )
        )
    if not has_twitter and not has_telegram:
        soc_pts += 6
        extra_flags.append(
            ScoutFlag(
                category="social",
                severity="warn",
                code="MISSING_SOCIAL_LINKS",
                value=False,
                threshold=True,
                source="dexscreener",
                detail_id="Tidak ada tautan akun sosial (X/Telegram) di profil DexScreener.",
            )
        )
    soc_pts = min(w.social, soc_pts)

    breakdown = ScoreBreakdown(
        contract=contract_pts,
        holders=holders_pts,
        volume_integrity=vol_pts,
        liquidity=liq_pts,
        social=soc_pts,
    )
    return breakdown, extra_flags
