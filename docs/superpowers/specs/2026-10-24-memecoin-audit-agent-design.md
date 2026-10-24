# Memecoin Audit Agent + 9router AI Analyst — Design Specification

- **Date:** 2026-10-24
- **Status:** Approved
- **Target Environment:** Local Personal Deployment (Windows / Docker Compose), Solana-first with Multi-Chain Adapter Architecture

---

## 1. Intent and Why

Retail memecoin traders face extreme noise: thousands of tokens launch daily on Solana, most of which suffer from contract traps (active mint/freeze authorities, unlocked LP), insider supply bundles, or bot-driven wash trading. Checking DexScreener, RugCheck, and holder distributions manually across tabs takes too long when tokens move in minutes.

**Memecoin Audit Agent** solves this through a **two-stage automated intelligence pipeline**:
1. **Stage 1 — Deterministic Auditor & GMGN Scout:** Continuously scans new and boosted Solana tokens, applies a cheap pre-filter, enriches with DexScreener pair data and RugCheck security reports, runs deterministic GMGN Scout heuristics (wash trade proxy, top-holder/bundle concentration, contract safety), and calculates an explainable **Risk Score (0–100, higher = riskier)** and **Verdict (`AVOID`, `HIGH RISK`, `WATCH`, `PROMISING`)**.
2. **Stage 2 — Local AI Analyst (`9router`):** Once the deterministic engine narrows the stream down to viable candidates (`PROMISING` and `WATCH`, plus any manually requested token), a local AI provider (`9router` on port `20128` using model `gemini-3.8-flash-high`) evaluates those shortlisted coins to answer the trader's core decision questions:
   - Is this coin **Healthy (`HEALTHY`)**, **Mixed (`MIXED`)**, or **Unhealthy (`UNHEALTHY`)**?
   - Is the volume driven by **Real Organic Buyers (`ORGANIC`)** or manipulated by bots (`BOT_HEAVY`) / insiders (`INSIDER_DRIVEN`)?
   - Can the liquidity pool absorb selling pressure from top holders?
   - What are the concrete **Bull Case**, **Main Risk (Red Flag)**, and **Invalidation Trigger** (when to walk away)?

The agent is strictly a read-only decision-support system, not a financial advisor or trade execution bot.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
1. **Automated 5-Stage Scanning Pipeline:** Run every 60 seconds without manual intervention (Discovery $\rightarrow$ Pre-filter $\rightarrow$ Parallel Enrichment $\rightarrow$ Deterministic GMGN Scout & Risk Scoring $\rightarrow$ Shortlist AI Analysis via `9router` $\rightarrow$ Persist & Real-time SSE/WebSocket broadcast).
2. **Periodic Re-scanning of Viable Tokens:** Re-scan `PROMISING` and `WATCH` tokens every 2–5 minutes (configurable) to track time-series trends in liquidity, volume, holder concentration, and verdict changes.
3. **On-Demand Manual Audit:** Allow auditing any Solana token mint address immediately via the web dashboard or CLI, running both the deterministic audit and `9router` AI analysis.
4. **Explainable Deterministic Risk Scoring (0–100):** Compute risk scores purely from rule-based penalties across 5 categories (Contract 30, Holders 25, Volume Integrity 20, Liquidity 15, Social/Metadata 10) with hard-stop overrides and numerical evidence on every flag.
5. **Deep Prospect & Health Analysis via Local `9router`:** Integrate with `http://localhost:20128/v1` (`gemini-3.8-flash-high`) to evaluate shortlisted coins for market health, real buyer quality, momentum phase, liquidity stress, narrative quality, decision scenarios, and comparative batch ranking.
6. **Responsive Dark-Mode Live Dashboard (Option A Layout):**
   - **Page 1 (Live Scanner):** Unified view featuring a top **"Kandidat Terbaik Hasil Bedah AI (Top Koin Sehat)"** highlight section for AI-vetted `PROMISING`/`WATCH` coins, followed by the real-time filterable/sortable scanner table and API/pipeline health bar.
   - **Page 2 (Token Detail):** Score breakdown bars, grouped GMGN Scout flags with numerical proofs, `9router` AI Decision Panel (Health verdict, Real Buyer badge, Momentum, LP Stress, Bull/Risk/Invalidation brief), price/liquidity snapshot charts, holder distribution donut chart, score timeline, and "Pindai Ulang" button.
   - **Page 3 (Watchlist & Alerts):** Pin tokens and trigger in-app (and optional Telegram) alerts on verdict change, liquidity drop $> X\%$, top holder sell-off, or authority change.
   - **Page 4 (Settings):** View and update pre-filter thresholds, category weights, scan intervals, and active chains/AI settings.

