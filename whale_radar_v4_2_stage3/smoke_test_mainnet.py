"""Run this on the user's machine, not in the restricted sandbox.

It validates:
1) HTTP RPC
2) WebSocket factory subscription
3) one recent V2/V3 factory log decoded into a pool
4) optional router monitoring can be enabled separately.

No secrets are printed.
"""
from __future__ import annotations

import asyncio
import json
import os

import websockets
from dotenv import load_dotenv

from abi_decode import decode_v2_pair_created, decode_v3_pool_created
from constants import DEFAULT_FACTORY_REGISTRY, V2_PAIR_CREATED, V3_POOL_CREATED
from rpc import RpcClient

load_dotenv(".env", override=True)


async def main():
    http = os.environ["RPC_HTTP_URL"]
    ws_url = os.environ["RPC_WS_URL"]
    rpc = RpcClient(http)

    chain_id = int(await rpc.call("eth_chainId", []), 16)
    latest = int(await rpc.call("eth_blockNumber", []), 16)
    print(f"HTTP RPC: OK | chain_id={chain_id} | latest_block={latest}")

    # Ask for a small recent window. This is intentionally local and bounded.
    start = max(0, latest - 2000)
    logs = []
    for factory in DEFAULT_FACTORY_REGISTRY:
        logs.extend(await rpc.call("eth_getLogs", [{
            "address": [factory["factory"]],
            "topics": [[factory["topic0"]]],
            "fromBlock": hex(start),
            "toBlock": hex(latest),
        }]))

    if not logs:
        raise RuntimeError("No recent factory logs found in the last 2000 blocks.")

    decoded = 0
    for item in logs[-20:]:
        topic0 = item["topics"][0].lower()
        try:
            if topic0 == V2_PAIR_CREATED:
                d = decode_v2_pair_created(item, chain_id, DEFAULT_FACTORY_REGISTRY[0])
            elif topic0 == V3_POOL_CREATED:
                d = decode_v3_pool_created(item, chain_id, DEFAULT_FACTORY_REGISTRY[1])
            else:
                continue
            decoded += 1
            print(
                f"DECODE OK | {d.event_name} | pool={d.pool.pool_address} "
                f"| token0={d.pool.token0} | token1={d.pool.token1} | fee={d.pool.fee}"
            )
        except Exception as exc:
            print(f"DECODE FAIL | tx={item.get('transactionHash')} | {exc}")

    if decoded == 0:
        raise RuntimeError("RPC returned logs, but none decoded successfully.")

    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 100,
            "method": "eth_subscribe",
            "params": ["logs", {
                "address": [x["factory"] for x in DEFAULT_FACTORY_REGISTRY],
                "topics": [[V2_PAIR_CREATED, V3_POOL_CREATED]],
            }],
        }))
        ack = json.loads(await ws.recv())
        if "error" in ack:
            raise RuntimeError(ack["error"])
        print(f"WebSocket factory subscription: OK | sub={ack['result']}")
        print("Leave this running for live validation; Ctrl+C to stop.")


if __name__ == "__main__":
    asyncio.run(main())
