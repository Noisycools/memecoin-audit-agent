"use client";

import Link from "next/link";
import { Sparkles, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { TokenAuditReport } from "@/lib/types";

function formatUsd(val: number | null | undefined): string {
  if (val === null || val === undefined) return "unknown";
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  return `$${val.toFixed(2)}`;
}

export function TopAIPicksBanner({ picks }: { picks: TokenAuditReport[] }) {
  if (!picks || picks.length === 0) {
    return (
      <div className="rounded-xl border border-indigo-900/60 bg-gradient-to-br from-indigo-950/40 via-slate-900 to-slate-950 p-4 mb-6">
        <div className="flex items-center gap-2 text-indigo-300 text-xs font-bold uppercase tracking-wider mb-1">
          <Sparkles className="w-4 h-4" />
          <span>Kandidat Terbaik Hasil Bedah AI · 9router (gemini-3.8-flash-high)</span>
        </div>
        <p className="text-sm text-slate-400">
          Belum ada koin yang lolos saringan <code className="text-emerald-400">PROMISING</code> atau{" "}
          <code className="text-amber-400">WATCH</code>. Klik tombol <b>Pindai Sekarang</b> atau masukkan alamat mint untuk mulai membedah koin.
        </p>
      </div>
    );
  }

  return (
    <section className="rounded-xl border border-indigo-800/70 bg-gradient-to-br from-indigo-950/50 via-slate-900/90 to-slate-950 p-4 mb-6 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 text-indigo-300 text-xs font-bold uppercase tracking-wider">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <span>Kandidat Terbaik Hasil Bedah AI (Dari Daftar PROMISING &amp; WATCH)</span>
        </div>
        <span className="text-xs text-slate-400">
          Diurutkan berdasarkan Kesehatan Pasar, Real Buyer, &amp; Skor Risiko
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {picks.slice(0, 3).map((item) => {
          const ai = item.ai_analysis;
          const health = ai?.health_status || "MIXED";
          const buyer = ai?.buyer_quality || "UNKNOWN";
          const top10 = item.holder_metrics?.top10_pct_ex_lp;

          const borderColor =
            health === "HEALTHY"
              ? "border-l-emerald-500"
              : health === "MIXED"
              ? "border-l-amber-500"
              : "border-l-rose-500";

          return (
            <Link
              key={`${item.token.chain}:${item.token.address}`}
              href={`/tokens/${item.token.chain}/${item.token.address}`}
              className={`block rounded-lg bg-slate-900/90 border border-slate-800 border-l-4 ${borderColor} p-3.5 hover:bg-slate-800/80 transition`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="font-bold text-white text-sm">
                    ${item.token.symbol}
                  </span>
                  <span className="text-xs text-slate-400 ml-1.5">
                    {item.token.name}
                  </span>
                </div>
                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${
                    health === "HEALTHY"
                      ? "bg-emerald-950 text-emerald-300 border border-emerald-700/60"
                      : health === "MIXED"
                      ? "bg-amber-950 text-amber-300 border border-amber-700/60"
                      : "bg-rose-950 text-rose-300 border border-rose-700/60"
                  }`}
                >
                  {health === "HEALTHY" ? (
                    <CheckCircle2 className="w-3 h-3" />
                  ) : health === "MIXED" ? (
                    <AlertTriangle className="w-3 h-3" />
                  ) : (
                    <XCircle className="w-3 h-3" />
                  )}
                  {health === "HEALTHY"
                    ? "SEHAT"
                    : health === "MIXED"
                    ? "MERAGUKAN"
                    : "TIDAK SEHAT"}{" "}
                  ·{" "}
                  {buyer === "ORGANIC"
                    ? "REAL BUYER"
                    : buyer === "BOT_HEAVY"
                    ? "INDIKASI BOT"
                    : buyer === "INSIDER_DRIVEN"
                    ? "INSIDER"
                    : "BUYER ?"}
                </span>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-300">
                <span>
                  Risiko:{" "}
                  <b
                    className={
                      item.risk_score < 30
                        ? "text-emerald-400"
                        : item.risk_score < 50
                        ? "text-amber-400"
                        : "text-rose-400"
                    }
                  >
                    {item.risk_score}/100 ({item.verdict})
                  </b>
                </span>
                <span>Liq: {formatUsd(item.market.liquidity_usd)}</span>
                <span>
                  Top10: {top10 !== null && top10 !== undefined ? `${top10}%` : "unknown"}
                </span>
              </div>

              <p className="mt-2 text-xs text-slate-300 line-clamp-2 leading-relaxed">
                {ai?.decision_brief?.bull_case_id || item.summary_id}
              </p>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
