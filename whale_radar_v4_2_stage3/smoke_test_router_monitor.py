from __future__ import annotations

import asyncio
from pathlib import Path

from config import load_settings, validate_settings
from db import Database
from rpc import RpcClient
from router_monitor import process_router_receipt


BLOCKS_TO_SCAN = 20
MAX_ROUTER_TXS_PER_BLOCK = 20
TARGET_SWAPS = 2


def hex_to_int(value: str) -> int:
    return int(value, 16)


async def get_latest_block(rpc: RpcClient) -> int:
    value = await rpc.call("eth_blockNumber", [])
    return hex_to_int(value)


async def get_full_block(
    rpc: RpcClient,
    block_number: int,
) -> dict:
    return await rpc.call(
        "eth_getBlockByNumber",
        [hex(block_number), True],
    )


async def get_receipt(
    rpc: RpcClient,
    tx_hash: str,
) -> dict | None:
    return await rpc.call(
        "eth_getTransactionReceipt",
        [tx_hash],
    )


async def main() -> None:

    print()
    print("==============================================")
    print(" WHALE RADAR V4.2 - ROUTER MONITOR SMOKE TEST")
    print("==============================================")
    print()

    settings = load_settings()
    validate_settings(settings)

    chain_id = settings.chain_id

    print(f"CHAIN | {chain_id}")
    print("RPC HTTP | configured")
    print("RPC WS   | configured")
    print()

    routers = settings.router_registry

    print("ROUTERS |")

    for router in routers:
        print(
            f"  - {router['name']} | "
            f"{router['address']}"
        )

    print()

    router_addresses = {
        router["address"].lower(): router["name"]
        for router in routers
    }

    rpc = RpcClient(settings.rpc_http_url)

    db = Database(Path(settings.db_path))
    await db.init()

    latest_block = await get_latest_block(rpc)

    first_block = max(
        0,
        latest_block - BLOCKS_TO_SCAN + 1,
    )

    print(
        f"SCAN | blocks {first_block} -> {latest_block}"
    )
    print()

    router_transactions = 0
    receipts_checked = 0
    swaps_found = 0

    successful_transactions = []

    for block_number in range(
        first_block,
        latest_block + 1,
    ):

        print(f"BLOCK | {block_number}")

        block = await get_full_block(
            rpc,
            block_number,
        )

        if not block:
            print("  BLOCK DATA | unavailable")
            continue

        transactions = block.get("transactions", [])

        block_router_txs = 0

        for tx in transactions:

            if block_router_txs >= MAX_ROUTER_TXS_PER_BLOCK:
                break

            tx_to = (tx.get("to") or "").lower()

            if not tx_to:
                continue

            router_name = router_addresses.get(tx_to)

            if router_name is None:
                continue

            block_router_txs += 1
            router_transactions += 1

            tx_hash = tx["hash"]

            print()
            print("  ROUTER TX FOUND")
            print(f"    router | {router_name}")
            print(f"    tx     | {tx_hash}")
            print(f"    from   | {tx.get('from')}")
            print(f"    block  | {block_number}")

            receipt = await get_receipt(
                rpc,
                tx_hash,
            )

            receipts_checked += 1

            if not receipt:
                print("    RECEIPT | unavailable")
                continue

            logs = receipt.get("logs", [])

            print(
                f"    RECEIPT | "
                f"status={receipt.get('status')} | "
                f"logs={len(logs)}"
            )

            before_trades = await db.count_trades()

            found = await process_router_receipt(
                db=db,
                chain_id=chain_id,
                receipt=receipt,
                router_name=router_name,
                origin=tx.get("from"),
            )

            after_trades = await db.count_trades()

            print(
                f"    SWAPS FOUND | {found}"
            )

            if found > 0:

                swaps_found += found

                successful_transactions.append(
                    (
                        router_name,
                        tx_hash,
                        block_number,
                        found,
                    )
                )

                print(
                    "    RESULT | SWAP DETECTED"
                )

                print(
                    f"    DB TRADES | "
                    f"{before_trades} -> {after_trades}"
                )

                if swaps_found >= TARGET_SWAPS:
                    print()
                    print(
                        f"TARGET REACHED | "
                        f"{swaps_found} swaps"
                    )
                    break

            else:

                print(
                    "    RESULT | "
                    "no V2/V3 Swap logs"
                )

        print(
            f"  ROUTER TXS IN BLOCK | "
            f"{block_router_txs}"
        )

        if swaps_found >= TARGET_SWAPS:
            break

    print()
    print("==============================================")
    print(" SUMMARY")
    print("==============================================")

    print(
        f"BLOCKS SCANNED       | "
        f"{first_block} -> {latest_block}"
    )

    print(
        f"ROUTER TX FOUND      | "
        f"{router_transactions}"
    )

    print(
        f"RECEIPTS CHECKED     | "
        f"{receipts_checked}"
    )

    print(
        f"SWAPS FOUND          | "
        f"{swaps_found}"
    )

    print()

    if successful_transactions:

        print("SUCCESSFUL SWAP TRANSACTIONS")
        print("----------------------------------------------")

        for (
            router_name,
            tx_hash,
            block_number,
            found,
        ) in successful_transactions:

            print(
                f"router={router_name} | "
                f"block={block_number} | "
                f"swaps={found} | "
                f"tx={tx_hash}"
            )

        print()
        print("ROUTER MONITOR SMOKE TEST | PASS")

    else:

        print(
            "ROUTER MONITOR SMOKE TEST | "
            "NO SWAP FOUND"
        )

        print()
        print(
            f"Current BLOCKS_TO_SCAN = "
            f"{BLOCKS_TO_SCAN}"
        )

        print(
            "If necessary, increase it to 100."
        )


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print()
        print("TEST INTERRUPTED")

    except Exception as exc:

        print()
        print("==============================================")
        print(" TEST FAILED")
        print("==============================================")

        print(
            f"{type(exc).__name__}: {exc}"
        )

        raise