"use client";

import { Bot, CheckCircle2, AlertTriangle, ShieldX } from "lucide-react";
import { AIAnalysisResult } from "@/lib/types";

export function AIDecisionPanel({
  ai,
  fallbackSummary,
}: {
  ai?: AIAnalysisResult | null;
  fallbackSummary: string;
}) {
  const health = ai?.health_status || "MIXED";
  const buyer = ai?.buyer_quality || "UNKNOWN";

  return (
    <div className="rounded-xl border border-indigo-700/60 bg-gradient-to-br from-indigo-950/60 via-slate-900 to-slate-950 p-5 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-indigo-900/60 pb-3.5 mb-4">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-indigo-400" />
          <div>
            <h2 className="text-sm font-bold text-indigo-200 uppercase tracking-wider">
              Panel Analisis &amp; Keputusan AI · 9router ({ai?.model || "gemini-3.8-flash-high"})
            </h2>
            <p className="text-xs text-slate-400">
              Status:{" "}
              {ai?.status === "completed"
                ? "Analisis AI Langsung (9router)"
                : "Ringkasan Aturan Deterministik (Fallback)"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${
              health === "HEALTHY"
                ? "bg-emerald-950 text-emerald-300 border-emerald-600/60"
                : health === "MIXED"
                ? "bg-amber-950 text-amber-300 border-amber-600/60"
                : "bg-rose-950 text-rose-300 border-rose-600/60"
            }`}
          >
            {health === "HEALTHY" ? (
              <CheckCircle2 className="w-4 h-4" />
            ) : health === "MIXED" ? (
              <AlertTriangle className="w-4 h-4" />
            ) : (
              <ShieldX className="w-4 h-4" />
            )}
            VONIS:{" "}
            {health === "HEALTHY"
              ? "KOIN SEHAT"
              : health === "MIXED"
              ? "MERAGUKAN"
              : "TIDAK SEHAT"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-4">
        <div className="rounded-lg bg-slate-950/80 border border-slate-800 p-3">
          <div className="text-[11px] text-slate-400">Kualitas Pembeli</div>
          <div
            className={`text-sm font-bold mt-0.5 ${
              buyer === "ORGANIC"
                ? "text-emerald-400"
                : buyer === "BOT_HEAVY"
                ? "text-rose-400"
                : "text-amber-400"
            }`}
          >
            {buyer === "ORGANIC"
              ? "Real Buyer (Organik)"
              : buyer === "BOT_HEAVY"
              ? "Dominasi Bot / Wash"
              : buyer === "INSIDER_DRIVEN"
              ? "Didominasi Insider"
              : "Belum Pasti"}
          </div>
        </div>

        <div className="rounded-lg bg-slate-950/80 border border-slate-800 p-3">
          <div className="text-[11px] text-slate-400">Skor Prospek AI</div>
          <div className="text-sm font-bold text-indigo-300 mt-0.5">
            {ai?.conviction_score ?? 50}/100
          </div>
        </div>

        <div className="rounded-lg bg-slate-950/80 border border-slate-800 p-3">
          <div className="text-[11px] text-slate-400">Fase Momentum</div>
          <div className="text-sm font-bold text-sky-300 mt-0.5">
            {ai?.momentum_phase || "UNKNOWN"}
          </div>
        </div>

        <div className="rounded-lg bg-slate-950/80 border border-slate-800 p-3">
          <div className="text-[11px] text-slate-400">Ketahanan LP vs Top 10</div>
          <div className="text-sm font-bold text-slate-200 mt-0.5">
            {ai?.liquidity_stress?.rating || "UNKNOWN"}
          </div>
        </div>
      </div>

      <div className="rounded-lg bg-slate-950/90 border border-slate-800 p-4 space-y-2.5 text-sm">
        <p className="text-slate-200 leading-relaxed">
          {ai?.summary_id || fallbackSummary}
        </p>

        {ai?.decision_brief && (
          <div className="pt-2 border-t border-slate-800/80 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-2.5 rounded bg-emerald-950/30 border border-emerald-800/40">
              <div className="font-bold text-emerald-300 mb-1">
                ✓ Pendukung Prospek (Bull Case)
              </div>
              <div className="text-slate-300">
                {ai.decision_brief.bull_case_id || "-"}
              </div>
            </div>

            <div className="p-2.5 rounded bg-amber-950/30 border border-amber-800/40">
              <div className="font-bold text-amber-300 mb-1">
                ⚠ Risiko Terbesar (Red Flag)
              </div>
              <div className="text-slate-300">
                {ai.decision_brief.red_flag_id || "-"}
              </div>
            </div>

            <div className="p-2.5 rounded bg-rose-950/30 border border-rose-800/40">
              <div className="font-bold text-rose-300 mb-1">
                🛑 Batas Batal Pantau (Invalidation)
              </div>
              <div className="text-slate-300">
                {ai.decision_brief.invalidation_trigger_id || "-"}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
