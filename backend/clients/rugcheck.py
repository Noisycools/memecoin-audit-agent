from __future__ import annotations

import asyncio
import time
from typing import Any
import httpx
from pydantic import BaseModel, Field

from backend.clients.cache import TTLCache
from backend.clients.rate_limiter import TokenBucketLimiter


class RugCheckRisk(BaseModel):
    name: str
    level: str = "info"
    description: str = ""
    score: int = 0
    value: str | None = None


class RugCheckHolder(BaseModel):
    address: str
    pct: float = 0.0
    amount: float | None = None
    insider: bool = False
    owner: str | None = None


class RugCheckKnownAccount(BaseModel):
    name: str = ""
    type: str = ""


class RugCheckReport(BaseModel):
    mint: str
    mint_authority: str | None = None
    freeze_authority: str | None = None
    rugged: bool = False
    score: int | None = None
    risks: list[RugCheckRisk] = Field(default_factory=list)
    top_holders: list[RugCheckHolder] = Field(default_factory=list)
    known_accounts: dict[str, RugCheckKnownAccount] = Field(default_factory=dict)
    graph_insiders_detected: int = 0
    lp_locked_pct: float | None = None
    creator: str | None = None
    creator_balance_pct: float | None = None
    mutable_metadata: bool | None = None
    transfer_fee_bps: int | None = None
    permanent_delegate: str | None = None


def _safe_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class RugCheckClient:
    BASE_URL = "https://api.rugcheck.xyz/v1"
    REPORT_CACHE_TTL = 600  # 10 minutes

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        cache: TTLCache | None = None,
        limiter: TokenBucketLimiter | None = None,
        api_key: str | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=15.0)
        self._owns_client = http_client is None
        self.cache = cache if cache is not None else TTLCache()
        self.limiter = limiter or TokenBucketLimiter(rate_per_minute=30)
        self.api_key = api_key
        self.max_retries = max_retries
        self.last_ok_at: float | None = None
        self.last_error: str | None = None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_report(
        self,
        mint: str,
        force_refresh: bool = False,
    ) -> RugCheckReport | None:
        cache_key = f"rugcheck:report:{mint}"
        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        headers: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-KEY"] = self.api_key

        url = f"{self.BASE_URL}/tokens/{mint}/report"
        for attempt in range(self.max_retries):
            await self.limiter.acquire()
            try:
                resp = await self._client.get(url, headers=headers)
                if resp.status_code == 429:
                    retry_after = _safe_float(resp.headers.get("Retry-After"))
                    await asyncio.sleep(min(retry_after or (0.5 * (2**attempt)), 5.0))
                    continue
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                raw = resp.json()
                report = self._parse_report(mint, raw)
                self.cache.set(cache_key, report, self.REPORT_CACHE_TTL)
                self.last_ok_at = time.time()
                self.last_error = None
                return report
            except Exception as exc:
                self.last_error = str(exc)
                if attempt == self.max_retries - 1:
                    return None
                await asyncio.sleep(0.2 * (2**attempt))
        return None

    def _parse_report(self, mint: str, raw: dict[str, Any]) -> RugCheckReport:
        token_obj = raw.get("token") if isinstance(raw.get("token"), dict) else {}
        mint_auth = raw.get("mintAuthority", token_obj.get("mintAuthority"))
        freeze_auth = raw.get("freezeAuthority", token_obj.get("freezeAuthority"))

        risks_raw = raw.get("risks") if isinstance(raw.get("risks"), list) else []
        risks = [
            RugCheckRisk(
                name=str(r.get("name") or ""),
                level=str(r.get("level") or "info").lower(),
                description=str(r.get("description") or ""),
                score=int(r.get("score") or 0),
                value=str(r.get("value")) if r.get("value") is not None else None,
            )
            for r in risks_raw
            if isinstance(r, dict)
        ]

        holders_raw = raw.get("topHolders") if isinstance(raw.get("topHolders"), list) else []
        top_holders = [
            RugCheckHolder(
                address=str(h.get("address") or h.get("owner") or ""),
                pct=float(h.get("pct") or 0.0),
                amount=_safe_float(h.get("uiAmount") or h.get("amount")),
                insider=bool(h.get("insider") or False),
                owner=h.get("owner"),
            )
            for h in holders_raw
            if isinstance(h, dict) and (h.get("address") or h.get("owner"))
        ]

        known_raw = raw.get("knownAccounts") if isinstance(raw.get("knownAccounts"), dict) else {}
        known_accounts: dict[str, RugCheckKnownAccount] = {}
        for addr, info in known_raw.items():
            if isinstance(info, dict):
                known_accounts[str(addr)] = RugCheckKnownAccount(
                    name=str(info.get("name") or ""),
                    type=str(info.get("type") or ""),
                )

        markets = raw.get("markets") if isinstance(raw.get("markets"), list) else []
        lp_locked_pct: float | None = _safe_float(raw.get("lpLockedPct"))
        if lp_locked_pct is None and markets:
            locked_vals = []
            for m in markets:
                if isinstance(m, dict) and isinstance(m.get("lp"), dict):
                    val = _safe_float(m["lp"].get("lpLockedPct"))
                    if val is not None:
                        locked_vals.append(val)
            if locked_vals:
                lp_locked_pct = max(locked_vals)

        creator = raw.get("creator")
        creator_balance_pct: float | None = None
        if creator:
            for h in top_holders:
                if h.address == creator or h.owner == creator:
                    creator_balance_pct = h.pct
                    break
            if creator_balance_pct is None and raw.get("creatorBalance") == 0:
                creator_balance_pct = 0.0

        token_meta = raw.get("tokenMeta") if isinstance(raw.get("tokenMeta"), dict) else {}
        mutable_meta = token_meta.get("mutable") if "mutable" in token_meta else None

        ext = raw.get("transferFee") if isinstance(raw.get("transferFee"), dict) else {}
        transfer_fee_bps = int(ext.get("pct", 0) * 100) if ext.get("pct") else None

        return RugCheckReport(
            mint=str(raw.get("mint") or mint),
            mint_authority=str(mint_auth) if mint_auth else None,
            freeze_authority=str(freeze_auth) if freeze_auth else None,
            rugged=bool(raw.get("rugged") or False),
            score=int(raw["score"]) if isinstance(raw.get("score"), (int, float)) else None,
            risks=risks,
            top_holders=top_holders,
            known_accounts=known_accounts,
            graph_insiders_detected=int(raw.get("graphInsidersDetected") or 0),
            lp_locked_pct=lp_locked_pct,
            creator=str(creator) if creator else None,
            creator_balance_pct=creator_balance_pct,
            mutable_metadata=bool(mutable_meta) if mutable_meta is not None else None,
            transfer_fee_bps=transfer_fee_bps,
            permanent_delegate=raw.get("permanentDelegate"),
        )
