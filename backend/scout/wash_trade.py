from __future__ import annotations

from typing import Any
from backend.adapters.base import EnrichedTokenData
from backend.config import AppConfig
from backend.schemas.token_report import ScoutFlag


def evaluate_wash_trade(
    data: EnrichedTokenData,
    config: AppConfig,
) -> tuple[list[ScoutFlag], int, int, dict[str, Any]]:
    flags: list[ScoutFlag] = []
    evaluated = 0
    unknown = 0
    metrics: dict[str, Any] = {}
    wt = config.thresholds.wash_trade
    m = data.market

    # 1. Volume to Liquidity Ratio (h24 / liquidity_usd)
    evaluated += 1
    if m.volume_24h is None or m.liquidity_usd is None or m.liquidity_usd <= 0:
        unknown += 1
        metrics["vol_liq_ratio"] = None
    else:
        ratio = round(m.volume_24h / m.liquidity_usd, 2)
        metrics["vol_liq_ratio"] = ratio
        if ratio > wt.vol_liq_critical:
            flags.append(
                ScoutFlag(
                    category="volume_integrity",
                    severity="critical",
                    code="VOL_LIQ_RATIO_HIGH",
                    value=ratio,
                    threshold=wt.vol_liq_critical,
                    source="dexscreener",
                    detail_id=f"Rasio volume 24j terhadap likuiditas ekstrem ({ratio}x > {wt.vol_liq_critical}x).",
                )
            )
        elif ratio > wt.vol_liq_warn:
            flags.append(
                ScoutFlag(
                    category="volume_integrity",
                    severity="warn",
                    code="VOL_LIQ_RATIO_HIGH",
                    value=ratio,
                    threshold=wt.vol_liq_warn,
                    source="dexscreener",
                    detail_id=f"Rasio volume 24j terhadap likuiditas tinggi ({ratio}x > {wt.vol_liq_warn}x).",
                )
            )

    # 2. Uniform buy/sell ratio across windows
    evaluated += 1
    if m.txns_h1_buys is None or m.txns_h1_sells is None or (m.txns_h1_buys + m.txns_h1_sells) <= 0:
        unknown += 1
        metrics["buy_ratio_h1"] = None
    else:
        total_h1 = m.txns_h1_buys + m.txns_h1_sells
        buy_ratio_h1 = round(m.txns_h1_buys / total_h1, 3)
        metrics["buy_ratio_h1"] = buy_ratio_h1
        if total_h1 >= wt.uniform_txns_min_h1 and (
            wt.uniform_buy_ratio_low <= buy_ratio_h1 <= wt.uniform_buy_ratio_high
        ):
            flags.append(
                ScoutFlag(
                    category="volume_integrity",
                    severity="warn",
                    code="UNIFORM_BUY_SELL_RATIO",
                    value=buy_ratio_h1,
                    threshold=0.50,
                    source="dexscreener",
                    detail_id=f"Transaksi h1 tinggi ({total_h1} tx) tetapi rasio buy:sell sangat seragam ({buy_ratio_h1:.1%}).",
                )
            )

    # 3. High txns with flat price movement
    evaluated += 1
    if (
        m.txns_h1_buys is not None
        and m.txns_h1_sells is not None
        and m.price_change_h1 is not None
    ):
        total_h1 = m.txns_h1_buys + m.txns_h1_sells
        if total_h1 >= wt.flat_price_min_txns_h1 and abs(m.price_change_h1) <= wt.flat_price_max_change_h1_pct:
            flags.append(
                ScoutFlag(
                    category="volume_integrity",
                    severity="warn",
                    code="HIGH_TXNS_FLAT_PRICE",
                    value=abs(m.price_change_h1),
                    threshold=wt.flat_price_max_change_h1_pct,
                    source="dexscreener",
                    detail_id=f"Banyak transaksi h1 ({total_h1} tx) namun harga nyaris stagnan ({m.price_change_h1}%).",
                )
            )
    elif (
        m.txns_m5_buys is not None
        and m.txns_m5_sells is not None
        and m.price_change_m5 is not None
    ):
        total_m5 = m.txns_m5_buys + m.txns_m5_sells
        if total_m5 >= wt.flat_price_min_txns_m5 and abs(m.price_change_m5) <= wt.flat_price_max_change_m5_pct:
            flags.append(
                ScoutFlag(
                    category="volume_integrity",
                    severity="warn",
                    code="HIGH_TXNS_FLAT_PRICE",
                    value=abs(m.price_change_m5),
                    threshold=wt.flat_price_max_change_m5_pct,
                    source="dexscreener",
                    detail_id=f"Transaksi m5 tinggi ({total_m5} tx) namun perubahan harga sangat kecil ({m.price_change_m5}%).",
                )
            )
    else:
        unknown += 1

    # 4. Sudden m5 volume spike without liquidity support
    evaluated += 1
    if m.volume_m5 is None or m.volume_h1 is None or m.volume_h1 <= 0:
        unknown += 1
    else:
        annualized_m5 = m.volume_m5 * 12.0
        spike_ratio = round(annualized_m5 / m.volume_h1, 2)
        metrics["m5_vol_spike_ratio"] = spike_ratio
        if spike_ratio > wt.vol_spike_multiplier and (m.liquidity_usd or 0.0) < 25000.0:
            flags.append(
                ScoutFlag(
                    category="volume_integrity",
                    severity="warn",
                    code="SUDDEN_VOL_SPIKE_NO_LIQ",
                    value=spike_ratio,
                    threshold=wt.vol_spike_multiplier,
                    source="dexscreener",
                    detail_id=f"Lonjakan volume 5 menit ({spike_ratio}x rata-rata jam) pada likuiditas tipis.",
                )
            )

    # 5. Repeated wallet wash trade via optional Solana RPC
    if data.repeated_wallet_wash is not None:
        evaluated += 1
        if data.repeated_wallet_wash:
            flags.append(
                ScoutFlag(
                    category="volume_integrity",
                    severity="critical",
                    code="REPEATED_WALLET_WASH",
                    value=True,
                    threshold=False,
                    source="solana_rpc",
                    detail_id="Terdeteksi transaksi berulang pada slot blok yang sangat berdekatan.",
                )
            )

    return flags, evaluated, unknown, metrics
