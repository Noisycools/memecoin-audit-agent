export type VerdictType = "AVOID" | "HIGH RISK" | "WATCH" | "PROMISING";
export type ConfidenceType = "high" | "medium" | "low";
export type SeverityType = "info" | "warn" | "critical";
export type HealthStatusType = "HEALTHY" | "MIXED" | "UNHEALTHY";
export type BuyerQualityType = "ORGANIC" | "BOT_HEAVY" | "INSIDER_DRIVEN" | "UNKNOWN";

export interface TokenIdentity {
  chain: string;
  address: string;
  symbol: string;
  name: string;
  logo_url?: string | null;
}

export interface MarketMetrics {
  price_usd: number | null;
  liquidity_usd: number | null;
  market_cap: number | null;
  fdv?: number | null;
  volume_24h: number | null;
  volume_h6?: number | null;
  volume_h1?: number | null;
  volume_m5?: number | null;
  txns_m5_buys?: number | null;
  txns_m5_sells?: number | null;
  txns_h1_buys?: number | null;
  txns_h1_sells?: number | null;
  price_change_m5?: number | null;
  price_change_h1?: number | null;
  pair_age_minutes: number | null;
  pair_address?: string | null;
  dex_id?: string | null;
  pair_url?: string | null;
}

export interface ScoutFlag {
  category: "contract" | "holders" | "volume_integrity" | "liquidity" | "social";
  severity: SeverityType;
  code: string;
  value: number | string | boolean | null;
  threshold: number | string | boolean | null;
  source: string;
  detail_id?: string | null;
}

export interface ScoreBreakdown {
  contract: number;
  holders: number;
  volume_integrity: number;
  liquidity: number;
  social: number;
}

export interface AIAnalysisResult {
  status: "completed" | "skipped" | "unavailable";
  model: string;
  analyzed_at?: string | null;
  health_status: HealthStatusType;
  buyer_quality: BuyerQualityType;
  conviction_score: number;
  momentum_phase: string;
  liquidity_stress: {
    rating: "STRONG" | "MODERATE" | "WEAK" | "UNKNOWN";
    lp_to_top10_ratio: number | null;
    note_id: string;
  };
  narrative_quality: string;
  summary_id: string;
  decision_brief: {
    bull_case_id: string;
    red_flag_id: string;
    invalidation_trigger_id: string;
  };
  shortlist_rank_reason_id: string;
}

export interface TokenAuditReport {
  token: TokenIdentity;
  scanned_at: string;
  market: MarketMetrics;
  risk_score: number;
  verdict: VerdictType;
  verdict_changed?: boolean;
  previous_verdict?: VerdictType | null;
  confidence: ConfidenceType;
  breakdown: ScoreBreakdown;
  flags: ScoutFlag[];
  summary_id: string;
  ai_analysis?: AIAnalysisResult | null;
  holder_metrics: Record<string, number | null | undefined>;
  social_meta: Record<string, unknown>;
  disclaimer: string;
}

export interface TokenDetailView {
  report: TokenAuditReport;
  verdict_changed: boolean;
  previous_verdict?: string | null;
  snapshots: Array<{
    scanned_at: string;
    price_usd: number | null;
    liquidity_usd: number | null;
    market_cap: number | null;
    volume_24h: number | null;
    risk_score: number;
    verdict: VerdictType;
  }>;
  is_watchlisted: boolean;
}

export interface SystemHealth {
  status: string;
  last_discovery_at: string | null;
  last_rescan_at: string | null;
  dexscreener: {
    healthy: boolean;
    remaining_tokens_per_min: number;
    last_error: string | null;
  };
  rugcheck: {
    healthy: boolean;
    remaining_tokens_per_min: number;
    last_error: string | null;
  };
  nine_router: {
    base_url: string;
    model: string;
    healthy: boolean;
    last_error: string | null;
  };
}
