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
    assert calls == 2
