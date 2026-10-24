"use client";

import { useEffect, useState } from "react";
import { Save, Check } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

export default function SettingsPage() {
  const [minLiquidity, setMinLiquidity] = useState("5000");
  const [minAge, setMinAge] = useState("5");
  const [maxAge, setMaxAge] = useState("10080");
  const [discoveryInterval, setDiscoveryInterval] = useState("60");
  const [rescanInterval, setRescanInterval] = useState("180");
  const [promisingMinLiq, setPromisingMinLiq] = useState("25000");

  const [wContract, setWContract] = useState("30");
  const [wHolders, setWHolders] = useState("25");
  const [wVolume, setWVolume] = useState("20");
  const [wLiquidity, setWLiquidity] = useState("15");
  const [wSocial, setWSocial] = useState("10");

  const [aiBaseUrl, setAiBaseUrl] = useState("http://localhost:20128/v1");
  const [aiModel, setAiModel] = useState("gemini-3.8-flash-high");

  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/settings`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        const pf = data.thresholds?.prefilter;
        const sc = data.thresholds?.scanner;
        const vr = data.thresholds?.verdict_rules;
        const w = data.weights;
        const ai = data.ai;
        if (pf) {
          setMinLiquidity(String(pf.min_liquidity_usd ?? 5000));
          setMinAge(String(pf.min_pair_age_minutes ?? 5));
          setMaxAge(String(pf.max_pair_age_minutes ?? 10080));
        }
        if (sc) {
          setDiscoveryInterval(String(sc.discovery_interval_seconds ?? 60));
          setRescanInterval(String(sc.rescan_interval_seconds ?? 180));
        }
        if (vr) {
          setPromisingMinLiq(String(vr.promising_min_liquidity_usd ?? 25000));
        }
        if (w) {
          setWContract(String(w.contract ?? 30));
          setWHolders(String(w.holders ?? 25));
          setWVolume(String(w.volume_integrity ?? 20));
          setWLiquidity(String(w.liquidity ?? 15));
          setWSocial(String(w.social ?? 10));
        }
        if (ai) {
          setAiBaseUrl(String(ai.base_url ?? "http://localhost:20128/v1"));
          setAiModel(String(ai.model ?? "gemini-3.8-flash-high"));
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(false);
    const res = await fetch(`${API_BASE_URL}/api/v1/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        min_liquidity_usd: Number(minLiquidity),
        min_pair_age_minutes: Number(minAge),
        max_pair_age_minutes: Number(maxAge),
        discovery_interval_seconds: Number(discoveryInterval),
        rescan_interval_seconds: Number(rescanInterval),
        promising_min_liquidity_usd: Number(promisingMinLiq),
        weights: {
          contract: Number(wContract),
          holders: Number(wHolders),
          volume_integrity: Number(wVolume),
          liquidity: Number(wLiquidity),
          social: Number(wSocial),
        },
        ai: {
          base_url: aiBaseUrl,
          model: aiModel,
        },
      }),
    });
    if (res.ok) {
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    }
  };

  return (
    <form onSubmit={handleSave} className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold text-white">
          Pengaturan Pipeline, Bobot Skor &amp; 9router AI
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Sesuaikan ambang batas pre-filter, bobot penalti kategori, interval
          pemindaian, dan endpoint lokal 9router.
        </p>
      </div>

      {/* Pre-Filter & Interval */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-300">
          1. Ambang Batas Pre-Filter &amp; Interval Pemindaian
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block text-slate-400 mb-1">
              Likuiditas Minimum Pre-filter ($)
            </label>
            <input
              type="number"
              value={minLiquidity}
              onChange={(e) => setMinLiquidity(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">
              Umur Pair Minimum (Menit)
            </label>
            <input
              type="number"
              value={minAge}
              onChange={(e) => setMinAge(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">
              Umur Pair Maksimum (Menit)
            </label>
            <input
              type="number"
              value={maxAge}
              onChange={(e) => setMaxAge(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">
              Likuiditas Min Verdict PROMISING ($)
            </label>
            <input
              type="number"
              value={promisingMinLiq}
              onChange={(e) => setPromisingMinLiq(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">
              Interval Discovery (Detik)
            </label>
            <input
              type="number"
              value={discoveryInterval}
              onChange={(e) => setDiscoveryInterval(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">
              Interval Re-Scan Shortlist (Detik)
            </label>
            <input
              type="number"
              value={rescanInterval}
              onChange={(e) => setRescanInterval(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>
        </div>
      </div>

      {/* Category Weights */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-300">
          2. Bobot Maksimum Skor Risiko (Total 100 Poin)
        </h2>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
          <div>
            <label className="block text-slate-400 mb-1">Kontrak (30)</label>
            <input
              type="number"
              value={wContract}
              onChange={(e) => setWContract(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Holder (25)</label>
            <input
              type="number"
              value={wHolders}
              onChange={(e) => setWHolders(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Volume (20)</label>
            <input
              type="number"
              value={wVolume}
              onChange={(e) => setWVolume(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Likuiditas (15)</label>
            <input
              type="number"
              value={wLiquidity}
              onChange={(e) => setWLiquidity(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Sosial (10)</label>
            <input
              type="number"
              value={wSocial}
              onChange={(e) => setWSocial(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white"
            />
          </div>
        </div>
      </div>

      {/* 9router AI Config */}
      <div className="rounded-xl border border-indigo-800/60 bg-slate-900/60 p-5 space-y-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-300">
          3. Konfigurasi AI Provider Lokal (9router)
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block text-slate-400 mb-1">
              Base URL 9router (OpenAI-Compatible)
            </label>
            <input
              type="text"
              value={aiBaseUrl}
              onChange={(e) => setAiBaseUrl(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white font-mono"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">Nama Model AI</label>
            <input
              type="text"
              value={aiModel}
              onChange={(e) => setAiModel(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white font-mono"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-bold text-white"
        >
          <Save className="w-4 h-4" />
          <span>Simpan Pengaturan</span>
        </button>

        {saved && (
          <span className="inline-flex items-center gap-1 text-xs text-emerald-400 font-semibold">
            <Check className="w-4 h-4" />
            Pengaturan berhasil diperbarui
          </span>
        )}
      </div>
    </form>
  );
}
