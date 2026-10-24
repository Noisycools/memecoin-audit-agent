# Memecoin Audit Agent + 9router AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated Solana memecoin audit agent and live dark-mode dashboard that filters tokens deterministically (DexScreener + RugCheck + GMGN Scout) and uses a local `9router` AI provider (`localhost:20128`, model `gemini-3.8-flash-high`) to evaluate shortlisted coins (`PROMISING`/`WATCH`) for market health, real buyer quality, and decision scenarios.

**Architecture:** A two-stage Python 3.11+ FastAPI & async worker backend paired with a Next.js (App Router) + TypeScript + Tailwind frontend. Stage 1 runs a 60-second discovery/pre-filter/enrichment pipeline and deterministic GMGN Scout scoring engine (0–100 Risk Score + `AVOID`/`HIGH RISK`/`WATCH`/`PROMISING` verdict). Stage 2 sends shortlisted `PROMISING` and `WATCH` tokens (plus manual audits) to `9router` (`gemini-3.8-flash-high` on port `20128`) for health/buyer-quality diagnosis and broadcasts real-time updates via Server-Sent Events (SSE).

**Tech Stack:** Python 3.11+, FastAPI, `httpx`, Pydantic v2, SQLAlchemy 2.0 Async + `aiosqlite` (SQLite WAL default, Postgres-ready), APScheduler, PyYAML, `pytest` + `pytest-asyncio`, Next.js 14+ (App Router), TypeScript, Tailwind CSS, TanStack Table, Recharts, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-24-memecoin-audit-agent-design.md` (and base requirements in `Memecoin Audit Agent.md`)

## Global Constraints

- **Python & Node Floors:** Python 3.11+, Node.js 20+, TypeScript 5+.
- **Deterministic Integrity:** Risk score (`0-100`, higher = riskier) and base/override verdicts (`AVOID`, `HIGH RISK`, `WATCH`, `PROMISING`) are computed strictly from deterministic rules; `9router` never alters `risk_score` or overrides a contract hard-stop `AVOID`.
- **Unknown Handling:** Missing API fields or failed upstream requests must resolve to `None` / `"unknown"`, never `0`. If `> 30%` of evaluated signals are `"unknown"`, set `confidence = "low"`.
- **Rate Limits & Cache TTLs:** DexScreener (`https://api.dexscreener.com`): 60 req/min for profiles/boosts, 300 req/min for pairs/search, 30s cache TTL. RugCheck (`https://api.rugcheck.xyz/v1`): 30 req/min default, optional `X-API-KEY` from `RUGCHECK_API_KEY`, 600s (10 min) cache TTL.
- **Local AI Provider (`9router`):** Default base URL `http://localhost:20128/v1`, default model `gemini-3.8-flash-high`, configured via `NINEROUTER_BASE_URL`, `NINEROUTER_MODEL`, and `NINEROUTER_API_KEY`.
- **Language & Copy Rules:** Code identifiers, DB columns, JSON keys, and flag codes use English. User-facing summaries (`summary_id`, `decision_brief`), UI labels, and disclaimers use concise descriptive Indonesian (no imperative buy/sell commands). Mandatory disclaimer: `"Analisis otomatis, bukan nasihat keuangan."`
- **Read-Only Blockchain Boundary:** Never store private keys, sign transactions, or scrape GMGN.

## Review Focus

1. **Multi-pair & null-field DexScreener responses:** When `/token-pairs/v1/solana/{mint}` returns multiple pools (including dead/illiquid pools or null `liquidity.usd` / `pairCreatedAt`), the client selects the pair with the highest `liquidity.usd` and maps missing metrics to `None` instead of `0` or raising `TypeError` (pinned in Task 2).
2. **LP vault and bonding-curve exclusion in holder concentration:** RugCheck `topHolders` often lists the Raydium AMM vault, Pump.fun bonding curve, or burn address holding `>40%` supply; `holders.py` must exclude addresses present in `knownAccounts` (with LP/AMM/LOCKER/BURN types) or matching the pair address before calculating `top1_pct` and `top10_pct` (pinned in Task 4).
3. **Zero-denominator division in wash-trade heuristics:** Tokens with `liquidity_usd == 0` or `txns == 0` in `m5`/`h1` must not trigger `ZeroDivisionError` in `wash_trade.py`; affected checks must emit `"unknown"` and increment the unknown signal counter (pinned in Task 4).
4. **Markdown-fenced or timed-out `9router` responses:** Local LLMs through `9router` may wrap JSON in ```` ```json ... ``` ```` fences or time out under load; `NineRouterClient.analyze_token` must strip code fences before Pydantic validation and return `build_deterministic_fallback_analysis(report)` with `status="unavailable"` on timeout/HTTP error without failing the pipeline (pinned in Task 6).
5. **Re-scan state transition & alert deduplication:** When a watched token is re-scanned and its verdict degrades (e.g., `PROMISING` $\rightarrow$ `AVOID`) or liquidity drops `> X%`, the pipeline must compare against the previous snapshot, fire `verdict_changed` / `alert_triggered` events once per transition, and persist the alert (pinned in Task 7).

---

### Task 1: Project Scaffolding, Config Loader, and Core Domain Schemas

