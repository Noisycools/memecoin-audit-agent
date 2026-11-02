# Memecoin Audit Agent

> **Automated Solana Memecoin Technical Auditor, Deterministic Risk Scorer, and Local LLM Market Health Analyst.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Memecoin Audit Agent is an automated end-to-end scanning, contract auditing, and market viability evaluation system for Solana tokens. It operates a two-tier evaluation pipeline:

1. **Tier 1 — Deterministic Auditor & GMGN Scout**: Periodically scans newly created and boosted tokens from DexScreener, enriches them with on-chain contract security and holder distribution data from RugCheck, and executes heuristic GMGN-style manipulation checks (wash trading, uniform buy/sell bot ratios, top-holder bundling, LP locking). Outputs a deterministic **Risk Score (0–100)** and categorical verdict (`AVOID`, `HIGH RISK`, `WATCH`, or `PROMISING`).
2. **Tier 2 — Market Health & AI Analysis via Local LLM (`9router`)**: For tokens qualifying as `PROMISING` or `WATCH` (or triggered on demand), the system queries a local OpenAI-compatible endpoint (`9router` running `gemini-3.8-flash-high`) to evaluate market structure: **Health Status** (`HEALTHY`, `MIXED`, `UNHEALTHY`), **Buyer Quality** (`ORGANIC`, `BOT_HEAVY`, `INSIDER_DRIVEN`), liquidity stress resistance against Top 10 dump scenarios, and structured decision briefs (*Bull Case*, *Red Flags*, and *Invalidation Triggers*).

---

## Architecture & Data Flow

```mermaid
flowchart TD
    subgraph Ingestion["1. Data Ingestion & Prefilter"]
        DEX[DexScreener API\nLatest Profiles & Boosts] --> PRE[Prefilter Gate\nLiq >= $5k, Age 5m-7d]
        RUG[RugCheck API\nContract Security & Top Holders] --> ADAPT[Solana Chain Adapter]
        RPC[Optional Solana RPC / Helius\nPer-Wallet Block Clustering] -.-> ADAPT
    end

    subgraph Tier1["2. Deterministic Engine & GMGN Scout"]
        PRE --> SCOUT[GMGN Scout Module\nWash Trade & Bundle Heuristics]
        ADAPT --> SCOUT
        SCOUT --> RUBRIC[Scoring Rubric\nContract: 30% | Holders: 25%\nVolume: 20% | Liq: 15% | Social: 10%]
        RUBRIC --> VERDICT{Verdict Engine}
        VERDICT -->|Critical Flag or Score >= 70| V_AVOID[AVOID]
        VERDICT -->|Score 50 - 69| V_HIGH[HIGH RISK]
        VERDICT -->|Score 30 - 49| V_WATCH[WATCH]
        VERDICT -->|Score < 30 & Liq >= $25k & Clean| V_PROM[PROMISING]
    end

    subgraph Tier2["3. Local LLM Analysis (9router)"]
        V_WATCH --> AI[9router / Local LLM\nModel: gemini-3.8-flash-high]
        V_PROM --> AI
        AI --> DECISION[AI Decision Panel\nBuyer Quality, Health Status, Liquidity Stress,\nBull Case, Red Flags, Invalidation Trigger]
        AI -.->|If LLM Unavailable| FALLBACK[Deterministic Fallback Engine]
    end

    subgraph StorageStream["4. Persistence & Presentation"]
        VERDICT --> DB[(SQLite / PostgreSQL\nWAL Mode)]
        DECISION --> DB
        DB --> SSE[Server-Sent Events / SSE Stream]
        SSE --> UI[Next.js 14 Dashboard\nLive Table, Top Picks, Watchlist, Charts]
        DB --> TG[Optional Telegram Alert Bot]
        CLI[Backend CLI\nfetch / audit commands] -.-> ADAPT
    end
```

---

## Core Features

- **Continuous Background Discovery**: Scans DexScreener every 60 seconds (configurable) for new token profiles and paid boosts.
- **Cheap Prefilter Stage**: Filters out dead pairs, low-liquidity spam (< $5,000 default), and out-of-scope pair ages before querying RugCheck.
- **GMGN Scout Heuristics**:
  - *Abnormal Volume*: Detects 24h volume-to-liquidity ratios exceeding 50x (`warn`) or 200x (`critical`).
  - *Symmetric Bot Churn*: Flags high transaction volumes with near-exact 50/50 buy/sell ratios across multiple timeframes.
  - *Flat-Price High-Frequency Churn*: Identifies high transaction frequency without corresponding price movement.
  - *Holder Concentration & Insider Bundles*: Analyzes Top 1, Top 10, and Top 20 supply allocations excluding LP, bonding curve, and burn addresses; flags creator holding thresholds.
  - *Contract Safety Rules*: Flags active mint authority, freeze authority, transfer fees, unburned/unlocked LP, and blacklist mechanisms. Contract critical flags trigger an immediate `AVOID` hard-stop.
