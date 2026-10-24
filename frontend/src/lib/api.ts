import { SystemHealth, TokenAuditReport, TokenDetailView } from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function fetchTokens(params?: {
  verdict?: string;
  chain?: string;
  min_liquidity_usd?: number;
  min_age_minutes?: number;
  max_age_minutes?: number;
  hide_critical?: boolean;
}): Promise<{ items: TokenAuditReport[]; top_ai_picks: TokenAuditReport[]; total: number }> {
  const search = new URLSearchParams();
  if (params?.verdict) search.set("verdict", params.verdict);
  if (params?.chain) search.set("chain", params.chain);
  if (params?.min_liquidity_usd !== undefined)
    search.set("min_liquidity_usd", String(params.min_liquidity_usd));
  if (params?.min_age_minutes !== undefined)
    search.set("min_age_minutes", String(params.min_age_minutes));
  if (params?.max_age_minutes !== undefined)
    search.set("max_age_minutes", String(params.max_age_minutes));
  if (params?.hide_critical) search.set("hide_critical", "true");

  const res = await fetch(`${API_BASE_URL}/api/v1/tokens?${search.toString()}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Gagal mengambil daftar token");
  return res.json();
}

export async function fetchSystemHealth(): Promise<SystemHealth> {
  const res = await fetch(`${API_BASE_URL}/api/v1/health`, { cache: "no-store" });
  if (!res.ok) throw new Error("Gagal mengambil status sistem");
  return res.json();
}

export async function fetchTokenDetail(
  chain: string,
  address: string
): Promise<TokenDetailView> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/tokens/${encodeURIComponent(chain)}/${encodeURIComponent(address)}`,
    { cache: "no-store" }
  );
  if (!res.ok) throw new Error("Gagal mengambil detail token");
  return res.json();
}

export async function triggerManualAudit(
  address: string,
  chain = "solana"
): Promise<TokenAuditReport> {
  const res = await fetch(`${API_BASE_URL}/api/v1/tokens/audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chain, address }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Gagal melakukan audit manual");
  }
  return res.json();
}

export async function triggerScanNow(): Promise<{
  scanned_count: number;
  items: TokenAuditReport[];
}> {
  const res = await fetch(`${API_BASE_URL}/api/v1/pipeline/scan-now`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Gagal menjalankan pemindaian");
  return res.json();
}