**Files:**
- Create: `config/thresholds.yaml`
- Create: `config/weights.yaml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `backend/pyproject.toml`
- Create: `backend/config.py`
- Create: `backend/schemas/token_report.py`
- Test: `backend/tests/test_config_and_schemas.py`

**Interfaces:**
- Consumes: `config/thresholds.yaml`, `config/weights.yaml`, environment variables
- Produces:
  - `backend.config.AppConfig`, `load_config(thresholds_path: Path | None = None, weights_path: Path | None = None) -> AppConfig`
  - `backend.schemas.token_report`: `TokenIdentity`, `MarketMetrics`, `ScoutFlag`, `ScoreBreakdown`, `LiquidityStress`, `DecisionBrief`, `AIAnalysisResult`, `TokenAuditReport`

- [ ] **Step 1: Write the failing test in `backend/tests/test_config_and_schemas.py`**

```python
from pathlib import Path
from backend.config import load_config
from backend.schemas.token_report import TokenAuditReport, ScoutFlag

def test_load_config_reads_default_thresholds_and_weights():
    cfg = load_config()
    assert cfg.thresholds.prefilter.min_liquidity_usd == 5000.0
    assert cfg.thresholds.prefilter.min_pair_age_minutes == 5
    assert cfg.thresholds.prefilter.max_pair_age_minutes == 10080
    assert cfg.weights.contract == 30
    assert cfg.weights.holders == 25
    assert cfg.weights.volume_integrity == 20
    assert cfg.weights.liquidity == 15
    assert cfg.weights.social == 10
    assert cfg.ai.base_url == "http://localhost:20128/v1"
    assert cfg.ai.model == "gemini-3.8-flash-high"

def test_token_audit_report_preserves_unknown_as_none_and_serializes_spec_format():
    report = TokenAuditReport(
        token={"chain": "solana", "address": "So11111111111111111111111111111111111111112", "symbol": "BONKAI", "name": "Bonk Agent"},
        scanned_at="2026-10-24T20:00:00+07:00",
        market={"price_usd": 0.0041, "liquidity_usd": 68000.0, "market_cap": None, "volume_24h": 520000.0, "pair_age_minutes": 42},
        risk_score=18,
        verdict="PROMISING",
        confidence="high",
        breakdown={"contract": 0, "holders": 8, "volume_integrity": 4, "liquidity": 4, "social": 2},
        flags=[ScoutFlag(category="holders", severity="warn", code="TOP10_CONCENTRATION", value=0.32, threshold=0.30, source="rugcheck")],
        summary_id="Kontrak aman dan likuiditas kuat.",
    )
    payload = report.model_dump(mode="json")
    assert payload["market"]["market_cap"] is None
    assert payload["disclaimer"] == "Analisis otomatis, bukan nasihat keuangan."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_config_and_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend'`

- [ ] **Step 3: Create `backend/pyproject.toml`, `.gitignore`, `.env.example`, `config/thresholds.yaml`, `config/weights.yaml`, `backend/config.py`, and `backend/schemas/token_report.py`**

