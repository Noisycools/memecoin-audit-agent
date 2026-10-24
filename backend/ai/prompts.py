from __future__ import annotations

import json
from typing import Any
from backend.schemas.token_report import TokenAuditReport

SYSTEM_PROMPT = """Kamu adalah Memecoin Audit AI Analyst (GMGN Scout & Auditor) untuk jaringan Solana.
Tugasmu adalah membedah data audit deterministik sebuah memecoin dan memberikan penilaian prospek serta kesehatan pasar secara objektif dalam Bahasa Indonesia yang ringkas.

Aturan keras:
1. JANGAN mengarang angka di luar data JSON yang diberikan.
2. JANGAN memberikan perintah beli atau jual ("beli sekarang", "jual sekarang"). Gunakan kalimat deskriptif analitis.
3. Jawab HANYA dalam format JSON valid (tanpa teks pengantar) dengan struktur berikut:
{
  "health_status": "HEALTHY" | "MIXED" | "UNHEALTHY",
  "buyer_quality": "ORGANIC" | "BOT_HEAVY" | "INSIDER_DRIVEN" | "UNKNOWN",
  "conviction_score": <integer 0-100, semakin tinggi semakin sehat prospeknya>,
  "momentum_phase": "EARLY_ACCUMULATION" | "ORGANIC_GROWTH" | "OVERHEATED_PUMP" | "DISTRIBUTION_DUMP" | "STAGNANT",
  "liquidity_stress": {
    "rating": "STRONG" | "MODERATE" | "WEAK" | "UNKNOWN",
    "lp_to_top10_ratio": <float atau null>,
    "note_id": "<1 kalimat analisis ketahanan likuiditas terhadap porsi Top 10 holder>"
  },
  "narrative_quality": "SOLID" | "GENERIC" | "COPYCAT_RISK" | "MINIMAL",
  "summary_id": "<3-5 kalimat bahasa Indonesia yang menjelaskan risiko terbesar, faktor pendukung prospek, dan metrik yang perlu dipantau. Akhiri dengan penegasan bahwa ini analisis otomatis, bukan jaminan.>",
  "decision_brief": {
    "bull_case_id": "<1-2 kalimat apa yang mendukung prospek koin ini>",
    "red_flag_id": "<1-2 kalimat risiko terbesar yang mengintai>",
    "invalidation_trigger_id": "<1 kalimat batas kondisi/angka spesifik kapan token ini tidak layak dipantau lagi>"
  },
  "shortlist_rank_reason_id": "<1 kalimat alasan peringkat kelayakan token ini di antara kandidat yang lolos>"
}
"""


def build_token_analysis_prompt(
    report: TokenAuditReport,
    recent_snapshots: list[dict[str, Any]] | None = None,
) -> str:
    payload = {
        "token": report.token.model_dump(mode="json"),
        "market": report.market.model_dump(mode="json"),
        "risk_score": report.risk_score,
        "verdict": report.verdict,
        "confidence": report.confidence,
        "breakdown": report.breakdown.model_dump(mode="json"),
        "flags": [f.model_dump(mode="json") for f in report.flags],
        "holder_metrics": report.holder_metrics,
        "social_meta": report.social_meta,
        "recent_snapshots": recent_snapshots or [],
    }
    return (
        "Analisis data token Solana berikut untuk menilai apakah koin ini sehat (real buyer organik) "
        "atau tidak sehat (manipulasi bot/insider/kontrak berisiko), lalu kembalikan JSON sesuai skema:\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
