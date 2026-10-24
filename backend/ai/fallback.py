from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from backend.schemas.token_report import (
    AIAnalysisResult,
    BuyerQualityType,
    DecisionBrief,
    HealthStatusType,
    LiquidityStress,
    TokenAuditReport,
)


def build_deterministic_fallback_analysis(
    report: TokenAuditReport,
    status: Literal["skipped", "unavailable"] = "unavailable",
    model_name: str = "gemini-3.8-flash-high",
) -> AIAnalysisResult:
    now_iso = datetime.now(timezone.utc).astimezone().isoformat()
    crit_flags = [f for f in report.flags if f.severity == "critical"]
    warn_flags = [f for f in report.flags if f.severity == "warn"]
    vol_flags = [f for f in report.flags if f.category == "volume_integrity"]
    holder_flags = [f for f in report.flags if f.category == "holders"]

    if report.verdict == "PROMISING" and not crit_flags and not vol_flags:
        health: HealthStatusType = "HEALTHY"
    elif report.verdict in ("PROMISING", "WATCH") and not crit_flags:
        health = "MIXED"
    else:
        health = "UNHEALTHY"

    if vol_flags:
        buyer_quality: BuyerQualityType = "BOT_HEAVY"
    elif any(f.code in ("INSIDER_BUNDLE_CLUSTER", "TOP10_CONCENTRATION") for f in holder_flags):
        buyer_quality = "INSIDER_DRIVEN"
    elif report.market.liquidity_usd and report.market.liquidity_usd >= 25000:
        buyer_quality = "ORGANIC"
    else:
        buyer_quality = "UNKNOWN"

    conviction = max(5, min(95, 100 - report.risk_score))
    liq_usd = report.market.liquidity_usd or 0.0
    mc_usd = report.market.market_cap or report.market.fdv or 0.0
    top10_pct = report.holder_metrics.get("top10_pct_ex_lp")

    lp_ratio: float | None = None
    stress_rating: Literal["STRONG", "MODERATE", "WEAK", "UNKNOWN"] = "UNKNOWN"
    stress_note = "Data distribusi holder atau market cap belum lengkap untuk menguji ketahanan likuiditas."

    if liq_usd > 0 and mc_usd > 0 and isinstance(top10_pct, (int, float)) and top10_pct > 0:
        top10_usd = mc_usd * (float(top10_pct) / 100.0)
        lp_ratio = round(liq_usd / top10_usd, 2) if top10_usd > 0 else None
        if lp_ratio is not None:
            if lp_ratio >= 0.6:
                stress_rating = "STRONG"
                stress_note = f"Likuiditas ${liq_usd:,.0f} cukup kuat dibanding nilai kepemilikan Top 10 (${top10_usd:,.0f})."
            elif lp_ratio >= 0.25:
                stress_rating = "MODERATE"
                stress_note = f"Likuiditas ${liq_usd:,.0f} moderat terhadap nilai Top 10 holder (${top10_usd:,.0f})."
            else:
                stress_rating = "WEAK"
                stress_note = f"Likuiditas ${liq_usd:,.0f} rawan tertekan jika Top 10 holder (${top10_usd:,.0f}) menjual bersamaan."

    if crit_flags:
        main_risk = crit_flags[0].detail_id or f"Flag kritis {crit_flags[0].code} terdeteksi."
    elif warn_flags:
        main_risk = warn_flags[0].detail_id or f"Peringatan pada {warn_flags[0].code}."
    else:
        main_risk = "Fluktuasi memecoin umur dini dan potensi rotasi volume cepat."

    if liq_usd >= 25000 and report.breakdown.contract == 0:
        bull_case = f"Kontrak bersih tanpa otoritas berbahaya dengan likuiditas mencapai ${liq_usd:,.0f}."
    else:
        bull_case = f"Token tercatat memiliki likuiditas ${liq_usd:,.0f} dan aktivitas pasar aktif di DexScreener."

    min_safe_liq = max(5000.0, round(liq_usd * 0.7, -2))
    invalidation = (
        f"Tinggalkan pantauan jika likuiditas turun di bawah ${min_safe_liq:,.0f} atau muncul flag kritis baru."
    )

    summary = (
        f"{report.token.name} ({report.token.symbol}) memperoleh skor risiko {report.risk_score}/100 "
        f"dengan verdict {report.verdict} (confidence: {report.confidence}). "
        f"Risiko utama saat ini: {main_risk} "
        f"Faktor pendukung: {bull_case} "
        f"Pantau pergerakan likuiditas serta konsentrasi top holder secara berkala. "
        f"Ini adalah analisis otomatis berdasarkan aturan deterministik, bukan jaminan atau nasihat keuangan."
    )

    return AIAnalysisResult(
        status=status,
        model=model_name,
        analyzed_at=now_iso,
        health_status=health,
        buyer_quality=buyer_quality,
        conviction_score=conviction,
        momentum_phase="EARLY_ACCUMULATION" if (report.market.pair_age_minutes or 999) < 120 else "ORGANIC_GROWTH",
        liquidity_stress=LiquidityStress(
            rating=stress_rating,
            lp_to_top10_ratio=lp_ratio,
            note_id=stress_note,
        ),
        narrative_quality="SOLID" if report.breakdown.social == 0 else "MINIMAL",
        summary_id=summary,
        decision_brief=DecisionBrief(
            bull_case_id=bull_case,
            red_flag_id=main_risk,
            invalidation_trigger_id=invalidation,
        ),
        shortlist_rank_reason_id=f"Skor risiko {report.risk_score}/100 dengan likuiditas ${liq_usd:,.0f}.",
    )