Include `.superpowers/`, `.venv/`, `__pycache__/`, `*.db`, `.env`, `frontend/node_modules/`, and `frontend/.next/` in `.gitignore`. Pin exact default thresholds from Spec Section 4.2 & 4.3 (`min_liquidity_usd: 5000`, `promising_min_liquidity_usd: 25000`, `vol_liq_warn: 50.0`, `vol_liq_critical: 200.0`, `top10_warn: 0.30`, `top10_critical: 0.50`, `top1_warn: 0.10`, `top1_critical: 0.15`, `low_confidence_unknown_ratio: 0.30`) in `config/thresholds.yaml` and category weights (`30/25/20/15/10`) in `config/weights.yaml`. Install backend package in editable mode (`pip install -e backend[dev]`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_config_and_schemas.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Initialize git repository and commit**

```bash
git init
git add .gitignore .env.example config/ backend/ docs/ "Memecoin Audit Agent.md"
git commit -m "feat(core): initialize project structure, config loader, and report schemas"
```

---

### Task 2: Async Rate Limiter, TTL Cache, and DexScreener Client

**Files:**
- Create: `backend/clients/cache.py`
- Create: `backend/clients/rate_limiter.py`
- Create: `backend/clients/dexscreener.py`
- Test: `backend/tests/test_dexscreener_client.py`

**Interfaces:**
- Consumes: `backend.config.AppConfig`, `backend.schemas.token_report.MarketMetrics`
- Produces:
  - `TTLCache.get(key: str) -> Any | None`, `TTLCache.set(key: str, value: Any, ttl_seconds: int) -> None`
  - `TokenBucketLimiter.acquire(tokens: float = 1.0) -> None`
  - `DexScreenerClient`:
    - `fetch_latest_profiles() -> list[DiscoveredToken]`
    - `fetch_boosted_tokens() -> list[DiscoveredToken]`
    - `fetch_token_market(chain_id: str, token_address: str) -> tuple[TokenIdentity, MarketMetrics, dict[str, Any]] | None`
    - `search_pairs(query: str) -> list[dict[str, Any]]`

- [ ] **Step 1: Write the failing tests in `backend/tests/test_dexscreener_client.py` (including Review Focus #1)**

```python
import pytest
import httpx
from backend.clients.cache import TTLCache
from backend.clients.rate_limiter import TokenBucketLimiter
from backend.clients.dexscreener import DexScreenerClient

@pytest.mark.asyncio
async def test_dexscreener_selects_highest_liquidity_pair_and_handles_missing_fields():
    sample_pairs = [
        {
            "chainId": "solana",
            "pairAddress": "DeadPool111",
            "baseToken": {"address": "Mint111", "symbol": "TEST", "name": "Test Coin"},
            "priceUsd": "0.0001",
            "liquidity": None,
        },
        {
            "chainId": "solana",
            "pairAddress": "MainPool222",
            "dexId": "raydium",
            "baseToken": {"address": "Mint111", "symbol": "TEST", "name": "Test Coin"},
            "priceUsd": "0.0042",
            "liquidity": {"usd": 68000},
            "fdv": None,
            "marketCap": None,
            "volume": {"m5": 12000, "h1": 84000, "h6": 210000, "h24": 520000},
            "txns": {"m5": {"buys": 90, "sells": 50}, "h1": {"buys": 600, "sells": 350}},
            "priceChange": {"m5": 4.2, "h1": 18.5},
            "pairCreatedAt": None,
            "info": {"websites": [{"url": "https://test.io"}], "socials": [{"type": "twitter", "url": "https://x.com/test"}]},
        },
    ]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=sample_pairs)

    transport = httpx.MockTransport(handler)
    client = DexScreenerClient(http_client=httpx.AsyncClient(transport=transport), cache=TTLCache())
    result = await client.fetch_token_market("solana", "Mint111")
    assert result is not None
    identity, market, meta = result
    assert identity.symbol == "TEST"
    assert market.pair_address == "MainPool222"
    assert market.liquidity_usd == 68000.0
    assert market.market_cap is None
    assert market.pair_age_minutes is None
    assert meta["has_website"] is True
    assert meta["has_twitter"] is True

@pytest.mark.asyncio
async def test_dexscreener_retries_on_429_and_caches_pair_for_30s():
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0.01"})
        return httpx.Response(200, json=[{
            "chainId": "solana",
            "pairAddress": "Pool1",
            "baseToken": {"address": "MintA", "symbol": "A", "name": "Coin A"},
            "priceUsd": "1.0",
            "liquidity": {"usd": 10000},
        }])

    client = DexScreenerClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache=TTLCache())
    first = await client.fetch_token_market("solana", "MintA")
    second = await client.fetch_token_market("solana", "MintA")
    assert first is not None and second is not None
    assert calls == 2  # 1st call hit 429 then retried (2), 2nd call served from cache
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_dexscreener_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.clients'`

- [ ] **Step 3: Implement `backend/clients/cache.py`, `backend/clients/rate_limiter.py`, and `backend/clients/dexscreener.py`**

Implement `TTLCache` (in-memory dict with `time.monotonic()` expiration + optional Redis backend), `TokenBucketLimiter` (60/min for discovery endpoints, 300/min for pair/search endpoints), and `DexScreenerClient` with exponential backoff + HTTP 429 `Retry-After` handling and 30-second pair caching.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_dexscreener_client.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/clients/ backend/tests/test_dexscreener_client.py
git commit -m "feat(clients): add async rate limiter, TTL cache, and DexScreener client"
```

---

### Task 3: RugCheck Client, Optional Solana RPC Adapter, and CLI Single-Token Fetch (Milestone 1 Gate)

**Files:**
- Create: `backend/clients/rugcheck.py`
- Create: `backend/clients/solana_rpc.py`
- Create: `backend/adapters/base.py`
- Create: `backend/adapters/solana.py`
- Create: `backend/cli.py`
- Test: `backend/tests/test_rugcheck_and_cli.py`

**Interfaces:**
- Consumes: `TTLCache`, `TokenBucketLimiter`, `DexScreenerClient`
- Produces:
  - `RugCheckReport` (Pydantic model normalizing `mintAuthority`, `freezeAuthority`, `rugged`, `score`, `risks`, `topHolders`, `knownAccounts`, `graphInsidersDetected`, `markets`, `creator`, `creatorBalance`, `tokenProgram`, `tokenExtensions`)
  - `RugCheckClient.fetch_report(mint: str, force_refresh: bool = False) -> RugCheckReport | None`
  - `SolanaRpcClient.check_repeated_wallet_wash(pair_address: str) -> bool | None` (returns `None` when `HELIUS_API_KEY`/`SOLANA_RPC_URL` is unset)
  - `SolanaChainAdapter.enrich_token(mint: str, force_refresh: bool = False) -> EnrichedTokenData`

- [ ] **Step 1: Write the failing tests in `backend/tests/test_rugcheck_and_cli.py`**

```python
import pytest
import httpx
from backend.clients.cache import TTLCache
from backend.clients.rugcheck import RugCheckClient
from backend.clients.solana_rpc import SolanaRpcClient

@pytest.mark.asyncio
async def test_rugcheck_client_parses_report_and_sends_optional_api_key():
    seen_headers = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(dict(request.headers))
        return httpx.Response(200, json={
            "mint": "Mint111",
            "mintAuthority": None,
            "freezeAuthority": "FreezePubkey111",
            "rugged": False,
            "score": 450,
            "risks": [{"name": "Freeze Authority still enabled", "level": "danger", "score": 300}],
            "topHolders": [{"address": "Holder1", "pct": 12.5, "insider": False}],
            "knownAccounts": {"RaydiumLP1": {"name": "Raydium", "type": "AMM"}},
            "graphInsidersDetected": 2,
            "creator": "Creator1",
            "creatorBalance": 0,
        })

    client = RugCheckClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        cache=TTLCache(),
        api_key="secret-rug-key",
    )
    report = await client.fetch_report("Mint111")
    assert report is not None
    assert seen_headers.get("x-api-key") == "secret-rug-key"
    assert report.mint_authority is None
    assert report.freeze_authority == "FreezePubkey111"
    assert len(report.risks) == 1
    assert report.risks[0].level == "danger"

@pytest.mark.asyncio
async def test_solana_rpc_returns_none_when_no_rpc_url_configured():
    rpc = SolanaRpcClient(rpc_url=None)
    result = await rpc.check_repeated_wallet_wash("Pair111")
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_rugcheck_and_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.clients.rugcheck'`

- [ ] **Step 3: Implement `rugcheck.py`, `solana_rpc.py`, `adapters/base.py`, `adapters/solana.py`, and `cli.py`**

Cache RugCheck reports for 600s (10 minutes) unless `force_refresh=True`. On HTTP 404/5xx or timeout after retries, `fetch_report` returns `None` (so downstream treats RugCheck signals as `unknown`). Implement `python -m backend.cli fetch <mint>` to print enriched JSON from CLI.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_rugcheck_and_cli.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/clients/rugcheck.py backend/clients/solana_rpc.py backend/adapters/ backend/cli.py backend/tests/test_rugcheck_and_cli.py
git commit -m "feat(m1): add RugCheck client, Solana adapter, and CLI token fetcher"
```

---

### Task 4: GMGN Scout Module (`wash_trade.py`, `holders.py`, `contract.py`)

**Files:**
- Create: `backend/scout/wash_trade.py`
- Create: `backend/scout/holders.py`
- Create: `backend/scout/contract.py`
- Create: `backend/scout/gmgn_scout.py`
- Test: `backend/tests/test_gmgn_scout.py`

**Interfaces:**
- Consumes: `EnrichedTokenData`, `AppConfig`
- Produces:
  - `ScoutResult(flags: list[ScoutFlag], evaluated_signals: int, unknown_signals: int, metrics: dict[str, Any])`
  - `run_gmgn_scout(data: EnrichedTokenData, config: AppConfig) -> ScoutResult`

- [ ] **Step 1: Write the failing tests in `backend/tests/test_gmgn_scout.py` (including Review Focus #2 and #3)**

```python
from backend.config import load_config
from backend.schemas.token_report import MarketMetrics, TokenIdentity
from backend.clients.rugcheck import RugCheckReport, RugCheckHolder, RugCheckKnownAccount, RugCheckRisk
from backend.adapters.base import EnrichedTokenData
from backend.scout.gmgn_scout import run_gmgn_scout

def test_holders_excludes_lp_and_burn_accounts_from_concentration():
    cfg = load_config()
    rug = RugCheckReport(
        mint="MintSafe",
        mint_authority=None,
        freeze_authority=None,
        rugged=False,
        top_holders=[
            RugCheckHolder(address="RaydiumVault", pct=45.0, insider=False),
            RugCheckHolder(address="BurnAddr1111", pct=20.0, insider=False),
            RugCheckHolder(address="UserWallet1", pct=4.5, insider=False),
            RugCheckHolder(address="UserWallet2", pct=3.5, insider=False),
        ],
        known_accounts={
            "RaydiumVault": RugCheckKnownAccount(name="Raydium Vault", type="AMM"),
            "BurnAddr1111": RugCheckKnownAccount(name="Burn", type="BURN"),
        },
        lp_locked_pct=99.0,
    )
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintSafe", symbol="SAFE", name="Safe"),
        market=MarketMetrics(price_usd=0.01, liquidity_usd=50000.0, volume_24h=100000.0, pair_age_minutes=60, pair_address="RaydiumVault"),
        rugcheck=rug,
        social_meta={"has_website": True, "has_twitter": True},
        repeated_wallet_wash=None,
    )
    res = run_gmgn_scout(data, cfg)
    codes = {f.code for f in res.flags}
    assert "TOP10_CONCENTRATION" not in codes
    assert "SINGLE_HOLDER_CONCENTRATION" not in codes
    assert res.metrics["top10_pct_ex_lp"] == 8.0

