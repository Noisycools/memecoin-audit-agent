"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ColumnDef,
  SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, ExternalLink } from "lucide-react";
import { TokenAuditReport } from "@/lib/types";

function formatUsd(val: number | null | undefined): string {
  if (val === null || val === undefined) return "unknown";
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  return `$${val.toFixed(2)}`;
}

function formatAge(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "unknown";
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h < 24) return `${h}j ${m}m`;
  const d = Math.floor(h / 24);
  return `${d}h ${h % 24}j`;
}

export function LiveScannerTable({
  data,
  highlightedAddresses,
}: {
  data: TokenAuditReport[];
  highlightedAddresses: Set<string>;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo<ColumnDef<TokenAuditReport>[]>(
    () => [
      {
        id: "symbol",
        header: "Token",
        accessorFn: (row) => row.token.symbol,
        cell: ({ row }) => {
          const t = row.original.token;
          return (
            <Link
              href={`/tokens/${t.chain}/${t.address}`}
              className="flex items-center gap-2.5 group"
            >
              {t.logo_url ? (
                <img
                  src={t.logo_url}
                  alt={t.symbol}
                  className="w-7 h-7 rounded-full bg-slate-800 object-cover"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-indigo-950 border border-indigo-700/50 flex items-center justify-center text-xs font-bold text-indigo-300">
                  {t.symbol.slice(0, 2)}
                </div>
              )}
              <div>
                <div className="font-bold text-slate-100 group-hover:text-indigo-400 transition flex items-center gap-1">
                  <span>${t.symbol}</span>
                  <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100" />
                </div>
                <div className="text-[11px] text-slate-400 truncate max-w-[140px]">
                  {t.name} · <span className="uppercase">{t.chain}</span>
                </div>
              </div>
            </Link>
          );
        },
      },
      {
        id: "age",
        header: "Umur Pair",
        accessorFn: (row) => row.market.pair_age_minutes ?? -1,
        cell: ({ row }) => (
          <span className="text-xs text-slate-300">
            {formatAge(row.original.market.pair_age_minutes)}
          </span>
        ),
      },
      {
        id: "price",
        header: "Harga USD",
        accessorFn: (row) => row.market.price_usd ?? 0,
        cell: ({ row }) => {
          const p = row.original.market.price_usd;
          return (
            <span className="text-xs font-mono text-slate-200">
              {p !== null && p !== undefined
                ? p < 0.01
                  ? `$${p.toFixed(6)}`
                  : `$${p.toFixed(4)}`
                : "unknown"}
            </span>
          );
        },
      },
      {
        id: "liquidity",
        header: "Likuiditas",
        accessorFn: (row) => row.market.liquidity_usd ?? 0,
        cell: ({ row }) => (
          <span className="text-xs font-medium text-slate-200">
            {formatUsd(row.original.market.liquidity_usd)}
          </span>
        ),
      },
      {
        id: "market_cap",
        header: "Market Cap",
        accessorFn: (row) => row.market.market_cap ?? 0,
        cell: ({ row }) => (
          <span className="text-xs text-slate-300">
            {formatUsd(row.original.market.market_cap)}
          </span>
        ),
      },
      {
        id: "volume_24h",
        header: "Volume 24J",
        accessorFn: (row) => row.market.volume_24h ?? 0,
        cell: ({ row }) => (
          <span className="text-xs text-slate-300">
            {formatUsd(row.original.market.volume_24h)}
          </span>
        ),
      },
      {
        id: "risk_score",
        header: "Skor Risiko",
        accessorFn: (row) => row.risk_score,
        cell: ({ row }) => {
          const s = row.original.risk_score;
          const color =
            s < 30
              ? "text-emerald-400"
              : s < 50
              ? "text-amber-400"
              : s < 70
              ? "text-orange-400"
              : "text-rose-400";
          return (
            <span className={`text-xs font-bold ${color}`}>{s}/100</span>
          );
        },
      },
      {
        id: "verdict",
        header: "Verdict",
        accessorFn: (row) => row.verdict,
        cell: ({ row }) => {
          const v = row.original.verdict;
          const conf = row.original.confidence;
          const badgeStyle =
            v === "PROMISING"
              ? "bg-emerald-950 text-emerald-300 border-emerald-700/60"
              : v === "WATCH"
              ? "bg-amber-950 text-amber-300 border-amber-700/60"
              : v === "HIGH RISK"
              ? "bg-orange-950 text-orange-300 border-orange-700/60"
              : "bg-rose-950 text-rose-300 border-rose-700/60";
          return (
            <div className="flex items-center gap-1.5">
              <span
                className={`px-2 py-0.5 rounded text-[11px] font-bold border ${badgeStyle}`}
              >
                {v}
              </span>
              {row.original.verdict_changed && row.original.previous_verdict && (
                <span className="px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-700/60 text-[10px]">
                  dari {row.original.previous_verdict}
                </span>
              )}
              {conf === "low" && (
                <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">
                  Confidence Rendah
                </span>
              )}
            </div>
          );
        },
      },
      {
        id: "ai_health",
        header: "Kesehatan AI (9router)",
        accessorFn: (row) => row.ai_analysis?.health_status ?? "UNKNOWN",
        cell: ({ row }) => {
          const ai = row.original.ai_analysis;
          if (!ai || ai.status === "skipped") {
            return (
              <span className="text-xs text-slate-500">
                Dilewati ({row.original.flags.length} flag)
              </span>
            );
          }
          const h = ai.health_status;
          const b = ai.buyer_quality;
          return (
            <div className="text-xs">
              <span
                className={`font-semibold ${
                  h === "HEALTHY"
                    ? "text-emerald-400"
                    : h === "MIXED"
                    ? "text-amber-400"
                    : "text-rose-400"
                }`}
              >
                ● {h === "HEALTHY" ? "SEHAT" : h === "MIXED" ? "MERAGUKAN" : "TIDAK SEHAT"}
              </span>
              <span className="text-slate-400 ml-1">
                ({b === "ORGANIC" ? "Real Buyer" : b})
              </span>
            </div>
          );
        },
      },
      {
        id: "flags",
        header: "Flag",
        accessorFn: (row) => row.flags.length,
        cell: ({ row }) => {
          const crit = row.original.flags.filter(
            (f) => f.severity === "critical"
          ).length;
          const warn = row.original.flags.filter(
            (f) => f.severity === "warn"
          ).length;
          return (
            <div className="flex items-center gap-1 text-[11px]">
              {crit > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800">
                  {crit} Crit
                </span>
              )}
              {warn > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                  {warn} Warn
                </span>
              )}
              {crit === 0 && warn === 0 && (
                <span className="text-emerald-400">Bersih</span>
              )}
            </div>
          );
        },
      },
    ],
    []
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr
                key={hg.id}
                className="border-b border-slate-800 bg-slate-950/70 text-[11px] font-semibold uppercase tracking-wider text-slate-400"
              >
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    className="py-3 px-3.5 cursor-pointer select-none hover:text-slate-200"
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      <ArrowUpDown className="w-3 h-3 opacity-60" />
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-slate-800/70 text-sm">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="py-10 text-center text-slate-400 text-sm"
                >
                  Belum ada data token yang cocok dengan filter saat ini.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => {
                const isHighlighted = highlightedAddresses.has(
                  row.original.token.address
                );
                return (
                  <tr
                    key={row.id}
                    className={`hover:bg-slate-800/50 transition ${
                      isHighlighted ? "animate-row-flash" : ""
                    }`}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="py-3 px-3.5 whitespace-nowrap">
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