- **Local AI Analysis (`9router`)**:
  - Evaluates buyer quality (`ORGANIC`, `BOT_HEAVY`, `INSIDER_DRIVEN`).
  - Computes conviction score (0–100) and market momentum phase.
  - Calculates liquidity stress: LP-to-Top-10 supply ratio and absorption capacity.
  - Generates actionable decision briefs with explicit invalidation conditions.
  - Automatic deterministic fallback if local LLM service is offline.
- **Real-Time Web Dashboard**:
  - Top AI Picks banner dynamically ranking the most promising audited tokens.
  - Filterable live table with Server-Sent Events (SSE) updates.
  - Deep-dive token detail page with TradingView-style price/volume metrics and risk breakdown.
  - Dedicated Watchlist with user-defined threshold triggers (liquidity drop, verdict changes, top holder sells).
  - Runtime settings panel to adjust scoring weights and prefilter thresholds without restarting services.
- **On-Demand Audits**: Manual token audit triggers available directly from the Web UI or via the CLI.

---

## Quick Start

### Option 1: Docker Compose (Recommended)

Run backend and frontend containers with a single command:

```bash
# 1. Clone repository and enter project directory
git clone https://github.com/your-username/memecoin-audit-agent.git
cd memecoin-audit-agent

# 2. Configure environment
cp .env.example .env

# 3. Start services
docker compose up --build
```

- **Frontend Dashboard**: `http://localhost:3003`
- **Backend API & Swagger Docs**: `http://localhost:8004/docs`

> **Note on Local AI (`9router`)**: Inside Docker, `NINEROUTER_BASE_URL` defaults to `http://host.docker.internal:20128/v1` to communicate with the host's `9router` instance. Ensure `9router` is running on your host machine.

---

### Option 2: Local Development Setup

#### Prerequisites
- **Python**: `>= 3.11`
- **Node.js**: `>= 18.0.0` and `npm`
- **9router** (optional for Tier 2 AI): Running on `http://localhost:20128` with `gemini-3.8-flash-high`

#### 1. Backend Setup

```bash
# Setup Python virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Install backend in editable mode with development dependencies
python -m pip install --upgrade pip
python -m pip install --no-build-isolation -e "backend[dev]"

# Copy environment configuration
cp .env.example .env

# Run FastAPI backend with the background scanner worker (Port 8004)
python -m backend
```

Alternatively, run with Uvicorn directly:
```bash
python -m uvicorn backend.api.main:create_app --factory --host 0.0.0.0 --port 8004 --reload
```

#### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3003` in your browser.

#### 3. CLI Audit Tool

The backend provides CLI commands for manual inspection and on-demand audits:

```bash
# Fetch raw enriched data from DexScreener and RugCheck
python -m backend.cli fetch <SOLANA_MINT_ADDRESS>

# Execute full audit: deterministic scoring + 9router AI evaluation
python -m backend.cli audit <SOLANA_MINT_ADDRESS>
```

#### 4. Running Tests

```bash
# Run backend test suite (unit, scoring, scout, API endpoints, AI client)
python -m pytest
```

---

## Environment Variables (`.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `BACKEND_HOST` | `0.0.0.0` | Host interface for FastAPI server |
| `BACKEND_PORT` | `8004` | Port for FastAPI backend |
| `FRONTEND_PORT` | `3003` | Port for Next.js frontend |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8004` | Backend API base URL accessible from browser |
| `DATABASE_URL` | `sqlite+aiosqlite:///./memecoin_audit.db` | Database connection string (SQLite WAL or PostgreSQL) |
| `REDIS_URL` | *(empty)* | Optional Redis URL for shared caching |
| `NINEROUTER_BASE_URL` | `http://localhost:20128/v1` | OpenAI-compatible endpoint for local `9router` |
| `NINEROUTER_MODEL` | `gemini-3.8-flash-high` | Target LLM model name served by `9router` |
| `NINEROUTER_API_KEY` | `local-9router` | API key for local LLM proxy |
| `RUGCHECK_API_KEY` | *(empty)* | Optional API key for RugCheck `X-API-KEY` header |
| `HELIUS_API_KEY` | *(empty)* | Optional API key for Helius Solana RPC |
| `SOLANA_RPC_URL` | *(empty)* | Optional custom Solana RPC endpoint for per-wallet wash trade analysis |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Optional Telegram Bot token for push notifications |
| `TELEGRAM_CHAT_ID` | *(empty)* | Target chat or channel ID for Telegram alerts |

