from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Callable, Coroutine

from backend.adapters.solana import SolanaChainAdapter
from backend.ai.fallback import build_deterministic_fallback_analysis
from backend.ai.nine_router import NineRouterClient
from backend.clients.cache import TTLCache
from backend.clients.dexscreener import DexScreenerClient
from backend.clients.rugcheck import RugCheckClient
from backend.clients.solana_rpc import SolanaRpcClient
from backend.config import AppConfig, load_config
from backend.db.repository import AuditRepository
from backend.db.session import create_async_session_factory
from backend.pipeline.alerts import evaluate_alerts_for_transition
from backend.pipeline.prefilter import passes_cheap_prefilter
from backend.schemas.token_report import TokenAuditReport
from backend.scoring.verdict import evaluate_token_score
from backend.scout.gmgn_scout import run_gmgn_scout


EventCallback = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class ScanPipelineWorker:
    def __init__(
        self,
        config: AppConfig,
        repo: AuditRepository,
        adapter: SolanaChainAdapter,
        ai_client: NineRouterClient,
        event_cb: EventCallback | None = None,
        alert_notifier_cb: Callable[[Any], Coroutine[Any, Any, Any]] | None = None,
    ) -> None:
        self.config = config
        self.repo = repo
        self.adapter = adapter
        self.ai_client = ai_client
        self.event_cb = event_cb
        self.alert_notifier_cb = alert_notifier_cb
        self.last_discovery_at: str | None = None
        self.last_rescan_at: str | None = None
        self._sem = asyncio.Semaphore(config.thresholds.scanner.max_concurrency)

    async def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        if self.event_cb is not None:
            try:
                await self.event_cb(event_type, data)
            except Exception:
                pass

    async def audit_single_token(
        self,
        chain: str,
        address: str,
        force_refresh: bool = True,
        force_ai: bool = True,
    ) -> TokenAuditReport | None:
        async with self._sem:
            enriched = await self.adapter.enrich_token(address, force_refresh=force_refresh)
            if enriched is None:
                return None

            scout = run_gmgn_scout(enriched, self.config)
            scoring = evaluate_token_score(enriched, scout, self.config)
            now_iso = datetime.now(timezone.utc).astimezone().isoformat()

            draft_report = TokenAuditReport(
                token=enriched.token,
                scanned_at=now_iso,
                market=enriched.market,
                risk_score=scoring.risk_score,
                verdict=scoring.verdict,
                confidence=scoring.confidence,
                breakdown=scoring.breakdown,
                flags=scoring.all_flags,
                summary_id="Menganalisis data...",
                holder_metrics=scout.metrics,
                social_meta=enriched.social_meta,
            )

            recent_snaps = await self.repo.get_recent_snapshots(chain, address, limit=5)
            if force_ai or scoring.is_shortlisted_for_ai:
                ai_res = await self.ai_client.analyze_token(draft_report, recent_snapshots=recent_snaps)
            else:
                ai_res = build_deterministic_fallback_analysis(
                    draft_report,
                    status="skipped",
                    model_name=self.config.ai.model,
                )

            draft_report.ai_analysis = ai_res
            draft_report.summary_id = ai_res.summary_id

            delta = await self.repo.save_audit_report(draft_report)
            await self._emit("token_scored", draft_report.model_dump(mode="json"))

            if delta.verdict_changed:
                await self._emit(
                    "verdict_changed",
                    {
                        "token": draft_report.token.model_dump(mode="json"),
                        "previous_verdict": delta.previous_verdict,
                        "new_verdict": draft_report.verdict,
                        "risk_score": draft_report.risk_score,
                    },
                )

            if ai_res.status == "completed":
                await self._emit("ai_analyzed", draft_report.model_dump(mode="json"))

            alerts = await evaluate_alerts_for_transition(
                self.repo,
                draft_report,
                delta,
                self.config,
                notifier_cb=self.alert_notifier_cb,
            )
            for al in alerts:
                await self._emit("alert_triggered", al.model_dump(mode="json"))

            return draft_report

    async def run_discovery_cycle(self, max_tokens: int = 12) -> list[TokenAuditReport]:
        discovered = await self.adapter.discover_tokens()
        candidates = discovered[:max_tokens]
        results: list[TokenAuditReport] = []

        async def _process_candidate(token_address: str) -> TokenAuditReport | None:
            dex_res = await self.adapter.dexscreener.fetch_token_market("solana", token_address)
            if dex_res is None:
                return None
            _, market, _ = dex_res
            ok, _reason = passes_cheap_prefilter(market, self.config)
            if not ok:
                return None
            return await self.audit_single_token(
                "solana",
                token_address,
                force_refresh=False,
                force_ai=False,
            )

        tasks = [_process_candidate(c.token_address) for c in candidates]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for item in completed:
            if isinstance(item, TokenAuditReport):
                results.append(item)

        self.last_discovery_at = datetime.now(timezone.utc).astimezone().isoformat()
        return results

    async def run_rescan_cycle(self) -> list[TokenAuditReport]:
        targets = await self.repo.list_rescan_candidates(limit=15)
        results: list[TokenAuditReport] = []
        tasks = [
            self.audit_single_token(chain, addr, force_refresh=True, force_ai=False)
            for chain, addr in targets
        ]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for item in completed:
            if isinstance(item, TokenAuditReport):
                results.append(item)
        self.last_rescan_at = datetime.now(timezone.utc).astimezone().isoformat()
        return results


async def run_cli_single_audit(mint: str) -> int:
    cfg = load_config()
    session_factory = await create_async_session_factory(cfg.database_url)
    repo = AuditRepository(session_factory)
    cache = TTLCache()
    dex = DexScreenerClient(cache=cache)
    rug = RugCheckClient(cache=cache, api_key=cfg.rugcheck_api_key)
    rpc = SolanaRpcClient(rpc_url=cfg.solana_rpc_url)
    adapter = SolanaChainAdapter(dexscreener=dex, rugcheck=rug, solana_rpc=rpc)
    ai_client = NineRouterClient(config=cfg)

    worker = ScanPipelineWorker(
        config=cfg,
        repo=repo,
        adapter=adapter,
        ai_client=ai_client,
    )
    try:
        report = await worker.audit_single_token("solana", mint, force_refresh=True, force_ai=True)
        if report is None:
            print(json.dumps({"error": f"Token {mint} not found on DexScreener"}, indent=2))
            return 1
        print(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return 0
    finally:
        await dex.close()
        await rug.close()
        await rpc.close()
        await ai_client.close()