### Non-Goals
- **No Trade Execution or Wallet Management:** The system never stores private keys, connects wallets, signs transactions, or executes swaps.
- **No Scraping of Unofficial Sources:** Never scrape GMGN or any site lacking a public API.
- **No Multi-Chain Implementation in v1:** Only Solana is implemented initially, though all data fetching and contract checks sit behind a `ChainAdapter` interface so Base, BSC, and Ethereum can be added cleanly later.

### Anti-Goals (Failure Conditions Even If Code Runs)
- **LLM Overriding Deterministic Risk Scores:** `9router` must *never* alter the deterministic `risk_score` (0–100) or override a hard-stop `AVOID` verdict. Deterministic rules govern safety; AI governs qualitative synthesis and shortlist prioritization.
- **Treating Missing Data as Safe (`0`):** Missing API fields or failed enrichments must be marked `unknown`, never `0`. If $> 30\%$ of signals are `unknown`, the verdict must carry a `low` confidence badge.
- **Hallucinating Metrics:** Every number referenced in flags or AI prompts must trace to a specific API source (`dexscreener`, `rugcheck`, `solana_rpc`) and scan timestamp.
- **Imperative Financial Advice:** Never output commands like *"Beli sekarang"* or *"Jual sekarang"*; always use descriptive analytical language in Indonesian.
- **Pipeline Stalls on External Outages:** If `9router` or RugCheck is slow or offline, the scanner must degrade gracefully without crashing or blocking real-time updates.

---

## 3. Constraints & External Integrations

### 3.1 Data Sources & Rate Limits
1. **DexScreener API** (`https://api.dexscreener.com`, no API key required):
   - `GET /token-profiles/latest/v1` — 60 req/min
   - `GET /token-boosts/latest/v1` and `GET /token-boosts/top/v1` — 60 req/min
   - `GET /token-pairs/v1/{chainId}/{tokenAddress}` — 300 req/min
   - `GET /latest/dex/pairs/{chainId}/{pairId}` — 300 req/min
   - `GET /latest/dex/search?q={query}` — 300 req/min
   - **Cache TTL:** 30 seconds for pair data.
2. **RugCheck API** (`https://api.rugcheck.xyz/v1`):
   - `GET /tokens/{mint}/report` — full security report (risks, score, topHolders, graphInsidersDetected/insider graph, markets/LP lockers, mintAuthority, freezeAuthority, rugged status, creator balance).
   - Optional `X-API-KEY` header loaded from `RUGCHECK_API_KEY` env var (works without key on public endpoints, rate-limited safely at 30 req/min default).
   - **Cache TTL:** 10 minutes per token report (bypassed when user clicks manual "Pindai Ulang").
3. **Optional Solana RPC / Helius Adapter** (`HELIUS_API_KEY` or `SOLANA_RPC_URL`):
   - Active only when configured in `.env`. Enables per-wallet repeated wash-trade detection within close block intervals. When unconfigured, the `REPEATED_WALLET_WASH` signal returns `unknown` without failing the pipeline.
4. **Resilience Rules for All HTTP Clients:**
   - Asynchronous `httpx.AsyncClient` wrapped in an async token-bucket rate limiter per upstream host.
   - Exponential backoff retry (max 3 attempts, jitter) on network timeouts, 5xx errors, and HTTP 429 (respecting `Retry-After` header).
   - Strict Pydantic v2 validation where missing/null optional fields resolve to explicit `UnknownField` / `None` markers rather than zero.

### 3.2 Local AI Provider (`9router`) Integration
- **Endpoint:** OpenAI-compatible Chat Completions API at `http://localhost:20128/v1/chat/completions` (configurable via `NINEROUTER_BASE_URL`, defaulting to `http://localhost:20128/v1` locally and `http://host.docker.internal:20128/v1` inside Docker).
- **Model:** `gemini-3.8-flash-high` (configurable via `NINEROUTER_MODEL`).
- **Authentication:** Uses `Bearer ${NINEROUTER_API_KEY}` header (defaults to `"local-9router"` if no key is required).
- **Trigger Policy:**
  - Automatically invoked for tokens whose deterministic verdict is `PROMISING` or `WATCH` (when first scored, or when re-scanned if market metrics shifted significantly, e.g., $>15\%$ change in liquidity/volume or flag changes).
  - Always invoked on manual token audit requests (CLI or Dashboard) unless the token has a hard-stop `AVOID` and the user did not force AI analysis (even for manual `AVOID`, a brief AI explanation of why it failed is generated).
  - For bulk `AVOID` and `HIGH RISK` background tokens, a deterministic Indonesian summary template is generated immediately so `9router` resources remain focused on promising candidates.