---

## Scoring Rubric & Verdict Rules

The deterministic risk engine computes a raw **Risk Score (0–100)** across five weighted categories defined in `config/weights.yaml`:

| Category | Weight | Evaluated Signals |
| :--- | :---: | :--- |
| **Contract** | 30% | Mint authority, freeze authority, transfer fees, LP lock/burn status, blacklist code. |
| **Holders** | 25% | Top 1, Top 10, Top 20 concentration (excl. LP/burn), creator wallet balance, insider clustering. |
| **Volume Integrity** | 20% | Volume-to-liquidity ratio, buy/sell symmetry churn, zero-price-change transaction spikes. |
| **Liquidity** | 15% | Absolute liquidity depth, FDV/liquidity ratio, liquidity stability over time. |
| **Social** | 10% | Profile completeness, verified websites, Telegram, Twitter/X links. |

### Verdict Thresholds & Overrides

```
Risk Score:
  0 ------------ 29 ------------ 49 ------------ 69 ------------ 100
    [ PROMISING ]     [  WATCH  ]    [ HIGH RISK ]     [  AVOID  ]
```

- **`AVOID` (Score ≥ 70)**: High technical risk or unviable market metrics.
  - **Hard-Stop Override**: Any `critical` flag in the **Contract** category (e.g. active mint authority, active freeze authority, transfer fee exploit) triggers an immediate **`AVOID`** verdict regardless of the composite score.
- **`HIGH RISK` (Score 50–69)**: Dangerous holder concentration, suspicious volume patterns, or weak liquidity depth.
- **`WATCH` (Score 30–49)**: Acceptable baseline parameters, but requires ongoing monitoring.
- **`PROMISING` (Score < 30)**: Clean security profile and healthy liquidity.
  - **Qualification Rule**: Must satisfy three conditions:
    1. Composite score < 30.
    2. Liquidity $\ge \$25,000$ (configurable via `verdict_rules.promising_min_liquidity_usd`).
    3. Zero `critical` severity flags across all categories.
    4. Successful RugCheck report available.
    *Tokens failing any of these conditions are adjusted to `WATCH`.*

---

## REST & Streaming API Reference

All REST endpoints are prefixed with `/api/v1`. Interactive Swagger documentation is available at `http://localhost:8004/docs`.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | System health, worker timestamps, rate limiter token counts, and AI connectivity status. |
| `GET` | `/api/v1/tokens` | Query audited tokens with filters (`verdict`, `chain`, `min_liquidity_usd`, `min_age_minutes`, `max_age_minutes`, `hide_critical`, `limit`). Returns token list and top AI picks. |
| `GET` | `/api/v1/tokens/{chain}/{address}` | Full audit details, breakdown scores, flags, and AI report for a specific mint. |
| `POST` | `/api/v1/tokens/audit` | Request an immediate manual audit for a token address (`{"chain": "solana", "address": "..."}`). |
| `POST` | `/api/v1/pipeline/scan-now` | Trigger an immediate discovery and enrichment scan cycle. |
| `GET` | `/api/v1/watchlist` | Retrieve all tokens currently saved in the watchlist. |
| `POST` | `/api/v1/watchlist` | Add a token to the watchlist with custom alert parameters. |
| `DELETE` | `/api/v1/watchlist/{chain}/{address}` | Remove a token from the watchlist. |
| `GET` | `/api/v1/alerts` | Query historical audit alerts and status change notifications. |
| `GET` | `/api/v1/settings` | Retrieve active thresholds, scoring weights, and AI provider configuration. |
| `PUT` | `/api/v1/settings` | Dynamically update thresholds, scoring weights, and AI config in memory. |
| `GET` | `/api/v1/stream/events` | Server-Sent Events (SSE) stream broadcasting token updates and alerts in real time. |

---

## Sample JSON Audit Report

Below is an example payload returned by `GET /api/v1/tokens/{chain}/{address}`:

