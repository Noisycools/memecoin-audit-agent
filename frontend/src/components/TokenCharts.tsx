"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

const COLORS = ["#10b981", "#f59e0b", "#6366f1", "#334155"];

export function TokenCharts({
  snapshots,
  holderMetrics,
}: {
  snapshots: Array<{
    scanned_at: string;
    price_usd: number | null;
    liquidity_usd: number | null;
    risk_score: number;
  }>;
  holderMetrics: Record<string, number | null | undefined>;
}) {
  const top10 = Number(holderMetrics?.top10_pct_ex_lp ?? 0);
  const creator = Number(holderMetrics?.creator_balance_pct ?? 0);
  const lpSupply = Number(holderMetrics?.lp_supply_pct ?? 0);
  const lpLocked = Number(holderMetrics?.lp_locked_pct ?? 0);
  const others = Math.max(0, 100 - lpSupply - top10 - creator);

  const pieData = [
    { name: "LP Pool", value: Number(lpSupply.toFixed(1)) },
    { name: "Top 10 (Non-LP)", value: Number(top10.toFixed(1)) },
    { name: "Creator", value: Number(creator.toFixed(1)) },
    { name: "Holder Lainnya", value: Number(others.toFixed(1)) },
  ];

  const chartSnapshots = snapshots.map((s) => ({
    time: new Date(s.scanned_at).toLocaleTimeString("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
    }),
    price_usd: s.price_usd ?? 0,
    liquidity: s.liquidity_usd ?? 0,
    risk_score: s.risk_score,
  }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
          Linimasa Harga (USD), Likuiditas ($), &amp; Skor Risiko
        </h3>
        <div className="h-60">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartSnapshots}>
              <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
              <YAxis yAxisId="left" stroke="#38bdf8" fontSize={11} />
              <YAxis
                yAxisId="right"
                orientation="right"
                domain={[0, 100]}
                stroke="#f59e0b"
                fontSize={11}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#1e293b",
                  fontSize: "12px",
                }}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="liquidity"
                name="Likuiditas ($)"
                stroke="#38bdf8"
                strokeWidth={2}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="price_usd"
                name="Harga (USD)"
                stroke="#10b981"
                strokeWidth={2}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="risk_score"
                name="Skor Risiko"
                stroke="#f59e0b"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Distribusi Suplai Holder (Non-LP)
          </h3>
          <span className="text-xs text-slate-400">
            LP Terkunci: {lpLocked ? `${lpLocked.toFixed(1)}%` : "unknown"}
          </span>
        </div>
        <div className="h-60">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                innerRadius={55}
                outerRadius={80}
                paddingAngle={3}
              >
                {pieData.map((_entry, index) => (
                  <Cell key={index} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#1e293b",
                  fontSize: "12px",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
