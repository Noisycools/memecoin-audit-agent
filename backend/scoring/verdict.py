from __future__ import annotations

from pydantic import BaseModel, Field

from backend.adapters.base import EnrichedTokenData
from backend.config import AppConfig
from backend.schemas.token_report import (
    ConfidenceType,
    ScoreBreakdown,
    ScoutFlag,
    VerdictType,
)
from backend.scoring.rubric import compute_score_breakdown
from backend.scout.gmgn_scout import ScoutResult


class ScoringResult(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    verdict: VerdictType
    confidence: ConfidenceType
    breakdown: ScoreBreakdown
    all_flags: list[ScoutFlag] = Field(default_factory=list)
    is_shortlisted_for_ai: bool = False


def evaluate_token_score(
    data: EnrichedTokenData,
    scout: ScoutResult,
    config: AppConfig,
) -> ScoringResult:
    breakdown, extra_flags = compute_score_breakdown(data, scout, config)
    all_flags = list(scout.flags) + extra_flags

    raw_total = (
        breakdown.contract
        + breakdown.holders
        + breakdown.volume_integrity
        + breakdown.liquidity
        + breakdown.social
    )
    risk_score = min(100, max(0, raw_total))

    # Base verdict mapping
    if risk_score >= 70:
        verdict: VerdictType = "AVOID"
    elif risk_score >= 50:
        verdict = "HIGH RISK"
    elif risk_score >= 30:
        verdict = "WATCH"
    else:
        verdict = "PROMISING"

    # Confidence calculation
    total_signals = max(1, scout.evaluated_signals)
    unknown_ratio = scout.unknown_signals / total_signals
    vr = config.thresholds.verdict_rules
    if data.rugcheck is None or unknown_ratio > vr.low_confidence_unknown_ratio:
        confidence: ConfidenceType = "low"
    elif unknown_ratio > vr.medium_confidence_unknown_ratio:
        confidence = "medium"
    else:
        confidence = "high"

    has_contract_critical = any(
        f.category == "contract" and f.severity == "critical" for f in all_flags
    )
    has_any_critical = any(f.severity == "critical" for f in all_flags)

    # Override Rule 2: PROMISING requires liquidity >= $25k, zero critical flags, and RugCheck present
    if verdict == "PROMISING":
        liq_ok = (data.market.liquidity_usd or 0.0) >= vr.promising_min_liquidity_usd
        if not liq_ok or has_any_critical or data.rugcheck is None:
            verdict = "WATCH"

    # Override Rule 1 (Hard Stop): Any critical flag in Contract category forces AVOID
    if has_contract_critical:
        verdict = "AVOID"

    is_shortlisted = verdict in ("PROMISING", "WATCH")

    return ScoringResult(
        risk_score=risk_score,
        verdict=verdict,
        confidence=confidence,
        breakdown=breakdown,
        all_flags=all_flags,
        is_shortlisted_for_ai=is_shortlisted,
    )