---

## 4. Architecture & How It Works

### 4.1 Two-Stage Pipeline & Data Flow

```text
[DexScreener Discovery (60s)] ──► [Cheap Pre-Filter (Liq >= $5k, Age 5m-7d)]
                                          │
                                          ▼
                            [Parallel Enrichment (Bounded Semaphore)]
                             ├─► DexScreener /token-pairs
                             ├─► RugCheck /tokens/{mint}/report
                             └─► Optional Solana RPC (if key present)
                                          │
                                          ▼
                             [GMGN Scout & Deterministic Scoring]
                             ├─► Category A: Wash Trade & Bot Heuristics (0-20)
                             ├─► Category B: Holder & Bundle Concentration (0-25)
                             ├─► Category C: Contract Safety (0-30, Hard Stop)
                             ├─► Category D: Liquidity Depth & Trend (0-15)
                             └─► Category E: Social & Metadata Completeness (0-10)
                                          │
                       ┌──────────────────┴──────────────────┐
                       ▼                                     ▼
        [Verdict: AVOID / HIGH RISK]          [Verdict: PROMISING / WATCH]
        Deterministic ID Summary              Shortlisted for 9router AI
                       │                                     │
                       │                                     ▼
                       │                      [9router (gemini-3.8-flash-high)]
                       │                      • Health: HEALTHY / MIXED / UNHEALTHY
                       │                      • Buyer Quality: ORGANIC / BOT_HEAVY / INSIDER
                       │                      • Momentum & LP Dump Stress Check
                       │                      • Bull Case, Main Risk, Invalidation Trigger
                       │                      • Batch Ranking Among Active Shortlist
                       └──────────────────┬──────────────────┘
                                          ▼
                        [Persist Snapshot to DB + Check Alerts]
                                          │
                                          ▼
                        [Broadcast via SSE/WebSocket to Dashboard]
```

### 4.2 GMGN Scout Heuristics (`backend/scout/`)

All thresholds below are defaults loaded from `config/thresholds.yaml`:

1. **`wash_trade.py` (Filter Wash Trade & Bot):**
   - `VOL_LIQ_RATIO_HIGH`: `volume.h24 / liquidity.usd`. Flag `warn` if $> 50\times$, `critical` if $> 200\times$.
   - `UNIFORM_BUY_SELL_RATIO`: High transaction count ($\text{txns.h1} \ge 200$) while buy/sell ratio stays abnormally close to $1:1$ ($0.48 \le \text{buys}/\text{total} \le 0.52$) across multiple windows (`m5`, `h1`, `h6`). Flag `warn`.
   - `HIGH_TXNS_FLAT_PRICE`: High transactions ($\text{txns.m5} \ge 100$ or $\text{txns.h1} \ge 400$) with near-zero price movement ($|\text{priceChange.m5}| < 1.0\%$ or $|\text{priceChange.h1}| < 2.0\%$). Flag `warn`.
   - `SUDDEN_VOL_SPIKE_NO_LIQ`: `volume.m5 * 12 > volume.h1 * 3` while liquidity is stagnant or shrinking. Flag `warn`.
   - `REPEATED_WALLET_WASH`: (Requires Optional RPC) Same wallets buying and selling repeatedly within $\le 5$ blocks. Flag `critical` (or `unknown` if RPC disabled).

2. **`holders.py` (Bundle & Top Holder Concentration):**
   - Filters out known LP, bonding curve (e.g., Raydium, Pump.fun bonding curve, Meteora), and burn addresses from RugCheck `topHolders` and `knownAccounts`.
   - Computes `top1_pct`, `top10_pct`, and `top20_pct` of circulating supply.
   - `TOP10_CONCENTRATION`: Flag `warn` if $> 30\%$, `critical` if $> 50\%$.
   - `SINGLE_HOLDER_CONCENTRATION`: Flag `warn` if `top1_pct` $> 10\%$, `critical` if $> 15\%$.
   - `INSIDER_BUNDLE_CLUSTER`: Uses RugCheck `graphInsidersDetected` / insider networks and launch-block concentration. Flag `warn` if insider cluster holds $> 10\%$, `critical` if $> 25\%$.
   - `CREATOR_HOLDINGS_AND_SELLS`: Tracks creator balance percentage and flags `warn` if creator holds $> 5\%$ or has dumped significant supply.

