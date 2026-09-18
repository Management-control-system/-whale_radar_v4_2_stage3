from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from abi_decode import decode_v2_pair_created
from constants import (
    CHAIN_ID,
    UNISWAP_V2_FACTORY,
    V2_PAIR_CREATED,
)
from rpc import RpcClient


# Real Uniswap V2 Factory "Create Pair" transaction.
TEST_TX = "0x9bb432e106d1d056affc99a57818e1927e1587cd676ce9c73162f2429a5883b2"


async def main():
    load_dotenv(".env", override=True)

    rpc_url = os.getenv("RPC_HTTP_URL", "")
    if not rpc_url:
        raise SystemExit("RPC_HTTP_URL is missing")

    rpc = RpcClient(rpc_url)

    chain_id = int(await rpc.call("eth_chainId", []), 16)
    print(f"V2 FACTORY TEST | chain_id={chain_id}")

    if chain_id != CHAIN_ID:
        raise SystemExit(
            f"Wrong chain: expected {CHAIN_ID}, got {chain_id}"
        )

    receipt = await rpc.call(
        "eth_getTransactionReceipt",
        [TEST_TX],
    )

    if not receipt:
        raise SystemExit(
            "FAIL: transaction receipt not found"
        )

    block_number = int(receipt["blockNumber"], 16)

    print(
        f"KNOWN TX | tx={TEST_TX}"
    )
    print(
        f"KNOWN BLOCK | block={block_number}"
    )

    params = [{
        "address": [UNISWAP_V2_FACTORY],
        "topics": [[V2_PAIR_CREATED]],
        "fromBlock": hex(block_number),
        "toBlock": hex(block_number),
    }]

    logs = await rpc.call("eth_getLogs", params)

    print(
        f"V2 LOG QUERY | block={block_number} | "
        f"logs_found={len(logs)}"
    )

    if not logs:
        raise SystemExit(
            "FAIL: no V2 PairCreated logs found in the "
            "transaction block"
        )

    matched = False

    for item in logs:
        if item["transactionHash"].lower() != TEST_TX.lower():
            continue

        matched = True

        decoded = decode_v2_pair_created(
            item,
            chain_id,
            {
                "dex": "uniswap_v2",
                "version": "v2",
                "factory": UNISWAP_V2_FACTORY,
                "event": "pair",
                "topic0": V2_PAIR_CREATED,
            },
        )

        print()
        print("V2 FACTORY DECODE OK")
        print(f"  pool       = {decoded.pool.pool_address}")
        print(f"  token0     = {decoded.pool.token0}")
        print(f"  token1     = {decoded.pool.token1}")
        print(f"  dex        = {decoded.pool.dex}")
        print(f"  discovered = {decoded.pool.discovered_by}")
        print(f"  event      = {decoded.event_name}")
        print(f"  block      = {int(item["blockNumber"], 16)}")
        print(f"  tx_hash    = {item["transactionHash"]}")
        print(f"  log_index  = {int(item["logIndex"], 16)}")

    if not matched:
        raise SystemExit(
            "FAIL: PairCreated log exists in the block, "
            "but none belongs to the known Create Pair transaction"
        )

    print()
    print("V2 FACTORY SMOKE TEST OK")


if __name__ == "__main__":
    asyncio.run(main())

