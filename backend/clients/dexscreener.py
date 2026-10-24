from __future__ import annotations

import asyncio
import time
from typing import Any
import httpx
from pydantic import BaseModel

from backend.clients.cache import TTLCache
from backend.clients.rate_limiter import TokenBucketLimiter
from backend.schemas.token_report import MarketMetrics, TokenIdentity


class DiscoveredToken(BaseModel):
    chain_id: str
    token_address: str
    source: str
    icon_url: str | None = None
    description: str | None = None


def _to_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _to_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


class DexScreenerClient:
    BASE_URL = "https://api.dexscreener.com"
    PAIR_CACHE_TTL = 30

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        cache: TTLCache | None = None,
        discovery_limiter: TokenBucketLimiter | None = None,
        pairs_limiter: TokenBucketLimiter | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=15.0)
        self._owns_client = http_client is None
        self.cache = cache if cache is not None else TTLCache()
        self.discovery_limiter = discovery_limiter or TokenBucketLimiter(rate_per_minute=60)
        self.pairs_limiter = pairs_limiter or TokenBucketLimiter(rate_per_minute=300)
        self.max_retries = max_retries
        self.last_ok_at: float | None = None
        self.last_error: str | None = None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request_json(
        self,
        path: str,
        limiter: TokenBucketLimiter,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.BASE_URL}{path}"
        for attempt in range(self.max_retries):
            await limiter.acquire()
            try:
                resp = await self._client.get(url, params=params)
                if resp.status_code == 429:
                    retry_after = _to_float(resp.headers.get("Retry-After"))
                    wait = retry_after if retry_after is not None else (0.5 * (2**attempt))
                    await asyncio.sleep(min(wait, 5.0))
                    continue
                resp.raise_for_status()
                self.last_ok_at = time.time()
                self.last_error = None
                return resp.json()
            except Exception as exc:
                self.last_error = str(exc)
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(0.2 * (2**attempt))
        return None

    async def fetch_latest_profiles(self) -> list[DiscoveredToken]:
        data = await self._request_json("/token-profiles/latest/v1", self.discovery_limiter)
        items = data if isinstance(data, list) else []
        results: list[DiscoveredToken] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            chain = str(item.get("chainId") or "").lower()
            addr = str(item.get("tokenAddress") or "").strip()
            if chain and addr:
                results.append(
                    DiscoveredToken(
                        chain_id=chain,
                        token_address=addr,
                        source="dexscreener:token-profiles/latest",
                        icon_url=item.get("icon"),
                        description=item.get("description"),
                    )
                )
        return results

    async def fetch_boosted_tokens(self) -> list[DiscoveredToken]:
        results: list[DiscoveredToken] = []
        for endpoint in ("/token-boosts/latest/v1", "/token-boosts/top/v1"):
            try:
                data = await self._request_json(endpoint, self.discovery_limiter)
            except Exception:
                continue
            items = data if isinstance(data, list) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                chain = str(item.get("chainId") or "").lower()
                addr = str(item.get("tokenAddress") or "").strip()
                if chain and addr:
                    results.append(
                        DiscoveredToken(
                            chain_id=chain,
                            token_address=addr,
                            source=f"dexscreener:{endpoint.strip('/')}",
                            icon_url=item.get("icon"),
                            description=item.get("description"),
                        )
                    )
        return results

    async def fetch_token_market(
        self,
        chain_id: str,
        token_address: str,
        force_refresh: bool = False,
    ) -> tuple[TokenIdentity, MarketMetrics, dict[str, Any]] | None:
        cache_key = f"dex:pairs:{chain_id.lower()}:{token_address}"
        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        raw = await self._request_json(
            f"/token-pairs/v1/{chain_id}/{token_address}",
            self.pairs_limiter,
        )
        pairs: list[dict[str, Any]] = []
        if isinstance(raw, list):
            pairs = [p for p in raw if isinstance(p, dict)]
        elif isinstance(raw, dict) and isinstance(raw.get("pairs"), list):
            pairs = [p for p in raw["pairs"] if isinstance(p, dict)]

        if not pairs:
            return None

        def _liq_score(pair: dict[str, Any]) -> float:
            liq_obj = pair.get("liquidity")
            if isinstance(liq_obj, dict):
                return _to_float(liq_obj.get("usd")) or -1.0
            return -1.0

        best = max(pairs, key=_liq_score)
        parsed = self._parse_pair(chain_id, token_address, best)
        self.cache.set(cache_key, parsed, self.PAIR_CACHE_TTL)
        return parsed

    async def search_pairs(self, query: str) -> list[dict[str, Any]]:
        data = await self._request_json(
            "/latest/dex/search",
            self.pairs_limiter,
            params={"q": query},
        )
        if isinstance(data, dict) and isinstance(data.get("pairs"), list):
            return data["pairs"]
        return []

    def _parse_pair(
        self,
        chain_id: str,
        token_address: str,
        pair: dict[str, Any],
    ) -> tuple[TokenIdentity, MarketMetrics, dict[str, Any]]:
        base_token = pair.get("baseToken") if isinstance(pair.get("baseToken"), dict) else {}
        info = pair.get("info") if isinstance(pair.get("info"), dict) else {}
        liq = pair.get("liquidity") if isinstance(pair.get("liquidity"), dict) else {}
        vol = pair.get("volume") if isinstance(pair.get("volume"), dict) else {}
        txns = pair.get("txns") if isinstance(pair.get("txns"), dict) else {}
        pchange = pair.get("priceChange") if isinstance(pair.get("priceChange"), dict) else {}

        m5_tx = txns.get("m5") if isinstance(txns.get("m5"), dict) else {}
        h1_tx = txns.get("h1") if isinstance(txns.get("h1"), dict) else {}
        h6_tx = txns.get("h6") if isinstance(txns.get("h6"), dict) else {}
        h24_tx = txns.get("h24") if isinstance(txns.get("h24"), dict) else {}

        created_at_ms = _to_int(pair.get("pairCreatedAt"))
        pair_age_minutes: int | None = None
        if created_at_ms is not None and created_at_ms > 0:
            now_ms = int(time.time() * 1000)
            pair_age_minutes = max(0, (now_ms - created_at_ms) // 60000)

        websites = info.get("websites") if isinstance(info.get("websites"), list) else []
        socials = info.get("socials") if isinstance(info.get("socials"), list) else []

        social_types = {
            str(s.get("type") or "").lower()
            for s in socials
            if isinstance(s, dict)
        }

        identity = TokenIdentity(
            chain=str(pair.get("chainId") or chain_id).lower(),
            address=str(base_token.get("address") or token_address),
            symbol=str(base_token.get("symbol") or "UNKNOWN"),
            name=str(base_token.get("name") or "Unknown Token"),
            logo_url=info.get("imageUrl"),
        )

        market = MarketMetrics(
            price_usd=_to_float(pair.get("priceUsd")),
            liquidity_usd=_to_float(liq.get("usd")),
            market_cap=_to_float(pair.get("marketCap")),
            fdv=_to_float(pair.get("fdv")),
            volume_24h=_to_float(vol.get("h24")),
            volume_h6=_to_float(vol.get("h6")),
            volume_h1=_to_float(vol.get("h1")),
            volume_m5=_to_float(vol.get("m5")),
            txns_m5_buys=_to_int(m5_tx.get("buys")),
            txns_m5_sells=_to_int(m5_tx.get("sells")),
            txns_h1_buys=_to_int(h1_tx.get("buys")),
            txns_h1_sells=_to_int(h1_tx.get("sells")),
            txns_h6_buys=_to_int(h6_tx.get("buys")),
            txns_h6_sells=_to_int(h6_tx.get("sells")),
            txns_h24_buys=_to_int(h24_tx.get("buys")),
            txns_h24_sells=_to_int(h24_tx.get("sells")),
            price_change_m5=_to_float(pchange.get("m5")),
            price_change_h1=_to_float(pchange.get("h1")),
            price_change_h6=_to_float(pchange.get("h6")),
            price_change_h24=_to_float(pchange.get("h24")),
            pair_age_minutes=pair_age_minutes,
            pair_address=pair.get("pairAddress"),
            dex_id=pair.get("dexId"),
            pair_url=pair.get("url"),
        )

        social_meta = {
            "has_website": len(websites) > 0,
            "websites": [w.get("url") for w in websites if isinstance(w, dict) and w.get("url")],
            "has_twitter": "twitter" in social_types,
            "has_telegram": "telegram" in social_types,
            "socials": [s for s in socials if isinstance(s, dict)],
            "pair_count": 1,
        }
        return identity, market, social_meta
