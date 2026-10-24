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
