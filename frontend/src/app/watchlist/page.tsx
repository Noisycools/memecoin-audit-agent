"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bell, Trash2, Plus, AlertTriangle } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";
import { TokenAuditReport } from "@/lib/types";

interface WatchlistEntry {
  chain: string;
  address: string;
  symbol: string;
  name: string;
  added_at: string;
  alert_on_verdict_change: boolean;
  alert_liquidity_drop_pct: number;
  alert_on_top_holder_sell: boolean;
  alert_on_authority_change: boolean;
  latest_report?: TokenAuditReport | null;
}

interface AlertEntry {
  id: number;
  chain: string;
  address: string;
  symbol: string;
  alert_type: string;
  severity: string;
  message_id: string;
  created_at: string;
}

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [alerts, setAlerts] = useState<AlertEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const [mintInput, setMintInput] = useState("");
  const [symbolInput, setSymbolInput] = useState("");
  const [liqDropPct, setLiqDropPct] = useState("20");

  const loadAll = useCallback(async () => {
    try {
      const [wlRes, alRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/v1/watchlist`, { cache: "no-store" }),
        fetch(`${API_BASE_URL}/api/v1/alerts`, { cache: "no-store" }),
      ]);
      if (wlRes.ok) {
        const wlData = await wlRes.json();
        setWatchlist(wlData.items || []);
      }
      if (alRes.ok) {
        const alData = await alRes.json();
        setAlerts(alData.items || []);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    const es = new EventSource(`${API_BASE_URL}/api/v1/stream/events`);
    const onAlert = () => loadAll();
    es.addEventListener("alert_triggered", onAlert);
    es.addEventListener("verdict_changed", onAlert);
    return () => es.close();
  }, [loadAll]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mintInput.trim()) return;
    await fetch(`${API_BASE_URL}/api/v1/watchlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chain: "solana",
        address: mintInput.trim(),
        symbol: symbolInput.trim() || "TOKEN",
        name: symbolInput.trim() || "Watched Token",
        alert_liquidity_drop_pct: Number(liqDropPct) || 20,
      }),
    });
    setMintInput("");
    setSymbolInput("");
    await loadAll();
  };

  const handleRemove = async (chain: string, address: string) => {
    await fetch(`${API_BASE_URL}/api/v1/watchlist/${chain}/${address}`, {
      method: "DELETE",
    });
    await loadAll();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">
            Watchlist &amp; Alert Real-Time
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Pantau perubahan verdict, penurunan likuiditas tajam, penjualan top
            holder, dan perubahan authority.
          </p>
        </div>
      </div>

      {/* Add Watchlist Form */}
      <form
        onSubmit={handleAdd}
        className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 flex flex-wrap items-end gap-3"
      >
        <div className="flex-1 min-w-[240px]">
          <label className="block text-[11px] text-slate-400 mb-1">
            Alamat Mint Token (Solana)
          </label>
          <input
            type="text"
            value={mintInput}
            onChange={(e) => setMintInput(e.target.value)}
            placeholder="Masukkan alamat mint..."
            className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
          />
        </div>

        <div className="w-36">
          <label className="block text-[11px] text-slate-400 mb-1">
            Simbol (Opsional)
          </label>
          <input
            type="text"
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value)}
            placeholder="BONKAI"
            className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
          />
        </div>

        <div className="w-44">
          <label className="block text-[11px] text-slate-400 mb-1">
            Alert Likuiditas Turun (%)
          </label>
          <input
            type="number"
            value={liqDropPct}
            onChange={(e) => setLiqDropPct(e.target.value)}
            className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-white"
          />
        </div>

        <button
          type="submit"
          className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white"
        >
          <Plus className="w-4 h-4" />
          <span>Tambah ke Watchlist</span>
        </button>
      </form>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Watchlist Table */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Daftar Token Dipantau ({watchlist.length})
          </h2>

          {loading ? (
            <div className="h-32 rounded bg-slate-900 animate-pulse" />
          ) : watchlist.length === 0 ? (
            <p className="text-xs text-slate-400 py-6 text-center">
              Belum ada token di watchlist.
            </p>
          ) : (
            <div className="space-y-2.5">
              {watchlist.map((item) => {
                const rep = item.latest_report;
                return (
                  <div
                    key={`${item.chain}:${item.address}`}
                    className="rounded-lg bg-slate-950/80 border border-slate-800 p-3 flex items-center justify-between gap-3"
                  >
                    <div>
                      <Link
                        href={`/tokens/${item.chain}/${item.address}`}
                        className="font-bold text-sm text-indigo-300 hover:underline"
                      >
                        ${item.symbol} · {item.name}
                      </Link>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        Alert Likuiditas: &gt;{item.alert_liquidity_drop_pct}% ·{" "}
                        {rep ? (
                          <span>
                            Verdict: <b>{rep.verdict}</b> (Skor{" "}
                            {rep.risk_score}/100)
                          </span>
                        ) : (
                          "Menunggu pemindaian"
                        )}
                      </div>
                    </div>

                    <button
                      onClick={() => handleRemove(item.chain, item.address)}
                      className="p-1.5 rounded hover:bg-rose-950/60 text-slate-400 hover:text-rose-300"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Alert Feed */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-amber-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Riwayat Notifikasi Alert ({alerts.length})
            </h2>
          </div>

          {alerts.length === 0 ? (
            <p className="text-xs text-slate-400 py-6 text-center">
              Belum ada alert yang terpicu.
            </p>
          ) : (
            <div className="space-y-2.5 max-h-[420px] overflow-y-auto">
              {alerts.map((al) => (
                <div
                  key={al.id}
                  className={`rounded-lg p-3 border text-xs ${
                    al.severity === "critical"
                      ? "bg-rose-950/30 border-rose-800/60 text-rose-200"
                      : "bg-amber-950/30 border-amber-800/60 text-amber-200"
                  }`}
                >
                  <div className="flex items-center justify-between font-bold mb-1">
                    <span className="inline-flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      ${al.symbol} · {al.alert_type}
                    </span>
                    <span className="text-[10px] opacity-75">
                      {new Date(al.created_at).toLocaleTimeString("id-ID")}
                    </span>
                  </div>
                  <p>{al.message_id}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
