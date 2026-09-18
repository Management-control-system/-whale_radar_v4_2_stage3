from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

from abi_decode import decode_v2_pair_created, decode_v3_pool_created
from constants import V2_PAIR_CREATED, V3_POOL_CREATED
from db import Database
from models import EventIdentity
from rpc import RpcClient

log = logging.getLogger(__name__)


def _hex_int(value: Any) -> int:
    return int(value, 16) if isinstance(value, str) else int(value)


def _identity(chain_id: int, item: dict[str, Any]) -> EventIdentity:
    return EventIdentity(
        chain_id=chain_id,
        block_number=_hex_int(item["blockNumber"]),
        block_hash=item["blockHash"],
        tx_hash=item["transactionHash"],
        log_index=_hex_int(item["logIndex"]),
    )


def _pool_address_from_factory_log(
    item: dict[str, Any],
    factory: dict[str, Any],
) -> str | None:
    """
    Best-effort extraction of the pool address from a factory creation event.

    V2 PairCreated:
        pool/pair is a non-indexed event argument in data.

    V3 PoolCreated:
        pool is an indexed event argument.
    """
    try:
        if factory["event"] == "pool":
            # PoolCreated(address indexed token0, address indexed token1,
            #             uint24 indexed fee, int24 tickSpacing,
            #             address pool)
            #
            # topics:
            # [topic0, token0, token1, fee]
            #
            # The pool address is in the decoded data, so use the existing
            # decoder rather than manually parsing ABI bytes.
            decoded = decode_v3_pool_created(
                item,
                chain_id=1,
                factory=factory,
            )
            return decoded.pool.pool_address

        if factory["event"] == "pair":
            decoded = decode_v2_pair_created(
                item,
                chain_id=1,
                factory=factory,
            )
            return decoded.pool.pool_address

    except Exception:
        log.exception(
            "Could not extract pool address from removed factory log: "
            "tx=%s logIndex=%s",
            item.get("transactionHash"),
            item.get("logIndex"),
        )

    return None


async def process_factory_log_async(
    db: Database,
    chain_id: int,
    item: dict[str, Any],
    registry: list[dict],
) -> bool:
    topics = item.get("topics") or []
    if not topics:
        return False

    address = item["address"].lower()
    topic0 = topics[0].lower()

    factory = next(
        (
            f
            for f in registry
            if f["factory"].lower() == address
            and f["topic0"].lower() == topic0
        ),
        None,
    )

    if not factory:
        return False

    identity = _identity(chain_id, item)

    if item.get("removed"):
        inserted = await db.record_event(
            identity,
            item,
            "factory_removed",
        )

        pool_address = _pool_address_from_factory_log(
            item,
            factory,
        )

        if pool_address:
            await db.mark_pool_inactive(
                chain_id,
                pool_address,
            )

        log.warning(
            "Factory log removed by reorg: %s pool=%s",
            identity.key(),
            pool_address,
        )

        return inserted

    if factory["event"] == "pair":
        decoded = decode_v2_pair_created(
            item,
            chain_id,
            factory,
        )

    elif factory["event"] == "pool":
        decoded = decode_v3_pool_created(
            item,
            chain_id,
            factory,
        )

    else:
        raise ValueError(
            f"Unsupported factory event type: {factory['event']}"
        )

    inserted = await db.record_event(
        identity,
        item,
        decoded.event_name,
    )

    if inserted:
        await db.upsert_pool(decoded.pool)

        log.info(
            "Pool discovered: dex=%s version=%s pool=%s "
            "token0=%s token1=%s fee=%s",
            decoded.pool.dex,
            decoded.pool.version,
            decoded.pool.pool_address,
            decoded.pool.token0,
            decoded.pool.token1,
            decoded.pool.fee,
        )

    return inserted