def test_wash_trade_zero_liquidity_or_zero_txns_returns_unknown_without_zero_division():
    cfg = load_config()
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintZero", symbol="ZERO", name="Zero"),
        market=MarketMetrics(price_usd=0.001, liquidity_usd=0.0, volume_24h=5000.0, txns_h1_buys=0, txns_h1_sells=0, pair_age_minutes=10),
        rugcheck=None,
        social_meta={},
        repeated_wallet_wash=None,
    )
    res = run_gmgn_scout(data, cfg)
    assert res.unknown_signals > 0
    assert res.evaluated_signals >= res.unknown_signals

def test_contract_flags_active_mint_and_freeze_as_critical():
    cfg = load_config()
    rug = RugCheckReport(
        mint="MintTrap",
        mint_authority="MintAuthPubkey",
        freeze_authority="FreezeAuthPubkey",
        rugged=True,
        risks=[RugCheckRisk(name="Rugged", level="danger", score=1000)],
    )
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintTrap", symbol="TRAP", name="Trap"),
        market=MarketMetrics(price_usd=0.001, liquidity_usd=30000.0, volume_24h=10000.0, pair_age_minutes=30),
        rugcheck=rug,
    )
    res = run_gmgn_scout(data, cfg)
    crit_codes = {f.code for f in res.flags if f.category == "contract" and f.severity == "critical"}
    assert "MINT_AUTHORITY_ACTIVE" in crit_codes
    assert "FREEZE_AUTHORITY_ACTIVE" in crit_codes
    assert "RUGCHECK_DANGER_OR_RUGGED" in crit_codes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_gmgn_scout.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.scout'`

- [ ] **Step 3: Implement `wash_trade.py`, `holders.py`, `contract.py`, and `gmgn_scout.py`**

