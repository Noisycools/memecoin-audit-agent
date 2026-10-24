from __future__ import annotations

from backend.config import AppConfig
from backend.schemas.token_report import MarketMetrics


def passes_cheap_prefilter(market: MarketMetrics | None, config: AppConfig) -> tuple[bool, str]:
    if market is None or not market.pair_address:
        return False, "NO_ACTIVE_PAIR"

    pf = config.thresholds.prefilter
    if market.liquidity_usd is None or market.liquidity_usd < pf.min_liquidity_usd:
        return False, "LIQUIDITY_BELOW_MIN"

    if market.pair_age_minutes is not None:
        if market.pair_age_minutes < pf.min_pair_age_minutes:
            return False, "PAIR_TOO_YOUNG"
        if market.pair_age_minutes > pf.max_pair_age_minutes:
            return False, "PAIR_TOO_OLD"

    return True, "OK"