3. **`contract.py` (Contract Security — Hard Stop Category):**
   - `MINT_AUTHORITY_ACTIVE`: Mint authority is not null/revoked $\rightarrow$ `critical`.
   - `FREEZE_AUTHORITY_ACTIVE`: Freeze authority is not null/revoked $\rightarrow$ `critical`.
   - `DANGEROUS_TOKEN_EXTENSION`: Mutable metadata (`warn`), Token-2022 `PermanentDelegate` (`critical`), high/mutable `TransferFeeConfig` (`warn` if $\le 5\%$, `critical` if $> 5\%$).
   - `LP_UNLOCKED_OR_SHORT`: LP unlocked/unburned $< 80\%$ (`warn`), or 100% controlled by creator without lock (`critical`).
   - `RUGCHECK_DANGER_OR_RUGGED`: Token marked `rugged: true` or carries a RugCheck `danger` risk item $\rightarrow$ `critical`.

### 4.3 Deterministic Scoring & Verdict Rules (`backend/scoring/`)

Default category caps from `config/weights.yaml` (total max 100):
- **Contract Safety:** max 30 pts
- **Holder Distribution:** max 25 pts
- **Volume Integrity:** max 20 pts
- **Liquidity:** max 15 pts (penalizes liquidity $< \$25\text{k}$, low $\text{liquidity}/\text{marketCap}$ ratio $< 5\%$, or negative liquidity delta across snapshots)
- **Social & Metadata:** max 10 pts (penalizes missing website, missing X/Telegram, or copycat symbol/name warning)

**Base Verdict Mapping:**
- `70–100` $\rightarrow$ `AVOID`
- `50–69` $\rightarrow$ `HIGH RISK`
- `30–49` $\rightarrow$ `WATCH`
- `0–29` $\rightarrow$ `PROMISING`

**Mandatory Override Rules:**
1. **Contract Hard Stop:** Any `critical` flag in Category C (`contract`) immediately forces `verdict = "AVOID"` regardless of total numerical score.
2. **Promising Gate:** `PROMISING` is only allowed if `liquidity_usd >= 25000`, zero `critical` flags exist across all categories, and RugCheck report succeeded. Otherwise, downgrade `PROMISING` $\rightarrow$ `WATCH`.
3. **Low Confidence Flag:** If $> 30\%$ of evaluated signal checks return `unknown`, set `confidence = "low"` (otherwise `"high"` if $\le 10\%$ unknown, `"medium"` if $10\text{–}30\%$ unknown).

### 4.4 `9router` AI Analyst Schema (`backend/ai/nine_router.py`)

When `9router` (`http://localhost:20128/v1`, model `gemini-3.8-flash-high`) analyzes a token, it receives the structured JSON audit report (plus up to 5 recent historical snapshots for trend context) and returns a strict JSON schema:

```json
{
  "status": "completed",
  "model": "gemini-3.8-flash-high",
  "analyzed_at": "2026-10-24T20:00:00+07:00",
  "health_status": "HEALTHY",
  "buyer_quality": "ORGANIC",
  "conviction_score": 82,
  "momentum_phase": "EARLY_ACCUMULATION",
  "liquidity_stress": {
    "rating": "STRONG",
    "lp_to_top10_ratio": 0.79,
    "note_id": "Likuiditas $68K cukup kuat menahan potensi jual dari Top 10 holder ($86K)."
  },
  "narrative_quality": "SOLID",
  "summary_id": "Ringkasan 3-5 kalimat bahasa Indonesia yang menjelaskan risiko terbesar, faktor pendukung prospek, dan metrik yang wajib dipantau.",
  "decision_brief": {
    "bull_case_id": "Kontrak bersih tanpa celah mint/freeze, distribusi Top 10 terkendali (21%), dan arus beli m5/h1 tumbuh organik.",
    "red_flag_id": "Umur pair baru 42 menit dan wallet creator masih memegang 2.4% suplai.",
    "invalidation_trigger_id": "Batalkan pantauan jika likuiditas turun di bawah $45.000 atau wallet creator mulai menjual."
  },
  "shortlist_rank_reason_id": "Kandidat paling sehat saat ini karena rasio likuiditas terhadap konsentrasi holder paling seimbang."
}
```

### 4.5 Extended Token Report JSON Format

Every token API response and exported report includes the base fields required by `Memecoin Audit Agent.md` plus the `ai_analysis` block:

