from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from constants import (
    CHAIN_ID,
    DEFAULT_FACTORY_REGISTRY,
)
from db import Database
from factory_discovery import process_factory_log_async
from rpc import RpcClient


TEST_TX = "0x9bb432e106d1d056affc99a57818e1927e1587cd676ce9c73162f2429a5883b2"


async def main():
    load_dotenv(".env", override=True)

    rpc_url = os.getenv("RPC_HTTP_URL", "")
    if not rpc_url:
        raise SystemExit("RPC_HTTP_URL is missing")

    rpc = RpcClient(rpc_url)

    chain_id = int(await rpc.call("eth_chainId", []), 16)

    if chain_id != CHAIN_ID:
        raise SystemExit(
            f"Wrong chain: expected {CHAIN_ID}, got {chain_id}"
        )

    receipt = await rpc.call(
        "eth_getTransactionReceipt",
        [TEST_TX],
    )

    if not receipt:
        raise SystemExit("FAIL: transaction receipt not found")

    block_number = int(receipt["blockNumber"], 16)

    logs = await rpc.call(
        "eth_getLogs",
        [{
            "address": [
                DEFAULT_FACTORY_REGISTRY[0]["factory"]
            ],
            "topics": [[
                DEFAULT_FACTORY_REGISTRY[0]["topic0"]
            ]],
            "fromBlock": hex(block_number),
            "toBlock": hex(block_number),
        }],
    )

    matching = [
        item
        for item in logs
        if item["transactionHash"].lower() == TEST_TX.lower()
    ]

    if not matching:
        raise SystemExit(
            "FAIL: known PairCreated log not found"
        )

    item = matching[0]

    db_path = "pool_registry_smoke_test.db"
    Path(db_path).unlink(missing_ok=True)

    db = Database(db_path)

    try:
        await db.open()

        inserted = await process_factory_log_async(
            db=db,
            chain_id=chain_id,
            item=item,
            registry=DEFAULT_FACTORY_REGISTRY,
        )

        print(f"FACTORY PROCESS | inserted={inserted}")

        pools = await db.get_pools()

        print(f"POOL REGISTRY | total_pools={len(pools)}")

        if not pools:
            raise SystemExit(
                "FAIL: Pool Registry contains no pools"
            )

        (
            stored_chain_id,
            stored_pool,
            stored_dex,
            stored_version,
            stored_token0,
            stored_token1,
            stored_fee,
            stored_tick_spacing,
            stored_discovered_by,
            stored_active,
        ) = pools[0]

        print()
        print("POOL REGISTRY ENTRY")
        print(f"  chain_id     = {stored_chain_id}")
        print(f"  pool         = {stored_pool}")
        print(f"  dex          = {stored_dex}")
        print(f"  version      = {stored_version}")
        print(f"  token0       = {stored_token0}")
        print(f"  token1       = {stored_token1}")
        print(f"  fee          = {stored_fee}")
        print(f"  tick_spacing = {stored_tick_spacing}")
        print(f"  discovered   = {stored_discovered_by}")
        print(f"  active       = {stored_active}")

        expected_pool = "0x96333416B6F5180d6b441B750Df70F572c3D844c"
        expected_token0 = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        expected_token1 = "0xd1Ea5cB30Fe85bf057C04DC6DF70BbcA51A9d713"

        checks = {
            "chain_id": stored_chain_id == chain_id,
            "pool": stored_pool.lower() == expected_pool.lower(),
            "dex": stored_dex == "uniswap_v2",
            "version": stored_version == "v2",
            "token0": stored_token0.lower() == expected_token0.lower(),
            "token1": stored_token1.lower() == expected_token1.lower(),
            "fee": stored_fee is None,
            "tick_spacing": stored_tick_spacing is None,
            "discovered_by": stored_discovered_by == "factory",
            "active": stored_active == 1,
        }

        print()
        print("FIELD VALIDATION")

        for name, ok in checks.items():
            print(f"  {name:15} = {'OK' if ok else 'FAIL'}")

        if not all(checks.values()):
            raise SystemExit(
                "FAIL: Pool Registry field validation failed"
            )

        stored = await db.get_pool(
            chain_id,
            expected_pool,
        )

        if not stored:
            raise SystemExit(
                "FAIL: get_pool() could not retrieve discovered pool"
            )

        print()
        print("POOL LOOKUP OK")
        print(f"  lookup_pool = {stored[1]}")
        print(f"  lookup_dex  = {stored[2]}")
        print(f"  lookup_ver  = {stored[3]}")
        print(f"  lookup_token0 = {stored[4]}")
        print(f"  lookup_token1 = {stored[5]}")

        print()
        print("FACTORY -> DB -> POOL REGISTRY SMOKE TEST OK")

    finally:
        await db.close()
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
