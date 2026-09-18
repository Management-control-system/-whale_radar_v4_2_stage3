from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

from abi_decode import decode_v2_swap, decode_v3_swap
from constants import V2_SWAP, V3_SWAP
from db import Database
from models import EventIdentity, NormalizedTrade, PoolRecord
from rpc import RpcClient

log = logging.getLogger(__name__)


def _hex_int(v: Any) -> int:
    return int(v, 16) if isinstance(v, str) else int(v)


def _topic0(item: dict) -> str:
    return item["topics"][0].lower()


async def process_router_receipt(
    db: Database,
    chain_id: int,
    receipt: dict[str, Any],
    router_name: str,
    origin: str | None = None,
) -> int:
    """Decode and persist normalized V2/V3 swaps from a router transaction."""
    found = 0
    for item in receipt.get("logs", []):
        topic0 = _topic0(item)
        if topic0 not in {V2_SWAP, V3_SWAP}:
            continue

        if topic0 == V2_SWAP:
            decoded = decode_v2_swap(item, chain_id)
            version = "v2"
            amount0 = decoded["amount0_in"] - decoded["amount0_out"]
            amount1 = decoded["amount1_in"] - decoded["amount1_out"]
        else:
            decoded = decode_v3_swap(item, chain_id)
            version = "v3"
            amount0 = decoded["amount0"]
            amount1 = decoded["amount1"]

        pool_address = decoded["pool_address"]
        pool_row = await db.get_pool(chain_id, pool_address)
        dex = pool_row[2] if pool_row else "unknown"
        token0 = pool_row[4] if pool_row and pool_row[4] != "0x0000000000000000000000000000000000000000" else None
        token1 = pool_row[5] if pool_row and pool_row[5] != "0x0000000000000000000000000000000000000000" else None
        token_in = token0 if decoded["token_in_index"] == 0 else token1
        token_out = token0 if decoded["token_out_index"] == 0 else token1

        trade = NormalizedTrade(
            chain_id=chain_id, pool_address=pool_address, dex=dex, version=version,
            tx_hash=decoded["tx_hash"], block_number=decoded["block_number"], block_hash=decoded["block_hash"],
            log_index=decoded["log_index"], sender=decoded["sender"], recipient=decoded["recipient"],
            origin=origin, token0=token0, token1=token1, amount0=amount0, amount1=amount1,
            token_in=token_in, token_out=token_out, amount_in=decoded["amount_in"],
            amount_out=decoded["amount_out"], raw_json=json.dumps(decoded, default=str, separators=(",", ":")),
        )
        identity = EventIdentity(
            chain_id=chain_id, block_number=decoded["block_number"], block_hash=decoded["block_hash"],
            tx_hash=decoded["tx_hash"], log_index=decoded["log_index"],
        )
        await db.record_event(identity, item, f"{version}_swap")
        await db.record_trade(trade, removed=bool(item.get("removed")))

        # Secondary pool discovery if the router touched an unknown pool.
        if pool_row is None:
            pool = PoolRecord(
                chain_id=chain_id, pool_address=pool_address, dex="unknown", version=version,
                token0="0x0000000000000000000000000000000000000000",
                token1="0x0000000000000000000000000000000000000000",
                discovered_by=f"router:{router_name}", first_seen_block=decoded["block_number"],
                first_seen_block_hash=decoded["block_hash"], tx_hash=decoded["tx_hash"],
                log_index=decoded["log_index"],
                metadata_json=json.dumps({"router": router_name}, separators=(",", ":")),
            )
            await db.upsert_pool(pool)
            log.info("Router secondary discovery: pool=%s version=%s router=%s", pool_address, version, router_name)

        found += 1
    return found


async def monitor_router_blocks(
    db: Database,
    rpc: RpcClient,
    rpc_ws_url: str,
    chain_id: int,
    routers: list[dict],
):
    router_map = {r["address"].lower(): r["name"] for r in routers}
    while True:
        try:
            async with websockets.connect(rpc_ws_url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({
                    "jsonrpc": "2.0", "id": 2, "method": "eth_subscribe",
                    "params": ["newHeads"],
                }))
                ack = json.loads(await ws.recv())
                if "error" in ack:
                    raise RuntimeError(ack["error"])
                log.info("Router block monitor active: %s", ack["result"])

                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("method") != "eth_subscription":
                        continue
                    header = msg.get("params", {}).get("result")
                    if not header:
                        continue
                    block_number = header["number"]
                    block = await rpc.call("eth_getBlockByNumber", [block_number, True])
                    for tx in block.get("transactions", []):
                        to = (tx.get("to") or "").lower()
                        router_name = router_map.get(to)
                        if not router_name:
                            continue
                        try:
                            receipt = await rpc.call("eth_getTransactionReceipt", [tx["hash"]])
                            if receipt:
                                await process_router_receipt(db, chain_id, receipt, router_name, tx.get("from"))
                        except Exception:
                            log.exception("Router receipt processing failed for tx=%s", tx["hash"])
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Router monitor disconnected; reconnecting in 5s")
            await asyncio.sleep(5)
