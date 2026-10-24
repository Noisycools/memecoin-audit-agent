"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, RefreshCw, Activity } from "lucide-react";
import {
  API_BASE_URL,
  fetchSystemHealth,
  fetchTokens,
  triggerManualAudit,
  triggerScanNow,
} from "@/lib/api";
import { SystemHealth, TokenAuditReport } from "@/lib/types";
import { TopAIPicksBanner } from "@/components/TopAIPicksBanner";
import { LiveScannerTable } from "@/components/LiveScannerTable";

export default function LiveScannerPage() {
  const router = useRouter();
  const [tokens, setTokens] = useState<TokenAuditReport[]>([]);
  const [topPicks, setTopPicks] = useState<TokenAuditReport[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanningNow, setScanningNow] = useState(false);

  // Filters
  const [verdictFilter, setVerdictFilter] = useState<string>("");
  const [chainFilter, setChainFilter] = useState<string>("solana");
  const [minLiqFilter, setMinLiqFilter] = useState<string>("");
  const [minAgeFilter, setMinAgeFilter] = useState<string>("");
  const [maxAgeFilter, setMaxAgeFilter] = useState<string>("");
  const [hideCritical, setHideCritical] = useState<boolean>(false);

  // Manual audit input
  const [manualMint, setManualMint] = useState("");
  const [auditingMint, setAuditingMint] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set());

  const loadData = useCallback(async () => {
    try {
      const [tokenRes, healthRes] = await Promise.all([
        fetchTokens({
          verdict: verdictFilter || undefined,
          chain: chainFilter || undefined,
          min_liquidity_usd: minLiqFilter ? Number(minLiqFilter) : undefined,
          min_age_minutes: minAgeFilter ? Number(minAgeFilter) : undefined,
          max_age_minutes: maxAgeFilter ? Number(maxAgeFilter) : undefined,
          hide_critical: hideCritical,
        }),
        fetchSystemHealth().catch(() => null),
      ]);
      setTokens(tokenRes.items);
      setTopPicks(tokenRes.top_ai_picks);
      if (healthRes) setHealth(healthRes);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Gagal memuat data");
    } finally {
      setLoading(false);
    }
  }, [verdictFilter, chainFilter, minLiqFilter, minAgeFilter, maxAgeFilter, hideCritical]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const es = new EventSource(`${API_BASE_URL}/api/v1/stream/events`);
    const onScored = (e: MessageEvent) => {
      try {
        const incoming: TokenAuditReport = JSON.parse(e.data);
        setHighlighted((prev) => new Set(prev).add(incoming.token.address));
        loadData();
      } catch {
        // ignore parse errors
      }
    };
    es.addEventListener("token_scored", onScored);
    es.addEventListener("ai_analyzed", onScored);
    es.addEventListener("verdict_changed", onScored);
    return () => es.close();
  }, [loadData]);

  const handleManualAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualMint.trim()) return;
    setAuditingMint(true);
    setErrorMsg(null);
    try {
      const report = await triggerManualAudit(manualMint.trim(), "solana");
      router.push(`/tokens/${report.token.chain}/${report.token.address}`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Audit manual gagal");
    } finally {
      setAuditingMint(false);
    }
  };

  const handleScanNow = async () => {
    setScanningNow(true);
    setErrorMsg(null);
    try {
      await triggerScanNow();
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Pemindaian gagal");
    } finally {
      setScanningNow(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Status & Manual Audit Bar */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-3.5">
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
          <span className="inline-flex items-center gap-1.5 text-emerald-400 font-semibold">
            <Activity className="w-4 h-4" />
            Live Stream Aktif
          </span>
          <span className="text-slate-600">|</span>
          <span>
            DexScreener:{" "}
            <b
              className={
                health?.dexscreener.healthy !== false
                  ? "text-emerald-400"
                  : "text-rose-400"
              }
            >
              {health?.dexscreener.healthy !== false ? "OK" : "Gangguan"}
            </b>{" "}
            ({health?.dexscreener.remaining_tokens_per_min ?? 300} kuota/m)
          </span>
          <span className="text-slate-600">|</span>
          <span>
            RugCheck:{" "}
            <b
              className={
                health?.rugcheck.healthy !== false
                  ? "text-emerald-400"
                  : "text-rose-400"
              }
            >
              {health?.rugcheck.healthy !== false ? "OK" : "Gangguan"}
            </b>
          </span>
          <span className="text-slate-600">|</span>
          <span>
            9router AI:{" "}
            <b className="text-indigo-300">
              {health?.nine_router.model || "gemini-3.8-flash-high"}
            </b>
          </span>
          <span className="text-slate-600">|</span>
          <span>
            Scan Terakhir:{" "}
            <b className="text-slate-200">
              {health?.last_discovery_at
                ? new Date(health.last_discovery_at).toLocaleTimeString("id-ID")
                : "Menunggu siklus"}
            </b>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <form onSubmit={handleManualAudit} className="flex items-center gap-2 flex-1">
            <div className="relative flex-1 min-w-[240px]">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={manualMint}
                onChange={(e) => setManualMint(e.target.value)}
                placeholder="Paste alamat mint Solana untuk audit instan..."
                className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              disabled={auditingMint}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold text-white whitespace-nowrap"
            >
              {auditingMint ? "Membedah..." : "Audit Koin"}
            </button>
          </form>

          <button
            onClick={handleScanNow}
            disabled={scanningNow}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-xs font-medium text-slate-200 border border-slate-700"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanningNow ? "animate-spin" : ""}`} />
            <span>{scanningNow ? "Memindai..." : "Pindai Sekarang"}</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="rounded-lg bg-rose-950/60 border border-rose-800 p-3 text-xs text-rose-200">
          {errorMsg}
        </div>
      )}

      {/* Option A: Unified Top AI Picks Highlight Banner */}
      <TopAIPicksBanner picks={topPicks} />

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {(["", "PROMISING", "WATCH", "HIGH RISK", "AVOID"] as const).map(
            (v) => (
              <button
                key={v || "ALL"}
                onClick={() => setVerdictFilter(v)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                  verdictFilter === v
                    ? "bg-indigo-600 text-white border-indigo-500"
                    : "bg-slate-900 text-slate-300 border-slate-800 hover:bg-slate-800"
                }`}
              >
                {v === "" ? "Semua Verdict" : v}
              </button>
            )
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">Chain:</span>
            <select
              value={chainFilter}
              onChange={(e) => setChainFilter(e.target.value)}
              className="px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-100"
            >
              <option value="solana">Solana</option>
              <option value="">Semua</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">Umur (m):</span>
            <input
              type="number"
              value={minAgeFilter}
              onChange={(e) => setMinAgeFilter(e.target.value)}
              placeholder="Min"
              className="w-16 px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-100"
            />
            <span>-</span>
            <input
              type="number"
              value={maxAgeFilter}
              onChange={(e) => setMaxAgeFilter(e.target.value)}
              placeholder="Max"
              className="w-20 px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-100"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">Likuiditas Min ($):</span>
            <input
              type="number"
              value={minLiqFilter}
              onChange={(e) => setMinLiqFilter(e.target.value)}
              placeholder="5000"
              className="w-24 px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-slate-100"
            />
          </div>

          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300">
            <input
              type="checkbox"
              checked={hideCritical}
              onChange={(e) => setHideCritical(e.target.checked)}
              className="rounded border-slate-700 bg-slate-900 text-indigo-600"
            />
            <span>Hanya Tanpa Flag Critical</span>
          </label>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((n) => (
            <div
              key={n}
              className="h-12 rounded-lg bg-slate-900/70 animate-pulse border border-slate-800/60"
            />
          ))}
        </div>
      ) : (
        <LiveScannerTable data={tokens} highlightedAddresses={highlighted} />
      )}
    </div>
  );
}
