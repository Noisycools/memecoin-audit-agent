"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Copy,
  Check,
  ExternalLink,
  RefreshCw,
  BookmarkPlus,
} from "lucide-react";
import {
  API_BASE_URL,
  fetchTokenDetail,
  triggerManualAudit,
} from "@/lib/api";
import { TokenDetailView } from "@/lib/types";
import { AIDecisionPanel } from "@/components/AIDecisionPanel";
import { TokenCharts } from "@/components/TokenCharts";

export default function TokenDetailPage() {
  const params = useParams<{ chain: string; address: string }>();
  const chain = params?.chain || "solana";
  const address = params?.address || "";

  const [detail, setDetail] = useState<TokenDetailView | null>(null);
  const [loading, setLoading] = useState(true);
  const [rescanning, setRescanning] = useState(false);
  const [copied, setCopied] = useState(false);
  const [watchlisted, setWatchlisted] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    if (!address) return;
    try {
      const d = await fetchTokenDetail(chain, address);
      setDetail(d);
      setWatchlisted(d.is_watchlisted);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error ? err.message : "Gagal memuat detail token"
      );
    } finally {
      setLoading(false);
    }
  }, [chain, address]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const handleCopy = () => {
    navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleRescan = async () => {
    setRescanning(true);
    setErrorMsg(null);
    try {
      await triggerManualAudit(address, chain);
      await loadDetail();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Gagal memindai ulang");
    } finally {
      setRescanning(false);
    }
  };

  const handleToggleWatchlist = async () => {
    if (!detail) return;
    try {
      if (watchlisted) {
        await fetch(
          `${API_BASE_URL}/api/v1/watchlist/${chain}/${address}`,
          { method: "DELETE" }
        );
        setWatchlisted(false);
      } else {
        await fetch(`${API_BASE_URL}/api/v1/watchlist`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chain,
            address,
            symbol: detail.report.token.symbol,
            name: detail.report.token.name,
          }),
        });
        setWatchlisted(true);
      }
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-24 rounded-xl bg-slate-900 animate-pulse" />
        <div className="h-48 rounded-xl bg-slate-900 animate-pulse" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 text-center space-y-3">
        <p className="text-slate-300">
          {errorMsg || "Token belum ditemukan di database."}
        </p>
        <button
          onClick={handleRescan}
          disabled={rescanning}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold"
        >
          {rescanning ? "Memindai..." : "Audit Token Ini Sekarang"}
        </button>
      </div>
    );
  }

  const { report, snapshots } = detail;
  const b = report.breakdown;

  const breakdownRows = [
    { label: "Keamanan Kontrak", score: b.contract, max: 30 },
    { label: "Distribusi Holder & Bundle", score: b.holders, max: 25 },
    { label: "Integritas Volume (Wash/Bot)", score: b.volume_integrity, max: 20 },
    { label: "Kedalaman Likuiditas", score: b.liquidity, max: 15 },
    { label: "Sosial & Metadata", score: b.social, max: 10 },
  ];

  const contractFlags = report.flags.filter((f) => f.category === "contract");
  const holderFlags = report.flags.filter((f) => f.category === "holders");
  const volumeFlags = report.flags.filter(
    (f) => f.category === "volume_integrity" || f.category === "liquidity" || f.category === "social"
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Kembali ke Live Scanner</span>
        </Link>

        <div className="flex items-center gap-2">
          <button
            onClick={handleToggleWatchlist}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border ${
              watchlisted
                ? "bg-amber-950/80 text-amber-300 border-amber-700"
                : "bg-slate-900 text-slate-300 border-slate-700 hover:bg-slate-800"
            }`}
          >
            <BookmarkPlus className="w-3.5 h-3.5" />
            <span>{watchlisted ? "Di Watchlist ✓" : "Simpan ke Watchlist"}</span>
          </button>

          <button
            onClick={handleRescan}
            disabled={rescanning}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold text-white"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${rescanning ? "animate-spin" : ""}`}
            />
            <span>{rescanning ? "Memindai Ulang..." : "Pindai Ulang"}</span>
          </button>
        </div>
      </div>

      {/* Header Card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-white">
              ${report.token.symbol} · {report.token.name}
            </h1>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 uppercase">
              {report.token.chain}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-slate-400">
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1 font-mono bg-slate-950 px-2 py-1 rounded border border-slate-800 hover:border-slate-600 text-slate-300"
            >
              <span>{address}</span>
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>

            <a
              href={`https://dexscreener.com/${chain}/${address}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-sky-400 hover:underline"
            >
              <span>DexScreener</span>
              <ExternalLink className="w-3 h-3" />
            </a>

            <a
              href={`https://rugcheck.xyz/tokens/${address}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-indigo-400 hover:underline"
            >
              <span>RugCheck</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs text-slate-400">
              Skor Risiko Deterministik
            </div>
            <div className="text-2xl font-extrabold text-white">
              {report.risk_score}
              <span className="text-sm font-normal text-slate-400">/100</span>
            </div>
            <div className="text-[11px] text-slate-400">
              Confidence: <b className="uppercase">{report.confidence}</b>
            </div>
          </div>

          <div
            className={`px-4 py-2.5 rounded-xl font-extrabold text-sm border ${
              report.verdict === "PROMISING"
                ? "bg-emerald-950 text-emerald-300 border-emerald-600"
                : report.verdict === "WATCH"
                ? "bg-amber-950 text-amber-300 border-amber-600"
                : report.verdict === "HIGH RISK"
                ? "bg-orange-950 text-orange-300 border-orange-600"
                : "bg-rose-950 text-rose-300 border-rose-600"
            }`}
          >
            {report.verdict}
          </div>
        </div>
      </div>

      {/* 9router AI Decision Panel */}
      <AIDecisionPanel
        ai={report.ai_analysis}
        fallbackSummary={report.summary_id}
      />

      {/* Score Breakdown & GMGN Scout Flags */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Rincian Skor Risiko per Kategori
          </h3>
          {breakdownRows.map((r) => {
            const pct = Math.min(100, Math.round((r.score / r.max) * 100));
            return (
              <div key={r.label} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-300">{r.label}</span>
                  <span className="font-bold text-slate-200">
                    {r.score}/{r.max}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      pct > 65
                        ? "bg-rose-500"
                        : pct > 35
                        ? "bg-amber-500"
                        : "bg-emerald-500"
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Temuan Flag GMGN Scout &amp; Bukti Numerik ({report.flags.length})
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="rounded-lg bg-slate-950/70 border border-slate-800 p-3 space-y-2">
              <div className="font-bold text-slate-300">
                Keamanan Kontrak ({contractFlags.length})
              </div>
              {contractFlags.length === 0 ? (
                <div className="text-emerald-400">
                  ✓ Tidak ada celah kontrak terdeteksi
                </div>
              ) : (
                contractFlags.map((f, i) => (
                  <div
                    key={i}
                    className="p-2 rounded bg-slate-900 border border-slate-800"
                  >
                    <div className="font-bold text-rose-400">
                      [{f.severity.toUpperCase()}] {f.code}
                    </div>
                    <div className="text-slate-300 mt-0.5">{f.detail_id}</div>
                    <div className="text-[10px] text-slate-500 mt-1">
                      Nilai: {String(f.value)} · Sumber: {f.source}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="rounded-lg bg-slate-950/70 border border-slate-800 p-3 space-y-2">
              <div className="font-bold text-slate-300">
                Bundle &amp; Holder ({holderFlags.length})
              </div>
              {holderFlags.length === 0 ? (
                <div className="text-emerald-400">
                  ✓ Distribusi holder terkendali
                </div>
              ) : (
                holderFlags.map((f, i) => (
                  <div
                    key={i}
                    className="p-2 rounded bg-slate-900 border border-slate-800"
                  >
                    <div className="font-bold text-amber-400">
                      [{f.severity.toUpperCase()}] {f.code}
                    </div>
                    <div className="text-slate-300 mt-0.5">{f.detail_id}</div>
                    <div className="text-[10px] text-slate-500 mt-1">
                      Nilai: {String(f.value)} (Batas: {String(f.threshold)}) ·{" "}
                      {f.source}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="rounded-lg bg-slate-950/70 border border-slate-800 p-3 space-y-2">
              <div className="font-bold text-slate-300">
                Wash Trade, Likuiditas &amp; Sosial ({volumeFlags.length})
              </div>
              {volumeFlags.length === 0 ? (
                <div className="text-emerald-400">
                  ✓ Pola volume &amp; likuiditas wajar
                </div>
              ) : (
                volumeFlags.map((f, i) => (
                  <div
                    key={i}
                    className="p-2 rounded bg-slate-900 border border-slate-800"
                  >
                    <div className="font-bold text-sky-400">
                      [{f.severity.toUpperCase()}] {f.code}
                    </div>
                    <div className="text-slate-300 mt-0.5">{f.detail_id}</div>
                    <div className="text-[10px] text-slate-500 mt-1">
                      Nilai: {String(f.value)} · Sumber: {f.source}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <TokenCharts
        snapshots={snapshots}
        holderMetrics={report.holder_metrics}
      />
    </div>
  );
}
