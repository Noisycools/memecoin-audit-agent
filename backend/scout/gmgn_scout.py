from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from backend.adapters.base import EnrichedTokenData
from backend.config import AppConfig
from backend.schemas.token_report import ScoutFlag
from backend.scout.contract import evaluate_contract
from backend.scout.holders import evaluate_holders
from backend.scout.wash_trade import evaluate_wash_trade


class ScoutResult(BaseModel):
    flags: list[ScoutFlag] = Field(default_factory=list)
    evaluated_signals: int = 0
    unknown_signals: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)


def run_gmgn_scout(data: EnrichedTokenData, config: AppConfig) -> ScoutResult:
    wt_flags, wt_eval, wt_unk, wt_metrics = evaluate_wash_trade(data, config)
    hd_flags, hd_eval, hd_unk, hd_metrics = evaluate_holders(data, config)
    ct_flags, ct_eval, ct_unk = evaluate_contract(data, config)

    all_flags = ct_flags + hd_flags + wt_flags
    merged_metrics = {**wt_metrics, **hd_metrics}

    return ScoutResult(
        flags=all_flags,
        evaluated_signals=wt_eval + hd_eval + ct_eval,
        unknown_signals=wt_unk + hd_unk + ct_unk,
        metrics=merged_metrics,
    )
