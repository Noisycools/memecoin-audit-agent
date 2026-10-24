from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field

from backend.clients.dexscreener import DiscoveredToken
from backend.clients.rugcheck import RugCheckReport
from backend.schemas.token_report import MarketMetrics, TokenIdentity


class EnrichedTokenData(BaseModel):
    token: TokenIdentity
    market: MarketMetrics
    rugcheck: RugCheckReport | None = None
    social_meta: dict[str, Any] = Field(default_factory=dict)
    repeated_wallet_wash: bool | None = None


class ChainAdapter(ABC):
    chain_id: str

    @abstractmethod
    async def discover_tokens(self) -> list[DiscoveredToken]:
        raise NotImplementedError

    @abstractmethod
    async def enrich_token(self, token_address: str, force_refresh: bool = False) -> EnrichedTokenData | None:
        raise NotImplementedError