```json
{
  "token": {
    "chain": "solana",
    "address": "So11111111111111111111111111111111111111112",
    "symbol": "BONKAI",
    "name": "Bonk Agent",
    "logo_url": "https://cdn.dexscreener.com/token-logos/solana/So11111111111111111111111111111111111111112.png"
  },
  "scanned_at": "2026-10-24T20:00:00+00:00",
  "market": {
    "price_usd": 0.0041,
    "liquidity_usd": 68000.0,
    "market_cap": 410000.0,
    "fdv": 410000.0,
    "volume_24h": 520000.0,
    "pair_age_minutes": 42,
    "dex_id": "raydium"
  },
  "risk_score": 18,
  "verdict": "PROMISING",
  "verdict_changed": false,
  "confidence": "high",
  "breakdown": {
    "contract": 0,
    "holders": 8,
    "volume_integrity": 4,
    "liquidity": 4,
    "social": 2
  },
  "flags": [
    {
      "category": "holders",
      "severity": "warn",
      "code": "CREATOR_HOLDINGS_HIGH",
      "value": 0.024,
      "threshold": 0.05,
      "source": "rugcheck",
      "detail_id": "Creator holds 2.4% of total supply."
    }
  ],
  "summary_id": "Clean contract with revoked authorities and locked LP. Healthy holder distribution with predominantly organic buyers. Watch creator wallet holding 2.4% of supply.",
  "ai_analysis": {
    "status": "completed",
    "model": "gemini-3.8-flash-high",
    "health_status": "HEALTHY",
    "buyer_quality": "ORGANIC",
    "conviction_score": 84,
    "momentum_phase": "EARLY_ACCUMULATION",
    "liquidity_stress": {
      "rating": "STRONG",
      "lp_to_top10_ratio": 0.79,
      "note_id": "$68k liquidity pool can adequately absorb Top 10 holder selling pressure."
    },
    "narrative_quality": "SOLID",
    "summary_id": "Token exhibits organic market structure with clean contract boundaries and active liquidity depth.",
    "decision_brief": {
      "bull_case_id": "Revoked authorities, high liquidity ratio, and 62% organic buyer dominance.",
      "red_flag_id": "Pair age is under 1 hour (42 minutes).",
      "invalidation_trigger_id": "Invalidate thesis if pool liquidity drops below $45,000 or creator wallet transfers tokens."
    },
    "shortlist_rank_reason_id": "High liquidity thickness paired with low bot footprint."
  },
  "disclaimer": "Automated technical analysis; not financial advice."
}
```

---

## Extending Multi-Chain Support

Market data retrieval and contract auditing are abstracted via the `ChainAdapter` interface located in `backend/adapters/base.py`:

```python
class ChainAdapter(ABC):
    @property
    @abstractmethod
    def chain_name(self) -> str:
        """Normalized chain identifier (e.g., 'solana', 'base', 'bsc')."""
        ...

    @abstractmethod
    async def discover_tokens(self, limit: int = 30) -> list[DiscoveredToken]:
        """Fetch candidate tokens from dex profiles, boosts, or search feeds."""
        ...

    @abstractmethod
    async def enrich_token(self, address: str, force_refresh: bool = False) -> EnrichedTokenData | None:
        """Fetch pair market metrics and security audit report."""
        ...
```

### Steps to Add a New Chain (e.g., Base or BSC):
1. **Create Adapter**: Create `backend/adapters/base_chain.py` inheriting from `ChainAdapter`.
2. **Implement Methods**: Implement `discover_tokens` (using DexScreener `chainId="base"`) and `enrich_token` (using DexScreener pairs and an EVM contract audit provider like GoPlus or Honeypot.is).
3. **Register Adapter**: Add the adapter to the scanner worker registry in `backend/pipeline/worker.py`.
4. **Update Configuration**: Add the chain identifier to `active_chains` in `config/thresholds.yaml`.

---

## Limitations & Disclaimer

- **Wash-Trading Heuristics are Proxies**: DexScreener volume and transaction counts are aggregate indicators, not per-wallet transaction graphs. Granular per-wallet clustering requires an active Solana RPC (e.g. Helius) connection.
- **Point-in-Time Assessment**: Risk scores and AI evaluations reflect token metrics at the exact instant of scanning. Memecoins are subject to extreme volatility and sudden liquidity removals.
- **Audit Scores Do Not Guarantee Safety**: A `PROMISING` or `HEALTHY` verdict does not eliminate rug pull risk. Malicious actors may employ off-chain wallet coordination, social engineering, or unannounced sell-offs.
- **Not Financial Advice**: Memecoin Audit Agent is an open-source, read-only analytics tool designed to assist technical due diligence. It does not execute trades or provide financial advice. Trading memecoins carries a significant risk of total capital loss.