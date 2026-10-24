from __future__ import annotations

import asyncio

from backend.adapters.base import ChainAdapter, EnrichedTokenData
from backend.clients.dexscreener import DexScreenerClient, DiscoveredToken
from backend.clients.rugcheck import RugCheckClient
from backend.clients.solana_rpc import SolanaRpcClient


class SolanaChainAdapter(ChainAdapter):
    chain_id = "solana"

    def __init__(
        self,
        dexscreener: DexScreenerClient,
        rugcheck: RugCheckClient,
        solana_rpc: SolanaRpcClient | None = None,
    ) -> None:
        self.dexscreener = dexscreener
        self.rugcheck = rugcheck
        self.solana_rpc = solana_rpc or SolanaRpcClient(rpc_url=None)

    async def discover_tokens(self) -> list[DiscoveredToken]:
        profiles, boosts = await asyncio.gather(
            self.dexscreener.fetch_latest_profiles(),
            self.dexscreener.fetch_boosted_tokens(),
            return_exceptions=True,
        )
        combined: list[DiscoveredToken] = []
        if isinstance(profiles, list):
            combined.extend(profiles)
        if isinstance(boosts, list):
            combined.extend(boosts)

        seen: set[str] = set()
        deduped: list[DiscoveredToken] = []
        for item in combined:
            if item.chain_id != "solana":
                continue
            key = f"{item.chain_id}:{item.token_address}"
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped

    async def enrich_token(
        self,
        token_address: str,
        force_refresh: bool = False,
    ) -> EnrichedTokenData | None:
        dex_task = self.dexscreener.fetch_token_market(
            self.chain_id,
            token_address,
            force_refresh=force_refresh,
        )
        rug_task = self.rugcheck.fetch_report(token_address, force_refresh=force_refresh)

        dex_res, rug_res = await asyncio.gather(dex_task, rug_task, return_exceptions=True)
        if isinstance(dex_res, Exception) or dex_res is None:
            return None

        identity, market, social_meta = dex_res
        rug_report = None if isinstance(rug_res, Exception) else rug_res
        repeated_wash = await self.solana_rpc.check_repeated_wallet_wash(market.pair_address)

        return EnrichedTokenData(
            token=identity,
            market=market,
            rugcheck=rug_report,
            social_meta=social_meta,
            repeated_wallet_wash=repeated_wash,
        )