Implement all signals in Spec Section 4.2:
- `wash_trade.py`: `VOL_LIQ_RATIO_HIGH` (>50x warn, >200x critical), `UNIFORM_BUY_SELL_RATIO`, `HIGH_TXNS_FLAT_PRICE`, `SUDDEN_VOL_SPIKE_NO_LIQ`, `REPEATED_WALLET_WASH`.
- `holders.py`: Filter LP/AMM/LOCKER/BURN and `pair_address` before computing `top1_pct_ex_lp`, `top10_pct_ex_lp`, `top20_pct_ex_lp`; check `TOP10_CONCENTRATION` (>30% warn, >50% critical), `SINGLE_HOLDER_CONCENTRATION` (>10% warn, >15% critical), `INSIDER_BUNDLE_CLUSTER`, `CREATOR_HOLDINGS_AND_SELLS`.
- `contract.py`: `MINT_AUTHORITY_ACTIVE`, `FREEZE_AUTHORITY_ACTIVE`, `DANGEROUS_TOKEN_EXTENSION`, `LP_UNLOCKED_OR_SHORT`, `RUGCHECK_DANGER_OR_RUGGED`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_gmgn_scout.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/scout/ backend/tests/test_gmgn_scout.py
git commit -m "feat(scout): implement gmgn_scout wash trade, holder bundle, and contract checks"
```

---

### Task 5: Deterministic Risk Rubric, Verdict Engine, and Override Rules

**Files:**
- Create: `backend/scoring/rubric.py`
- Create: `backend/scoring/verdict.py`
- Test: `backend/tests/test_scoring_and_verdict.py`

**Interfaces:**
- Consumes: `EnrichedTokenData`, `ScoutResult`, `AppConfig`
- Produces:
  - `ScoringResult(risk_score: int, verdict: Literal["AVOID", "HIGH RISK", "WATCH", "PROMISING"], confidence: Literal["high", "medium", "low"], breakdown: ScoreBreakdown, is_shortlisted_for_ai: bool)`
  - `evaluate_token_score(data: EnrichedTokenData, scout: ScoutResult, config: AppConfig) -> ScoringResult`

- [ ] **Step 1: Write the failing tests in `backend/tests/test_scoring_and_verdict.py`**

```python
from backend.config import load_config
from backend.schemas.token_report import MarketMetrics, TokenIdentity
from backend.clients.rugcheck import RugCheckReport, RugCheckHolder
from backend.adapters.base import EnrichedTokenData
from backend.scout.gmgn_scout import run_gmgn_scout
from backend.scoring.verdict import evaluate_token_score

def test_contract_critical_flag_forces_avoid_override_even_when_score_is_low():
    cfg = load_config()
    rug = RugCheckReport(
        mint="MintOverride",
        mint_authority="StillActiveAuth",
        freeze_authority=None,
        rugged=False,
        top_holders=[RugCheckHolder(address="User1", pct=2.0)],
        lp_locked_pct=100.0,
    )
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintOverride", symbol="OVR", name="Override"),
        market=MarketMetrics(price_usd=0.05, liquidity_usd=80000.0, market_cap=400000.0, volume_24h=150000.0, pair_age_minutes=120),
        rugcheck=rug,
        social_meta={"has_website": True, "has_twitter": True},
    )
    scout = run_gmgn_scout(data, cfg)
    res = evaluate_token_score(data, scout, cfg)
    assert res.risk_score < 70
    assert res.verdict == "AVOID"
    assert res.is_shortlisted_for_ai is False

def test_promising_downgrades_to_watch_when_liquidity_under_25k_or_rugcheck_missing():
    cfg = load_config()
    rug = RugCheckReport(mint="MintLowLiq", mint_authority=None, freeze_authority=None, rugged=False, lp_locked_pct=100.0)
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintLowLiq", symbol="LOW", name="LowLiq"),
        market=MarketMetrics(price_usd=0.01, liquidity_usd=18000.0, market_cap=100000.0, volume_24h=30000.0, pair_age_minutes=90),
        rugcheck=rug,
        social_meta={"has_website": True, "has_twitter": True},
    )
    scout = run_gmgn_scout(data, cfg)
    res = evaluate_token_score(data, scout, cfg)
    assert res.risk_score <= 29
    assert res.verdict == "WATCH"
    assert res.is_shortlisted_for_ai is True

def test_missing_rugcheck_sets_low_confidence_and_never_promising():
    cfg = load_config()
    data = EnrichedTokenData(
        token=TokenIdentity(chain="solana", address="MintNoRug", symbol="NORUG", name="NoRug"),
        market=MarketMetrics(price_usd=0.01, liquidity_usd=60000.0, market_cap=300000.0, volume_24h=90000.0, pair_age_minutes=60),
        rugcheck=None,
        social_meta={"has_website": True, "has_twitter": True},
    )
    scout = run_gmgn_scout(data, cfg)
    res = evaluate_token_score(data, scout, cfg)
    assert res.confidence == "low"
    assert res.verdict != "PROMISING"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_scoring_and_verdict.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.scoring'`

- [ ] **Step 3: Implement `backend/scoring/rubric.py` and `backend/scoring/verdict.py`**

Implement category penalty calculation capped at `30/25/20/15/10` (`total <= 100`), base verdict thresholds (`70-100 AVOID`, `50-69 HIGH RISK`, `30-49 WATCH`, `0-29 PROMISING`), and all 3 override rules from Spec Section 4.3. Set `is_shortlisted_for_ai = verdict in ("PROMISING", "WATCH")`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_scoring_and_verdict.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/scoring/ backend/tests/test_scoring_and_verdict.py
git commit -m "feat(scoring): implement deterministic risk rubric, verdict mapping, and overrides"
```

---

### Task 6: Local `9router` AI Analyst & Shortlist Batch Ranker (Milestone 2 Gate)

**Files:**
- Create: `backend/ai/prompts.py`
- Create: `backend/ai/fallback.py`
- Create: `backend/ai/nine_router.py`
- Test: `backend/tests/test_nine_router_ai.py`

**Interfaces:**
- Consumes: `TokenAuditReport`, `AppConfig`
- Produces:
  - `build_deterministic_fallback_analysis(report: TokenAuditReport, status: Literal["skipped", "unavailable"] = "unavailable") -> AIAnalysisResult`
  - `NineRouterClient.analyze_token(report: TokenAuditReport, recent_snapshots: list[dict] | None = None) -> AIAnalysisResult`
  - `NineRouterClient.rank_shortlist(reports: list[TokenAuditReport]) -> list[str]` (returns ordered list of token addresses from healthiest to weakest)

- [ ] **Step 1: Write the failing tests in `backend/tests/test_nine_router_ai.py` (including Review Focus #4)**

```python
import pytest
import httpx
from backend.config import load_config
from backend.schemas.token_report import TokenAuditReport, ScoutFlag
from backend.ai.nine_router import NineRouterClient

