from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

VerdictType = Literal["AVOID", "HIGH RISK", "WATCH", "PROMISING"]
ConfidenceType = Literal["high", "medium", "low"]
SeverityType = Literal["info", "warn", "critical"]
FlagCategoryType = Literal["contract", "holders", "volume_integrity", "liquidity", "social"]
HealthStatusType = Literal["HEALTHY", "MIXED", "UNHEALTHY"]
BuyerQualityType = Literal["ORGANIC", "BOT_HEAVY", "INSIDER_DRIVEN", "UNKNOWN"]


class TokenIdentity(BaseModel):
    chain: str = "solana"
    address: str
    symbol: str = "UNKNOWN"
    name: str = "Unknown Token"
    logo_url: str | None = None


class MarketMetrics(BaseModel):
    price_usd: float | None = None
    liquidity_usd: float | None = None
    market_cap: float | None = None
    fdv: float | None = None
    volume_24h: float | None = None
    volume_h6: float | None = None
    volume_h1: float | None = None
    volume_m5: float | None = None
    txns_m5_buys: int | None = None
    txns_m5_sells: int | None = None
    txns_h1_buys: int | None = None
    txns_h1_sells: int | None = None
    txns_h6_buys: int | None = None
    txns_h6_sells: int | None = None
    txns_h24_buys: int | None = None
    txns_h24_sells: int | None = None
    price_change_m5: float | None = None
    price_change_h1: float | None = None
    price_change_h6: float | None = None
    price_change_h24: float | None = None
    pair_age_minutes: int | None = None
    pair_address: str | None = None
    dex_id: str | None = None
    pair_url: str | None = None


class ScoutFlag(BaseModel):
    category: FlagCategoryType
    severity: SeverityType
    code: str
    value: float | int | str | bool | None = None
    threshold: float | int | str | bool | None = None
    source: str
    detail_id: str | None = None


class ScoreBreakdown(BaseModel):
    contract: int = 0
    holders: int = 0
    volume_integrity: int = 0
    liquidity: int = 0
    social: int = 0


class LiquidityStress(BaseModel):
    rating: Literal["STRONG", "MODERATE", "WEAK", "UNKNOWN"] = "UNKNOWN"
    lp_to_top10_ratio: float | None = None
    note_id: str = ""


class DecisionBrief(BaseModel):
    bull_case_id: str = ""
    red_flag_id: str = ""
    invalidation_trigger_id: str = ""


class AIAnalysisResult(BaseModel):
    status: Literal["completed", "skipped", "unavailable"] = "skipped"
    model: str = "gemini-3.8-flash-high"
    analyzed_at: str | None = None
    health_status: HealthStatusType = "MIXED"
    buyer_quality: BuyerQualityType = "UNKNOWN"
    conviction_score: int = Field(default=50, ge=0, le=100)
    momentum_phase: str = "UNKNOWN"
    liquidity_stress: LiquidityStress = Field(default_factory=LiquidityStress)
    narrative_quality: str = "UNKNOWN"
    summary_id: str = ""
    decision_brief: DecisionBrief = Field(default_factory=DecisionBrief)
    shortlist_rank_reason_id: str = ""


class TokenAuditReport(BaseModel):
    token: TokenIdentity
    scanned_at: str
    market: MarketMetrics
    risk_score: int = Field(ge=0, le=100)
    verdict: VerdictType
    verdict_changed: bool = False
    previous_verdict: VerdictType | None = None
    confidence: ConfidenceType = "high"
    breakdown: ScoreBreakdown
    flags: list[ScoutFlag] = Field(default_factory=list)
    summary_id: str
    ai_analysis: AIAnalysisResult | None = None
    holder_metrics: dict[str, Any] = Field(default_factory=dict)
    social_meta: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = "Analisis otomatis, bukan nasihat keuangan."
