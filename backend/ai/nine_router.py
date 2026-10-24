from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any
import httpx

from backend.ai.fallback import build_deterministic_fallback_analysis
from backend.ai.prompts import SYSTEM_PROMPT, build_token_analysis_prompt
from backend.config import AppConfig
from backend.schemas.token_report import (
    AIAnalysisResult,
    DecisionBrief,
    LiquidityStress,
    TokenAuditReport,
)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_json_fences(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = _FENCE_RE.sub("", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


class NineRouterClient:
    """OpenAI-compatible client for local 9router AI provider (port 20128)."""

    def __init__(
        self,
        config: AppConfig,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = http_client or httpx.AsyncClient(timeout=config.ai.timeout_seconds)
        self._owns_client = http_client is None
        self.last_ok_at: float | None = None
        self.last_error: str | None = None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def analyze_token(
        self,
        report: TokenAuditReport,
        recent_snapshots: list[dict[str, Any]] | None = None,
    ) -> AIAnalysisResult:
        base_url = self.config.ai.base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        model_name = self.config.ai.model
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.ai.api_key}",
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_token_analysis_prompt(report, recent_snapshots)},
            ],
            "temperature": 0.2,
        }

        try:
            resp = await self._client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            body = resp.json()
            content = (
                body.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            cleaned_json = _strip_json_fences(str(content))
            parsed = json.loads(cleaned_json)

            stress_raw = parsed.get("liquidity_stress") if isinstance(parsed.get("liquidity_stress"), dict) else {}
            brief_raw = parsed.get("decision_brief") if isinstance(parsed.get("decision_brief"), dict) else {}

            health = str(parsed.get("health_status") or "MIXED").upper()
            if health not in ("HEALTHY", "MIXED", "UNHEALTHY"):
                health = "MIXED"

            buyer = str(parsed.get("buyer_quality") or "UNKNOWN").upper()
            if buyer not in ("ORGANIC", "BOT_HEAVY", "INSIDER_DRIVEN", "UNKNOWN"):
                buyer = "UNKNOWN"

            stress_rating = str(stress_raw.get("rating") or "UNKNOWN").upper()
            if stress_rating not in ("STRONG", "MODERATE", "WEAK", "UNKNOWN"):
                stress_rating = "UNKNOWN"

            conviction = int(parsed.get("conviction_score") or max(0, 100 - report.risk_score))
            conviction = max(0, min(100, conviction))

            result = AIAnalysisResult(
                status="completed",
                model=model_name,
                analyzed_at=datetime.now(timezone.utc).astimezone().isoformat(),
                health_status=health,  # type: ignore[arg-type]
                buyer_quality=buyer,  # type: ignore[arg-type]
                conviction_score=conviction,
                momentum_phase=str(parsed.get("momentum_phase") or "UNKNOWN"),
                liquidity_stress=LiquidityStress(
                    rating=stress_rating,  # type: ignore[arg-type]
                    lp_to_top10_ratio=stress_raw.get("lp_to_top10_ratio"),
                    note_id=str(stress_raw.get("note_id") or ""),
                ),
                narrative_quality=str(parsed.get("narrative_quality") or "UNKNOWN"),
                summary_id=str(parsed.get("summary_id") or report.summary_id),
                decision_brief=DecisionBrief(
                    bull_case_id=str(brief_raw.get("bull_case_id") or ""),
                    red_flag_id=str(brief_raw.get("red_flag_id") or ""),
                    invalidation_trigger_id=str(brief_raw.get("invalidation_trigger_id") or ""),
                ),
                shortlist_rank_reason_id=str(parsed.get("shortlist_rank_reason_id") or ""),
            )
            self.last_ok_at = datetime.now(timezone.utc).timestamp()
            self.last_error = None
            return result
        except Exception as exc:
            self.last_error = str(exc)
            return build_deterministic_fallback_analysis(
                report=report,
                status="unavailable",
                model_name=model_name,
            )

    def rank_shortlist(self, reports: list[TokenAuditReport]) -> list[str]:
        """Sort shortlisted PROMISING/WATCH tokens by AI health, buyer quality, conviction, and low risk."""
        health_weight = {"HEALTHY": 3, "MIXED": 2, "UNHEALTHY": 1}
        buyer_weight = {"ORGANIC": 3, "UNKNOWN": 2, "INSIDER_DRIVEN": 1, "BOT_HEAVY": 0}

        def _sort_key(r: TokenAuditReport) -> tuple[int, int, int, int, float]:
            ai = r.ai_analysis
            h_score = health_weight.get(ai.health_status, 1) if ai else 1
            b_score = buyer_weight.get(ai.buyer_quality, 1) if ai else 1
            conv = ai.conviction_score if ai else (100 - r.risk_score)
            inv_risk = 100 - r.risk_score
            liq = r.market.liquidity_usd or 0.0
            return (h_score, b_score, conv, inv_risk, liq)

        sorted_reports = sorted(reports, key=_sort_key, reverse=True)
        return [r.token.address for r in sorted_reports]
