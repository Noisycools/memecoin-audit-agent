from __future__ import annotations

from collections import Counter
import httpx


class SolanaRpcClient:
    """Optional Solana RPC adapter (e.g. Helius) for per-wallet wash trade detection."""

    def __init__(
        self,
        rpc_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.rpc_url = rpc_url
        self._client = http_client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = http_client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def check_repeated_wallet_wash(self, pair_address: str | None) -> bool | None:
        if not self.rpc_url or not pair_address:
            return None
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [pair_address, {"limit": 40}],
            }
            resp = await self._client.post(self.rpc_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            sigs = data.get("result") if isinstance(data, dict) else None
            if not isinstance(sigs, list) or not sigs:
                return False
            slot_counts = Counter(
                s.get("slot") for s in sigs if isinstance(s, dict) and s.get("slot") is not None
            )
            return any(count >= 6 for count in slot_counts.values())
        except Exception:
            return None
