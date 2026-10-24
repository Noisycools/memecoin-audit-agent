from __future__ import annotations

from typing import Any
from backend.adapters.base import EnrichedTokenData
from backend.config import AppConfig
from backend.schemas.token_report import ScoutFlag

EXCLUDED_ACCOUNT_TYPES = {"AMM", "LP", "LOCKER", "BURN", "VAULT", "BONDING_CURVE"}
BURN_ADDRESS_PREFIXES = ("11111111111111111111111111111111", "Burn", "dead")


def _is_lp_or_burn(
    address: str,
    owner: str | None,
    pair_address: str | None,
    known_accounts: dict[str, Any],
) -> bool:
    if pair_address and (address == pair_address or owner == pair_address):
        return True
    if any(address.startswith(p) for p in BURN_ADDRESS_PREFIXES):
        return True
    for candidate in (address, owner):
        if candidate and candidate in known_accounts:
            acct = known_accounts[candidate]
            acct_type = str(getattr(acct, "type", "") or "").upper()
            acct_name = str(getattr(acct, "name", "") or "").upper()
            if acct_type in EXCLUDED_ACCOUNT_TYPES or any(
                kw in acct_name for kw in ("RAYDIUM", "METEORA", "ORCA", "PUMP.FUN", "BONDING", "BURN", "LOCKER", "POOL", "VAULT")
            ):
                return True
    return False


def evaluate_holders(
    data: EnrichedTokenData,
    config: AppConfig,
) -> tuple[list[ScoutFlag], int, int, dict[str, Any]]:
    flags: list[ScoutFlag] = []
    ht = config.thresholds.holders
    rug = data.rugcheck

    if rug is None:
        return flags, 4, 4, {
            "top1_pct_ex_lp": None,
            "top10_pct_ex_lp": None,
            "top20_pct_ex_lp": None,
            "insider_cluster_pct": None,
            "creator_balance_pct": None,
        }

    evaluated = 4
    unknown = 0

    non_lp_holders = [
        h
        for h in rug.top_holders
        if not _is_lp_or_burn(h.address, h.owner, data.market.pair_address, rug.known_accounts)
    ]
    lp_holders = [
        h
        for h in rug.top_holders
        if _is_lp_or_burn(h.address, h.owner, data.market.pair_address, rug.known_accounts)
    ]
    lp_supply_pct = round(sum(h.pct for h in lp_holders), 2)

    top1_pct = round(non_lp_holders[0].pct, 2) if non_lp_holders else 0.0
    top10_pct = round(sum(h.pct for h in non_lp_holders[:10]), 2)
    top20_pct = round(sum(h.pct for h in non_lp_holders[:20]), 2)
    insider_pct = round(sum(h.pct for h in non_lp_holders if h.insider), 2)

    top1_ratio = round(top1_pct / 100.0, 4)
    top10_ratio = round(top10_pct / 100.0, 4)
    insider_ratio = round(insider_pct / 100.0, 4)

    # 1. Top 10 holder concentration
    if top10_ratio > ht.top10_critical:
        flags.append(
            ScoutFlag(
                category="holders",
                severity="critical",
                code="TOP10_CONCENTRATION",
                value=top10_ratio,
                threshold=ht.top10_critical,
                source="rugcheck",
                detail_id=f"Top 10 holder (di luar LP) menguasai {top10_pct:.1f}% suplai (> {ht.top10_critical * 100:.0f}%).",
            )
        )
    elif top10_ratio > ht.top10_warn:
        flags.append(
            ScoutFlag(
                category="holders",
                severity="warn",
                code="TOP10_CONCENTRATION",
                value=top10_ratio,
                threshold=ht.top10_warn,
                source="rugcheck",
                detail_id=f"Top 10 holder (di luar LP) memegang {top10_pct:.1f}% suplai (> {ht.top10_warn * 100:.0f}%).",
            )
        )

    # 2. Single top holder concentration
    if top1_ratio > ht.top1_critical:
        flags.append(
            ScoutFlag(
                category="holders",
                severity="critical",
                code="SINGLE_HOLDER_CONCENTRATION",
                value=top1_ratio,
                threshold=ht.top1_critical,
                source="rugcheck",
                detail_id=f"Satu wallet terbesar menguasai {top1_pct:.1f}% suplai (> {ht.top1_critical * 100:.0f}%).",
            )
        )
    elif top1_ratio > ht.top1_warn:
        flags.append(
            ScoutFlag(
                category="holders",
                severity="warn",
                code="SINGLE_HOLDER_CONCENTRATION",
                value=top1_ratio,
                threshold=ht.top1_warn,
                source="rugcheck",
                detail_id=f"Wallet terbesar memegang {top1_pct:.1f}% suplai (> {ht.top1_warn * 100:.0f}%).",
            )
        )

    # 3. Insider / bundle cluster detection
    if insider_ratio > ht.insider_cluster_critical or rug.graph_insiders_detected >= 5:
        flags.append(
            ScoutFlag(
                category="holders",
                severity="critical",
                code="INSIDER_BUNDLE_CLUSTER",
                value=insider_ratio if insider_ratio > 0 else rug.graph_insiders_detected,
                threshold=ht.insider_cluster_critical,
                source="rugcheck",
                detail_id=f"Klaster insider/bundle terdeteksi memegang {insider_pct:.1f}% suplai ({rug.graph_insiders_detected} koneksi insider).",
            )
        )
    elif insider_ratio > ht.insider_cluster_warn or rug.graph_insiders_detected > 0:
        flags.append(
            ScoutFlag(
                category="holders",
                severity="warn",
                code="INSIDER_BUNDLE_CLUSTER",
                value=insider_ratio if insider_ratio > 0 else rug.graph_insiders_detected,
                threshold=ht.insider_cluster_warn,
                source="rugcheck",
                detail_id=f"Indikasi wallet terhubung/insider ({insider_pct:.1f}% suplai, {rug.graph_insiders_detected} koneksi).",
            )
        )

    # 4. Creator holdings
    creator_pct = rug.creator_balance_pct
    if creator_pct is not None:
        creator_ratio = round(creator_pct / 100.0, 4)
        if creator_ratio > ht.creator_holdings_warn:
            flags.append(
                ScoutFlag(
                    category="holders",
                    severity="warn",
                    code="CREATOR_HOLDINGS_HIGH",
                    value=creator_ratio,
                    threshold=ht.creator_holdings_warn,
                    source="rugcheck",
                    detail_id=f"Creator masih memegang {creator_pct:.1f}% suplai.",
                )
            )

    metrics = {
        "top1_pct_ex_lp": top1_pct,
        "top10_pct_ex_lp": top10_pct,
        "top20_pct_ex_lp": top20_pct,
        "insider_cluster_pct": insider_pct,
        "graph_insiders_detected": rug.graph_insiders_detected,
        "creator_balance_pct": creator_pct,
        "lp_locked_pct": rug.lp_locked_pct,
        "lp_supply_pct": lp_supply_pct,
    }
    return flags, evaluated, unknown, metrics
