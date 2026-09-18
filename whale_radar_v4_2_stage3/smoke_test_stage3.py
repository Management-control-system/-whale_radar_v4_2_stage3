from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from rpc import RpcClient
from abi_decode import decode_v2_swap, decode_v3_swap
from constants import V2_SWAP, V3_SWAP, DEFAULT_ROUTER_REGISTRY


load_dotenv(".env", override=True)


async def main():
    url = os.getenv("RPC_HTTP_URL", "")
    if not url:
        raise SystemExit("RPC_HTTP_URL is missing")

    rpc = RpcClient(url)

    chain = int(await rpc.call("eth_chainId", []), 16)
    latest = int(await rpc.call("eth_blockNumber", []), 16)

    routers = {
        r["address"].lower(): r["name"]
        for r in DEFAULT_ROUTER_REGISTRY
    }

    print(
        f"HTTP RPC: OK | chain_id={chain} | latest_block={latest}"
    )

    found_v2 = False
    found_v3 = False

    checked_router_txs = 0
    blocks_checked = 0

    # Search the recent 25 blocks.
    for n in range(latest, max(-1, latest - 24), -1):
        block = await rpc.call(
            "eth_getBlockByNumber",
            [hex(n), True],
        )

        blocks_checked += 1

        for tx in block.get("transactions", []):
            router = routers.get(
                (tx.get("to") or "").lower()
            )

            if not router:
                continue

            checked_router_txs += 1

            receipt = await rpc.call(
                "eth_getTransactionReceipt",
                [tx["hash"]],
            )

            if not receipt:
                continue

            for item in receipt.get("logs", []):
                topics = item.get("topics") or []

                if not topics:
                    continue

                t0 = topics[0].lower()

                # -------------------------
                # V2
                # -------------------------
                if t0 == V2_SWAP and not found_v2:
                    d = decode_v2_swap(item, chain)

                    print(
                        "DECODE OK | V2 Swap "
                        f"| pool={d['pool_address']} "
                        f"| amount_in={d['amount_in']} "
                        f"| amount_out={d['amount_out']} "
                        f"| router={router}"
                    )

                    found_v2 = True

                # -------------------------
                # V3
                # -------------------------
                elif t0 == V3_SWAP and not found_v3:
                    d = decode_v3_swap(item, chain)

                    print(
                        "DECODE OK | V3 Swap "
                        f"| pool={d['pool_address']} "
                        f"| amount_in={d['amount_in']} "
                        f"| amount_out={d['amount_out']} "
                        f"| router={router}"
                    )

                    found_v3 = True

                # Stop only after BOTH have been verified.
                if found_v2 and found_v3:
                    print(
                        "SMOKE TEST OK | "
                        f"V2={found_v2} | "
                        f"V3={found_v3} | "
                        f"blocks_checked={blocks_checked} | "
                        f"router_txs_checked={checked_router_txs}"
                    )
                    return

    # -------------------------
    # Final status
    # -------------------------

    print(
        "SMOKE TEST INCOMPLETE | "
        f"V2={found_v2} | "
        f"V3={found_v3} | "
        f"blocks_checked={blocks_checked} | "
        f"router_txs_checked={checked_router_txs}"
    )

    if not found_v2:
        print("V2 Swap was not found in the recent router transactions.")

    if not found_v3:
        print("V3 Swap was not found in the recent router transactions.")


if __name__ == "__main__":
    asyncio.run(main())