```json
{
  "token": {"chain": "solana", "address": "...", "symbol": "...", "name": "..."},
  "scanned_at": "2026-10-24T20:00:00+07:00",
  "market": {
    "price_usd": 0.0041,
    "liquidity_usd": 68000,
    "market_cap": 410000,
    "fdv": 410000,
    "volume_24h": 520000,
    "volume_h1": 84000,
    "volume_m5": 12500,
    "txns_m5_buys": 94,
    "txns_m5_sells": 58,
    "txns_h1_buys": 612,
    "txns_h1_sells": 380,
    "price_change_m5": 4.2,
    "price_change_h1": 18.5,
    "pair_age_minutes": 42,
    "pair_address": "...",
    "dex_id": "raydium"
  },
  "risk_score": 18,
  "verdict": "PROMISING",
  "confidence": "high",
  "breakdown": {"contract": 0, "holders": 8, "volume_integrity": 4, "liquidity": 4, "social": 2},
  "flags": [
    {"category": "holders", "severity": "warn", "code": "CREATOR_HOLDINGS", "value": 0.024, "threshold": 0.05, "source": "rugcheck"}
  ],
  "summary_id": "Ringkasan 3-5 kalimat dalam bahasa Indonesia.",
  "ai_analysis": { ... },
  "disclaimer": "Analisis otomatis, bukan nasihat keuangan."
}
```

---

## 5. What Is Left to the Builder (and Builder Calls)

The following technical choices are settled as **Builder Calls** to keep local setup fast, reliable, and self-contained while satisfying every requirement in `Memecoin Audit Agent.md`:

1. **Database (Builder Call):** Use **SQLite (async `aiosqlite` with WAL mode enabled)** as the default zero-config database so the project runs immediately on Windows/macOS/Linux without requiring a separate database server, while using **SQLAlchemy 2.0 Async ORM** so switching `DATABASE_URL` to PostgreSQL in `docker-compose.yml` or `.env` requires zero code changes.
2. **Cache & Rate Limiter (Builder Call):** Implement a dual-mode cache and token-bucket rate limiter (`in-memory` default + optional `Redis` when `REDIS_URL` is set). This guarantees single-command local execution even without Docker/Redis running, while supporting Redis in Docker Compose.
3. **Real-Time Transport (Builder Call):** Use **Server-Sent Events (SSE)** (`GET /api/v1/stream/events`) + REST API in FastAPI for pushing `token_scored`, `verdict_changed`, `ai_analyzed`, and `alert_triggered` events to the Next.js dashboard, as SSE is unidirectional server-to-client, auto-reconnects natively in browsers, and works cleanly through proxies.
4. **Worker & API Process Sharing (Builder Call):** Support both embedded background scheduler mode (APScheduler running inside FastAPI lifespan for simple single-command dev start) and standalone worker mode (`python -m backend.pipeline.worker`) for Docker Compose production separation.
5. **Repository Structure:**
   ```text
   memecoin-audit-agent-argon/
     backend/
       adapters/       # base.py, solana.py (ChainAdapter interface)
       clients/        # dexscreener.py, rugcheck.py, solana_rpc.py, rate_limiter.py, cache.py
       scout/          # gmgn_scout.py, wash_trade.py, holders.py, contract.py
       scoring/        # rubric.py, verdict.py
       ai/             # nine_router.py, prompts.py, fallback.py
       pipeline/       # discovery.py, enrich.py, worker.py, alerts.py
       db/             # models.py, session.py, repository.py
       api/            # main.py, routes.py, sse.py, schemas.py
       cli.py          # Manual token audit & pipeline CLI
       tests/          # Unit & fixture tests (safe, suspicious, rugged tokens, AI mock)
     frontend/         # Next.js (App Router) + TypeScript + Tailwind + TanStack Table + Recharts
     config/           # thresholds.yaml, weights.yaml
     docs/superpowers/specs/
     docker-compose.yml
     .env.example
     README.md
   ```
6. **Milestone Execution Plan:**
   - **M1:** Data clients (DexScreener, RugCheck, Rate Limiter, Cache, Schemas) + CLI single-token fetch & unit tests.
   - **M2:** `gmgn_scout` module, deterministic scoring rubric, verdict overrides, and `9router` AI Analyst client + fixture unit tests.
   - **M3:** Scheduled discovery/enrichment/re-scan pipeline, SQLite/Postgres snapshot persistence, and alert evaluation engine.
   - **M4:** Next.js Live Dashboard (Page 1: Unified Live Scanner + Top AI Healthy Picks Banner; Page 2: Token Detail + AI Decision Card + Charts).
   - **M5:** Watchlist, Alerts (in-app + optional Telegram bot), and Settings page (thresholds, weights, intervals, `9router` config).
   - **M6:** Docker Compose, `.env.example`, comprehensive `README.md`, and end-to-end verification.
