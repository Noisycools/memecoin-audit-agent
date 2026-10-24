from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.adapters.solana import SolanaChainAdapter
from backend.clients.cache import TTLCache
from backend.clients.dexscreener import DexScreenerClient
from backend.clients.rugcheck import RugCheckClient
from backend.clients.solana_rpc import SolanaRpcClient
from backend.config import load_config


async def _run_fetch(mint: str) -> int:
    cfg = load_config()
    cache = TTLCache()
    dex = DexScreenerClient(cache=cache)
    rug = RugCheckClient(cache=cache, api_key=cfg.rugcheck_api_key)
    rpc = SolanaRpcClient(rpc_url=cfg.solana_rpc_url)
    adapter = SolanaChainAdapter(dexscreener=dex, rugcheck=rug, solana_rpc=rpc)
    try:
        enriched = await adapter.enrich_token(mint, force_refresh=True)
        if enriched is None:
            print(json.dumps({"error": f"Token {mint} not found on DexScreener"}, indent=2))
            return 1
        print(json.dumps(enriched.model_dump(mode="json"), indent=2))
        return 0
    finally:
        await dex.close()
        await rug.close()
        await rpc.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Memecoin Audit Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser("fetch", help="Fetch raw DexScreener + RugCheck enriched data for a Solana mint")
    fetch_p.add_argument("mint", help="Solana token mint address")

    audit_p = sub.add_parser("audit", help="Run full deterministic + 9router AI audit on a Solana mint")
    audit_p.add_argument("mint", help="Solana token mint address")

    args = parser.parse_args(argv)
    if args.command == "fetch":
        return asyncio.run(_run_fetch(args.mint))
    if args.command == "audit":
        from backend.pipeline.worker import run_cli_single_audit
        return asyncio.run(run_cli_single_audit(args.mint))
    return 1


if __name__ == "__main__":
    sys.exit(main())