async def _get_factory_logs_adaptive(
    rpc: RpcClient,
    factory: dict[str, Any],
    start_block: int,
    end_block: int,
    min_chunk_size: int = 1,
) -> list[dict[str, Any]]:
    """
    Query eth_getLogs with automatic range reduction.

    If the RPC provider rejects a block range, split it in half and retry.
    This is particularly useful for providers that impose getLogs limits.
    """

    if end_block < start_block:
        return []

    params = [
        {
            "address": [factory["factory"]],
            "topics": [[factory["topic0"]]],
            "fromBlock": hex(start_block),
            "toBlock": hex(end_block),
        }
    ]

    try:
        return await rpc.call(
            "eth_getLogs",
            params,
        )

    except Exception as exc:
        span = end_block - start_block + 1

        if span <= min_chunk_size:
            log.exception(
                "eth_getLogs failed at minimum range: "
                "dex=%s blocks=%s-%s",
                factory["dex"],
                start_block,
                end_block,
            )
            raise

        midpoint = start_block + (span // 2) - 1

        log.warning(
            "eth_getLogs rejected range; splitting: "
            "dex=%s blocks=%s-%s span=%s -> %s-%s and %s-%s "
            "error=%s",
            factory["dex"],
            start_block,
            end_block,
            span,
            start_block,
            midpoint,
            midpoint + 1,
            end_block,
            exc,
        )

        left_logs = await _get_factory_logs_adaptive(
            rpc,
            factory,
            start_block,
            midpoint,
            min_chunk_size,
        )

        right_logs = await _get_factory_logs_adaptive(
            rpc,
            factory,
            midpoint + 1,
            end_block,
            min_chunk_size,
        )

        return left_logs + right_logs


async def backfill(
    db: Database,
    rpc: RpcClient,
    chain_id: int,
    registry: list[dict],
    start_block: int,
    end_block: int,
    chunk_size: int,
):
    if end_block < start_block:
        return

    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")

    for factory in registry:
        cursor = start_block

        while cursor <= end_block:
            stop = min(
                cursor + chunk_size - 1,
                end_block,
            )

            logs = await _get_factory_logs_adaptive(
                rpc,
                factory,
                cursor,
                stop,
            )

            log.info(
                "Factory backfill: %s blocks=%s-%s logs=%s",
                factory["dex"],
                cursor,
                stop,
                len(logs),
            )

            for item in logs:
                await process_factory_log_async(
                    db,
                    chain_id,
                    item,
                    registry,
                )

            cursor = stop + 1


async def live_factory_monitor(
    db: Database,
    rpc_ws_url: str,
    chain_id: int,
    registry: list[dict],
):
    sub_id = None

    while True:
        try:
            async with websockets.connect(
                rpc_ws_url,
                ping_interval=20,
                ping_timeout=20,
            ) as ws:
                params = [
                    {
                        "address": [
                            f["factory"]
                            for f in registry
                        ],
                        "topics": [
                            [
                                V2_PAIR_CREATED,
                                V3_POOL_CREATED,
                            ]
                        ],
                    }
                ]

                await ws.send(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "eth_subscribe",
                            "params": [
                                "logs",
                                params,
                            ],
                        }
                    )
                )

                ack = json.loads(
                    await ws.recv()
                )

                if "error" in ack:
                    raise RuntimeError(
                        ack["error"]
                    )

                sub_id = ack["result"]

                log.info(
                    "Factory log subscription active: %s",
                    sub_id,
                )

                while True:
                    message = json.loads(
                        await ws.recv()
                    )

                    if (
                        message.get("method")
                        != "eth_subscription"
                    ):
                        continue

                    result = (
                        message
                        .get("params", {})
                        .get("result")
                    )

                    if not result:
                        continue

                    try:
                        await process_factory_log_async(
                            db,
                            chain_id,
                            result,
                            registry,
                        )

                    except Exception:
                        # One malformed log must not kill the
                        # WebSocket loop.
                        log.exception(
                            "Factory log processing failed; "
                            "subscription stays alive"
                        )

        except asyncio.CancelledError:
            raise

        except Exception:
            log.exception(
                "Factory monitor disconnected; "
                "reconnecting in 5s"
            )

            await asyncio.sleep(5)