def _sample_promising_report() -> TokenAuditReport:
    return TokenAuditReport(
        token={"chain": "solana", "address": "MintPromising1", "symbol": "BONKAI", "name": "Bonk Agent"},
        scanned_at="2026-10-24T20:00:00+07:00",
        market={"price_usd": 0.0041, "liquidity_usd": 68000.0, "market_cap": 410000.0, "volume_24h": 520000.0, "pair_age_minutes": 42},
        risk_score=18,
        verdict="PROMISING",
        confidence="high",
        breakdown={"contract": 0, "holders": 8, "volume_integrity": 4, "liquidity": 4, "social": 2},
        flags=[ScoutFlag(category="holders", severity="warn", code="CREATOR_HOLDINGS", value=0.024, threshold=0.05, source="rugcheck")],
        summary_id="Placeholder",
    )

@pytest.mark.asyncio
async def test_nine_router_handles_markdown_fences_and_falls_back_on_timeout():
    cfg = load_config()
    fenced_json = """```json
    {
      "health_status": "HEALTHY",
      "buyer_quality": "ORGANIC",
      "conviction_score": 84,
      "momentum_phase": "EARLY_ACCUMULATION",
      "liquidity_stress": {
        "rating": "STRONG",
        "lp_to_top10_ratio": 0.79,
        "note_id": "Likuiditas $68K sanggup menyerap tekanan jual Top 10."
      },
      "narrative_quality": "SOLID",
      "summary_id": "Token memiliki struktur kontrak aman tanpa otoritas mint/freeze. Distribusi holder sehat dengan arus pembeli organik. Pantau pergerakan wallet creator yang masih memegang 2.4% suplai.",
      "decision_brief": {
        "bull_case_id": "Kontrak bersih dan rasio pembelian organik kuat di 62%.",
        "red_flag_id": "Umur pair baru 42 menit.",
        "invalidation_trigger_id": "Batalkan pantauan jika likuiditas turun di bawah $45.000."
      },
      "shortlist_rank_reason_id": "Kandidat paling sehat karena likuiditas tebal dan minim bot."
    }
    ```"""

    def ok_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:20128/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": fenced_json}}]})

    client = NineRouterClient(config=cfg, http_client=httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)))
    report = _sample_promising_report()
    ai_res = await client.analyze_token(report)
    assert ai_res.status == "completed"
    assert ai_res.model == "gemini-3.8-flash-high"
    assert ai_res.health_status == "HEALTHY"
    assert ai_res.buyer_quality == "ORGANIC"
    assert "45.000" in ai_res.decision_brief.invalidation_trigger_id

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("9router timed out")

    offline_client = NineRouterClient(config=cfg, http_client=httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)))
    fallback_res = await offline_client.analyze_token(report)
    assert fallback_res.status == "unavailable"
    assert fallback_res.health_status in ("HEALTHY", "MIXED", "UNHEALTHY")
    assert len(fallback_res.summary_id) > 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_nine_router_ai.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.ai'`

- [ ] **Step 3: Implement `backend/ai/prompts.py`, `backend/ai/fallback.py`, and `backend/ai/nine_router.py`**

Also update `backend/cli.py` so `python -m backend.cli audit <mint>` runs full enrichment + GMGN Scout + deterministic scoring + `9router` analysis and outputs the complete JSON report.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_nine_router_ai.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/ai/ backend/cli.py backend/tests/test_nine_router_ai.py
git commit -m "feat(m2): integrate local 9router AI analyst (gemini-3.8-flash-high) with deterministic fallback"
```

---

### Task 7: Database Persistence, Scheduled Discovery/Enrichment/Re-scan Pipeline, and Alert Engine (Milestone 3 Gate)

**Files:**
- Create: `backend/db/models.py`
- Create: `backend/db/session.py`
- Create: `backend/db/repository.py`
- Create: `backend/pipeline/prefilter.py`
- Create: `backend/pipeline/alerts.py`
- Create: `backend/pipeline/worker.py`
- Test: `backend/tests/test_pipeline_and_alerts.py`

**Interfaces:**
- Consumes: `SolanaChainAdapter`, `run_gmgn_scout`, `evaluate_token_score`, `NineRouterClient`, `AppConfig`
- Produces:
  - SQLAlchemy tables: `tokens`, `snapshots`, `flags`, `scores`, `watchlist`, `alerts`
  - `AuditRepository`: `save_audit_report(report: TokenAuditReport) -> PreviousSnapshotDelta`, `list_tokens(filters: TokenFilterParams) -> list[TokenAuditReport]`, `get_token_detail(chain: str, address: str) -> TokenDetailView | None`, `manage_watchlist(...)`, `list_alerts(...)`
  - `ScanPipelineWorker.run_discovery_cycle() -> list[TokenAuditReport]`
  - `ScanPipelineWorker.run_rescan_cycle() -> list[TokenAuditReport]`
  - `ScanPipelineWorker.audit_single_token(chain: str, address: str, force_refresh: bool = True) -> TokenAuditReport`

- [ ] **Step 1: Write the failing tests in `backend/tests/test_pipeline_and_alerts.py` (including Review Focus #5)**

```python
import pytest
from backend.config import load_config
from backend.db.session import create_async_session_factory
from backend.db.repository import AuditRepository
from backend.pipeline.alerts import evaluate_alerts_for_transition
from backend.schemas.token_report import TokenAuditReport, ScoutFlag

