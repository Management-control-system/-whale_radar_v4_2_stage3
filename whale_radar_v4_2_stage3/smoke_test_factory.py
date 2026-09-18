from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from constants import DEFAULT_FACTORY_REGISTRY
from db import Database
from factory_discovery import backfill
from rpc import RpcClient


load_dotenv(".env", override=True)


async def main():
    rpc_url = os.getenv("RPC_HTTP_URL", "")

    if not rpc_url:
        raise SystemExit("RPC_HTTP_URL is missing")

    rpc = RpcClient(rpc_url)

    chain_id = int(
        await rpc.call("eth_chainId", []),
        16,
    )

    latest = int(
        await rpc.call("eth_blockNumber", []),
        16,
    )

    print(
        f"FACTORY SMOKE | chain_id={chain_id} "
        f"| latest_block={latest}"
    )

    if chain_id != 1:
        raise SystemExit(
            f"Expected Ethereum Mainnet chain_id=1, got {chain_id}"
        )

    db_path = "factory_smoke_test.db"
    db = Database(db_path)

    try:
        Path(db_path).unlink(missing_ok=True)

        await db.open()

        # Smaller window for reliable eth_getLogs testing.
        start_block = max(0, latest - 99)

        print(
            f"Searching blocks {start_block} -> {latest}"
        )

        await backfill(
            db=db,
            rpc=rpc,
            chain_id=chain_id,
            registry=DEFAULT_FACTORY_REGISTRY,
            start_block=start_block,
            end_block=latest,
            chunk_size=10,
        )

        pools = await db.get_pools()

        v2_pools = [
            p for p in pools
            if p[2] == "uniswap_v2"
        ]

        v3_pools = [
            p for p in pools
            if p[2] == "uniswap_v3"
        ]

        print(
            f"FACTORY RESULT | total_pools={len(pools)} "
            f"| v2={len(v2_pools)} "
            f"| v3={len(v3_pools)}"
        )

        if v2_pools:
            p = v2_pools[0]

            print(
                "V2 FACTORY OK | "
                f"pool={p[1]} | "
                f"token0={p[4]} | "
                f"token1={p[5]} | "
                f"discovered_by={p[8]}"
            )
        else:
            print("V2 FACTORY: NO POOLS FOUND")

        if v3_pools:
            p = v3_pools[0]

            print(
                "V3 FACTORY OK | "
                f"pool={p[1]} | "
                f"token0={p[4]} | "
                f"token1={p[5]} | "
                f"fee={p[6]} | "
                f"tick_spacing={p[7]} | "
                f"discovered_by={p[8]}"
            )
        else:
            print("V3 FACTORY: NO POOLS FOUND")

        if v2_pools and v3_pools:
            print(
                "FACTORY SMOKE TEST OK | "
                "V2=True | V3=True"
            )
        else:
            print(
                "FACTORY SMOKE TEST INCOMPLETE | "
                f"V2={bool(v2_pools)} | "
                f"V3={bool(v3_pools)}"
            )

    finally:
        await db.close()

        # Windows can only remove SQLite files after the connection is closed.
        try:
            Path(db_path).unlink(missing_ok=True)
        except PermissionError:
            print(
                f"WARNING: Could not remove {db_path}. "
                "The file may still be held by another process."
            )


if __name__ == "__main__":
    asyncio.run(main())