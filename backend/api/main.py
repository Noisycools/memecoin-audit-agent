from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.adapters.solana import SolanaChainAdapter
from backend.ai.nine_router import NineRouterClient
from backend.api.routes import router
from backend.api.sse import SSEBroadcaster
from backend.clients.cache import TTLCache
from backend.clients.dexscreener import DexScreenerClient
from backend.clients.rugcheck import RugCheckClient
from backend.clients.solana_rpc import SolanaRpcClient
from backend.config import AppConfig, load_config
from backend.db.repository import AuditRepository
from backend.db.session import create_async_session_factory
from backend.pipeline.worker import ScanPipelineWorker


async def create_app(
    db_url: str | None = None,
    enable_scheduler: bool = True,
    config: AppConfig | None = None,
) -> FastAPI:
    cfg = config or load_config()
    if db_url:
        cfg.database_url = db_url

    session_factory = await create_async_session_factory(cfg.database_url)
    repo = AuditRepository(session_factory)
    cache = TTLCache()
    dex = DexScreenerClient(cache=cache)
    rug = RugCheckClient(cache=cache, api_key=cfg.rugcheck_api_key)
    rpc = SolanaRpcClient(rpc_url=cfg.solana_rpc_url)
    adapter = SolanaChainAdapter(dexscreener=dex, rugcheck=rug, solana_rpc=rpc)
    ai_client = NineRouterClient(config=cfg)
    broadcaster = SSEBroadcaster()

    worker = ScanPipelineWorker(
        config=cfg,
        repo=repo,
        adapter=adapter,
        ai_client=ai_client,
        event_cb=broadcaster.broadcast,
    )

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None, None]:
        bg_tasks: list[asyncio.Task[None]] = []
        stop_event = asyncio.Event()

        async def _discovery_loop() -> None:
            while not stop_event.is_set():
                try:
                    await worker.run_discovery_cycle(max_tokens=10)
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=float(cfg.thresholds.scanner.discovery_interval_seconds),
                    )
                except asyncio.TimeoutError:
                    pass

        async def _rescan_loop() -> None:
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=float(cfg.thresholds.scanner.rescan_interval_seconds),
                    )
                except asyncio.TimeoutError:
                    pass
                if stop_event.is_set():
                    break
                try:
                    await worker.run_rescan_cycle()
                except Exception:
                    pass

        if enable_scheduler:
            bg_tasks.append(asyncio.create_task(_discovery_loop()))
            bg_tasks.append(asyncio.create_task(_rescan_loop()))

        try:
            yield
        finally:
            stop_event.set()
            for t in bg_tasks:
                t.cancel()
            await dex.close()
            await rug.close()
            await rpc.close()
            await ai_client.close()

    app = FastAPI(
        title="Memecoin Audit Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.config = cfg
    app.state.repo = repo
    app.state.dexscreener = dex
    app.state.rugcheck = rug
    app.state.ai_client = ai_client
    app.state.broadcaster = broadcaster
    app.state.worker = worker

    app.include_router(router)
    return app
