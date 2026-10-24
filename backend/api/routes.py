from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.db.repository import TokenFilterParams


class ManualAuditRequest(BaseModel):
    chain: str = "solana"
    address: str


class WatchlistCreateRequest(BaseModel):
    chain: str = "solana"
    address: str
    symbol: str = "UNKNOWN"
    name: str = "Unknown Token"
    alert_on_verdict_change: bool = True
    alert_liquidity_drop_pct: float = 20.0
    alert_on_top_holder_sell: bool = True
    alert_on_authority_change: bool = True


router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def get_health(request: Request) -> dict[str, Any]:
    state = request.app.state
    cfg = state.config
    worker = state.worker
    dex = state.dexscreener
    rug = state.rugcheck
    ai = state.ai_client

    return {
        "status": "ok",
        "last_discovery_at": worker.last_discovery_at,
        "last_rescan_at": worker.last_rescan_at,
        "dexscreener": {
            "healthy": dex.last_error is None,
            "last_ok_at": dex.last_ok_at,
            "last_error": dex.last_error,
            "remaining_tokens_per_min": int(dex.pairs_limiter.tokens),
        },
        "rugcheck": {
            "healthy": rug.last_error is None,
            "last_ok_at": rug.last_ok_at,
            "last_error": rug.last_error,
            "remaining_tokens_per_min": int(rug.limiter.tokens),
        },
        "nine_router": {
            "base_url": cfg.ai.base_url,
            "model": cfg.ai.model,
            "healthy": ai.last_error is None,
            "last_ok_at": ai.last_ok_at,
            "last_error": ai.last_error,
        },
    }


@router.get("/tokens")
async def list_tokens(
    request: Request,
    verdict: str | None = Query(default=None),
    chain: str | None = Query(default=None),
    min_liquidity_usd: float | None = Query(default=None),
    min_age_minutes: int | None = Query(default=None),
    max_age_minutes: int | None = Query(default=None),
    hide_critical: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    repo = request.app.state.repo
    ai_client = request.app.state.ai_client

    filters = TokenFilterParams(
        verdict=verdict,
        chain=chain,
        min_liquidity_usd=min_liquidity_usd,
        min_age_minutes=min_age_minutes,
        max_age_minutes=max_age_minutes,
        hide_critical=hide_critical,
        limit=limit,
    )
    items = await repo.list_tokens(filters)
    shortlisted = [r for r in items if r.verdict in ("PROMISING", "WATCH")]
    ranked_addrs = ai_client.rank_shortlist(shortlisted)
    addr_to_report = {r.token.address: r for r in shortlisted}
    top_ai_picks = [
        addr_to_report[addr].model_dump(mode="json")
        for addr in ranked_addrs[:6]
        if addr in addr_to_report
    ]

    return {
        "items": [r.model_dump(mode="json") for r in items],
        "top_ai_picks": top_ai_picks,
        "total": len(items),
    }


@router.get("/tokens/{chain}/{address}")
async def get_token_detail(
    request: Request,
    chain: str,
    address: str,
) -> dict[str, Any]:
    repo = request.app.state.repo
    detail = await repo.get_token_detail(chain, address)
    if detail is None:
        raise HTTPException(status_code=404, detail="Token belum ditemukan di database. Gunakan tombol Audit Manual.")
    return detail.model_dump(mode="json")


@router.post("/tokens/audit")
async def manual_audit_token(
    request: Request,
    body: ManualAuditRequest,
) -> dict[str, Any]:
    worker = request.app.state.worker
    report = await worker.audit_single_token(
        chain=body.chain.lower(),
        address=body.address.strip(),
        force_refresh=True,
        force_ai=True,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Pair token tidak ditemukan di DexScreener.")
    return report.model_dump(mode="json")


@router.post("/pipeline/scan-now")
async def trigger_scan_now(request: Request) -> dict[str, Any]:
    worker = request.app.state.worker
    scanned = await worker.run_discovery_cycle(max_tokens=10)
    return {"scanned_count": len(scanned), "items": [r.model_dump(mode="json") for r in scanned]}


@router.get("/watchlist")
async def get_watchlist(request: Request) -> dict[str, Any]:
    repo = request.app.state.repo
    items = await repo.list_watchlist()
    return {"items": [i.model_dump(mode="json") for i in items]}


@router.post("/watchlist")
async def add_watchlist(
    request: Request,
    body: WatchlistCreateRequest,
) -> dict[str, Any]:
    repo = request.app.state.repo
    item = await repo.add_to_watchlist(
        chain=body.chain,
        address=body.address,
        symbol=body.symbol,
        name=body.name,
        alert_on_verdict_change=body.alert_on_verdict_change,
        alert_liquidity_drop_pct=body.alert_liquidity_drop_pct,
        alert_on_top_holder_sell=body.alert_on_top_holder_sell,
        alert_on_authority_change=body.alert_on_authority_change,
    )
    return item.model_dump(mode="json")


@router.delete("/watchlist/{chain}/{address}")
async def delete_watchlist(
    request: Request,
    chain: str,
    address: str,
) -> dict[str, Any]:
    repo = request.app.state.repo
    removed = await repo.remove_from_watchlist(chain, address)
    return {"removed": removed}


@router.get("/alerts")
async def get_alerts(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    repo = request.app.state.repo
    alerts = await repo.list_alerts(limit=limit)
    return {"items": [a.model_dump(mode="json") for a in alerts]}


@router.get("/settings")
async def get_settings(request: Request) -> dict[str, Any]:
    cfg = request.app.state.config
    return {
        "thresholds": cfg.thresholds.model_dump(mode="json"),
        "weights": cfg.weights.model_dump(mode="json"),
        "ai": {
            "base_url": cfg.ai.base_url,
            "model": cfg.ai.model,
        },
    }


@router.put("/settings")
async def update_settings(
    request: Request,
    payload: dict[str, Any],
) -> dict[str, Any]:
    cfg = request.app.state.config
    if "min_liquidity_usd" in payload:
        cfg.thresholds.prefilter.min_liquidity_usd = float(payload["min_liquidity_usd"])
    if "min_pair_age_minutes" in payload:
        cfg.thresholds.prefilter.min_pair_age_minutes = int(payload["min_pair_age_minutes"])
    if "max_pair_age_minutes" in payload:
        cfg.thresholds.prefilter.max_pair_age_minutes = int(payload["max_pair_age_minutes"])
    if "discovery_interval_seconds" in payload:
        cfg.thresholds.scanner.discovery_interval_seconds = int(payload["discovery_interval_seconds"])
    if "rescan_interval_seconds" in payload:
        cfg.thresholds.scanner.rescan_interval_seconds = int(payload["rescan_interval_seconds"])
    if "promising_min_liquidity_usd" in payload:
        cfg.thresholds.verdict_rules.promising_min_liquidity_usd = float(payload["promising_min_liquidity_usd"])
    if "weights" in payload and isinstance(payload["weights"], dict):
        w = payload["weights"]
        for k in ("contract", "holders", "volume_integrity", "liquidity", "social"):
            if k in w:
                setattr(cfg.weights, k, int(w[k]))
    if "ai" in payload and isinstance(payload["ai"], dict):
        if "base_url" in payload["ai"]:
            cfg.ai.base_url = str(payload["ai"]["base_url"])
        if "model" in payload["ai"]:
            cfg.ai.model = str(payload["ai"]["model"])

    return await get_settings(request)


@router.get("/stream/events")
async def stream_events(request: Request) -> StreamingResponse:
    broadcaster = request.app.state.broadcaster
    return StreamingResponse(
        broadcaster.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