@pytest.mark.asyncio
async def test_pipeline_rescan_detects_verdict_change_and_liquidity_drop_alert(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    session_factory = await create_async_session_factory(db_url)
    repo = AuditRepository(session_factory)
    cfg = load_config()

    await repo.add_to_watchlist(chain="solana", address="MintWatch1", symbol="W1", name="Watch 1", alert_liquidity_drop_pct=20.0)

    snap1 = TokenAuditReport(
        token={"chain": "solana", "address": "MintWatch1", "symbol": "W1", "name": "Watch 1"},
        scanned_at="2026-10-24T20:00:00+07:00",
        market={"price_usd": 0.01, "liquidity_usd": 60000.0, "market_cap": 300000.0, "volume_24h": 120000.0, "pair_age_minutes": 50},
        risk_score=20,
        verdict="PROMISING",
        confidence="high",
        breakdown={"contract": 0, "holders": 10, "volume_integrity": 4, "liquidity": 4, "social": 2},
        flags=[],
        summary_id="Awal yang sehat.",
    )
    delta1 = await repo.save_audit_report(snap1)
    assert delta1.verdict_changed is False

    snap2 = snap1.model_copy(deep=True)
    snap2.scanned_at = "2026-10-24T20:03:00+07:00"
    snap2.market.liquidity_usd = 40000.0  # -33.3% drop (> 20% threshold)
    snap2.risk_score = 58
    snap2.verdict = "HIGH RISK"
    delta2 = await repo.save_audit_report(snap2)
    assert delta2.verdict_changed is True
    assert delta2.previous_verdict == "PROMISING"

    alerts = await evaluate_alerts_for_transition(repo, snap2, delta2, cfg)
    alert_types = {a.alert_type for a in alerts}
    assert "VERDICT_CHANGED" in alert_types
    assert "LIQUIDITY_DROP" in alert_types
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_pipeline_and_alerts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.db'`

- [ ] **Step 3: Implement `backend/db/`, `backend/pipeline/prefilter.py`, `backend/pipeline/alerts.py`, and `backend/pipeline/worker.py`**

Enable SQLite `PRAGMA journal_mode=WAL;` on connection connect. Implement cheap pre-filter (`min_liquidity_usd >= 5000`, `5 <= pair_age_minutes <= 10080`), bounded concurrency (`asyncio.Semaphore(5)`), discovery every 60s, and re-scan of `PROMISING`/`WATCH`/watchlisted tokens every 180s.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_pipeline_and_alerts.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/db/ backend/pipeline/ backend/tests/test_pipeline_and_alerts.py
git commit -m "feat(m3): add SQLite WAL persistence, discovery/rescan pipeline, and alert engine"
```

---

### Task 8: FastAPI REST Endpoints, Manual Audit, Settings API, and Live SSE Stream

**Files:**
- Create: `backend/api/sse.py`
- Create: `backend/api/routes.py`
- Create: `backend/api/main.py`
- Test: `backend/tests/test_api_endpoints.py`

**Interfaces:**
- Consumes: `AuditRepository`, `ScanPipelineWorker`, `AppConfig`
- Produces:
  - `GET /api/v1/health` -> pipeline status, last scan timestamp, DexScreener/RugCheck/`9router` health
  - `GET /api/v1/tokens` -> filterable/sortable token list + `top_ai_picks` shortlist array
  - `GET /api/v1/tokens/{chain}/{address}` -> token detail + historical snapshots + flags + `ai_analysis`
  - `POST /api/v1/tokens/audit` -> on-demand manual audit (`{"chain": "solana", "address": "..."}`)
  - `GET /api/v1/watchlist`, `POST /api/v1/watchlist`, `DELETE /api/v1/watchlist/{chain}/{address}`
  - `GET /api/v1/alerts`
  - `GET /api/v1/settings`, `PUT /api/v1/settings`
  - `GET /api/v1/stream/events` -> SSE stream (`token_scored`, `verdict_changed`, `ai_analyzed`, `alert_triggered`)

- [ ] **Step 1: Write the failing tests in `backend/tests/test_api_endpoints.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from backend.api.main import create_app

@pytest.mark.asyncio
async def test_api_health_tokens_and_settings_endpoints(tmp_path):
    app = await create_app(db_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}", enable_scheduler=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        health = await ac.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["nine_router"]["model"] == "gemini-3.8-flash-high"

        tokens = await ac.get("/api/v1/tokens")
        assert tokens.status_code == 200
        assert "items" in tokens.json()
        assert "top_ai_picks" in tokens.json()

        settings_res = await ac.put("/api/v1/settings", json={"min_liquidity_usd": 7500.0})
        assert settings_res.status_code == 200
        assert settings_res.json()["thresholds"]["prefilter"]["min_liquidity_usd"] == 7500.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_api_endpoints.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.api'`

- [ ] **Step 3: Implement `backend/api/sse.py`, `backend/api/routes.py`, and `backend/api/main.py`**

Implement `SSEBroadcaster` with per-client `asyncio.Queue`, CORS middleware for `http://localhost:3000`, and all REST endpoints.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_api_endpoints.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/api/ backend/tests/test_api_endpoints.py
git commit -m "feat(api): add FastAPI REST endpoints, manual audit trigger, settings API, and SSE stream"
```

---

### Task 9: Next.js Live Dashboard — Page 1 (Live Scanner + Top AI Picks Banner) & Page 2 (Token Detail + AI Decision Panel) (Milestone 4 Gate)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/next.config.mjs`
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/components/Navbar.tsx`
- Create: `frontend/src/components/TopAIPicksBanner.tsx`
- Create: `frontend/src/components/LiveScannerTable.tsx`
- Create: `frontend/src/components/AIDecisionPanel.tsx`
- Create: `frontend/src/components/TokenCharts.tsx`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/tokens/[chain]/[address]/page.tsx`

**Interfaces:**
- Consumes: FastAPI `/api/v1/*` and SSE `/api/v1/stream/events`
- Produces:
  - Page 1 (`/`): Option A Unified Live Scanner featuring `TopAIPicksBanner` (highlighting `PROMISING`/`WATCH` coins vetted by `9router` with Health badge `SEHAT`/`MERAGUKAN`/`TIDAK SEHAT`, Buyer Quality `REAL BUYER`, Risk Score, and AI brief), manual mint audit search bar, filter/sort controls, and real-time `LiveScannerTable` with SSE auto-updates.
  - Page 2 (`/tokens/[chain]/[address]`): Token header with copy-address & DexScreener/RugCheck links, `AIDecisionPanel` (`9router` `gemini-3.8-flash-high` verdict, Buyer Quality, Momentum Phase, Liquidity Stress vs Top 10, Bull Case, Red Flag, Invalidation Trigger), category score breakdown bars, grouped GMGN Scout flags with numerical proofs, Recharts price/liquidity & holder distribution donut chart, and "Pindai Ulang" button.

- [ ] **Step 1: Create Next.js TypeScript project files and components in `frontend/`**

Scaffold `frontend/` with Next.js 14, React 18, TypeScript, Tailwind CSS, `@tanstack/react-table`, `recharts`, and `lucide-react`. Ensure permanent footer disclaimer `"Analisis otomatis, bukan nasihat keuangan. Memecoin berisiko kehilangan seluruh modal."` is rendered in `layout.tsx`.

- [ ] **Step 2: Install frontend dependencies and run TypeScript / Next.js build check**

Run: `cd frontend && npm install && npm run build`
Expected: Next.js production build succeeds with zero TypeScript or ESLint errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/
git commit -m "feat(m4): build Next.js Live Scanner with Top AI Picks banner and Token Detail page"
```

---

### Task 10: Watchlist & Alerts Page, Settings Page, Telegram Notifier, and Docker Compose / README Hardening (Milestones 5 & 6 Gate)

**Files:**
- Create: `backend/clients/telegram.py`
- Create: `frontend/src/app/watchlist/page.tsx`
- Create: `frontend/src/app/settings/page.tsx`
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `README.md`
- Test: `backend/tests/test_telegram_notifier.py`

**Interfaces:**
- Consumes: `/api/v1/watchlist`, `/api/v1/alerts`, `/api/v1/settings`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Produces:
  - `TelegramNotifier.send_alert(alert: AlertRecord) -> bool` (no-op returning `False` when token/chat_id unset)
  - Page 3 (`/watchlist`): Manage watched tokens, custom alert thresholds, and live alert feed.
  - Page 4 (`/settings`): Configure pre-filter thresholds, category weights, scan intervals, and `9router` endpoint/model settings.
  - `docker-compose.yml` & `README.md` with honest limitations, setup instructions, environment variables, and sample JSON report.

- [ ] **Step 1: Write the failing test in `backend/tests/test_telegram_notifier.py`**

```python
import pytest
import httpx
from backend.clients.telegram import TelegramNotifier

@pytest.mark.asyncio
async def test_telegram_notifier_skips_when_unconfigured_and_sends_when_configured():
    unconfigured = TelegramNotifier(bot_token=None, chat_id=None)
    assert await unconfigured.send_message("Test alert") is False

    sent_payload = {}
    def handler(request: httpx.Request) -> httpx.Response:
        import json
        sent_payload.update(json.loads(request.content.decode()))
        return httpx.Response(200, json={"ok": True})

    configured = TelegramNotifier(
        bot_token="123:ABC",
        chat_id="999",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    assert await configured.send_message("Alert: Verdict berubah") is True
    assert sent_payload["chat_id"] == "999"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_telegram_notifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.clients.telegram'`

- [ ] **Step 3: Implement `backend/clients/telegram.py`, Watchlist page (`/watchlist`), Settings page (`/settings`), `docker-compose.yml`, Dockerfiles, and `README.md`**

Wire `TelegramNotifier` into `evaluate_alerts_for_transition` in `backend/pipeline/alerts.py`. Build `/watchlist` and `/settings` pages in Next.js, add `docker-compose.yml` (with `extra_hosts: ["host.docker.internal:host-gateway"]` so backend container reaches host `9router` on port `20128`), and write `README.md`.

- [ ] **Step 4: Run full backend test suite and frontend production build**

Run: `pytest backend/tests/ -v && cd frontend && npm run build`
Expected: All backend tests PASS and Next.js build succeeds cleanly covering `/`, `/tokens/[chain]/[address]`, `/watchlist`, and `/settings`.

- [ ] **Step 5: Commit**

```bash
git add backend/ frontend/ docker-compose.yml README.md
git commit -m "feat(m5-m6): add watchlist, Telegram alerts, settings UI, Docker Compose, and README"
```
