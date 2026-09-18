from __future__ import annotations

import logging
from typing import Any

from web3 import Web3
from web3._utils.events import get_event_data

from constants import (
    V2_PAIR_CREATED_ABI,
    V2_SWAP_ABI,
    V3_POOL_CREATED_ABI,
    V3_SWAP_ABI,
)
from models import DecodedFactoryEvent, PoolRecord

log = logging.getLogger(__name__)

_DECODER = Web3().codec


def _topic0(log_item: dict[str, Any]) -> str:
    topics = log_item.get("topics") or []
    if not topics:
        raise ValueError("log has no topics")
    return topics[0].lower()


def decode_event(log_item: dict[str, Any], abi: dict) -> dict[str, Any]:
    """Decode one log. Crucially, get_event_data receives Web3().codec."""
    try:
        return dict(get_event_data(_DECODER, abi, log_item))
    except Exception:
        log.exception(
            "Failed to decode event: address=%s topic0=%s tx=%s logIndex=%s",
            log_item.get("address"),
            _topic0(log_item) if log_item.get("topics") else None,
            log_item.get("transactionHash"),
            log_item.get("logIndex"),
        )
        raise


def _addr(v: Any) -> str:
    return Web3.to_checksum_address(v)


def decode_v2_pair_created(log_item: dict[str, Any], chain_id: int, factory: dict) -> DecodedFactoryEvent:
    event = decode_event(log_item, V2_PAIR_CREATED_ABI)
    args = event["args"]
    pool = PoolRecord(
        chain_id=chain_id,
        pool_address=_addr(args["pair"]),
        dex=factory["dex"],
        version="v2",
        token0=_addr(args["token0"]),
        token1=_addr(args["token1"]),
        factory_address=_addr(log_item["address"]),
        discovered_by="factory",
        first_seen_block=int(log_item["blockNumber"], 16) if isinstance(log_item["blockNumber"], str) else int(log_item["blockNumber"]),
        first_seen_block_hash=log_item.get("blockHash"),
        tx_hash=log_item.get("transactionHash"),
        log_index=int(log_item["logIndex"], 16) if isinstance(log_item["logIndex"], str) else int(log_item["logIndex"]),
    )
    return DecodedFactoryEvent(pool=pool, event_name="PairCreated", raw=event)


def decode_v3_pool_created(log_item: dict[str, Any], chain_id: int, factory: dict) -> DecodedFactoryEvent:
    event = decode_event(log_item, V3_POOL_CREATED_ABI)
    args = event["args"]
    pool = PoolRecord(
        chain_id=chain_id,
        pool_address=_addr(args["pool"]),
        dex=factory["dex"],
        version="v3",
        token0=_addr(args["token0"]),
        token1=_addr(args["token1"]),
        fee=int(args["fee"]),
        tick_spacing=int(args["tickSpacing"]),
        factory_address=_addr(log_item["address"]),
        discovered_by="factory",
        first_seen_block=int(log_item["blockNumber"], 16) if isinstance(log_item["blockNumber"], str) else int(log_item["blockNumber"]),
        first_seen_block_hash=log_item.get("blockHash"),
        tx_hash=log_item.get("transactionHash"),
        log_index=int(log_item["logIndex"], 16) if isinstance(log_item["logIndex"], str) else int(log_item["logIndex"]),
    )
    return DecodedFactoryEvent(pool=pool, event_name="PoolCreated", raw=event)


def _hex_int(v: Any) -> int:
    return int(v, 16) if isinstance(v, str) else int(v)


def _normalize_common(log_item: dict[str, Any], chain_id: int) -> dict[str, Any]:
    return {
        "chain_id": chain_id,
        "pool_address": _addr(log_item["address"]),
        "tx_hash": log_item["transactionHash"],
        "block_number": _hex_int(log_item["blockNumber"]),
        "block_hash": log_item["blockHash"],
        "log_index": _hex_int(log_item["logIndex"]),
    }


def decode_v2_swap(log_item: dict[str, Any], chain_id: int | None = None) -> dict[str, Any]:
    event = decode_event(log_item, V2_SWAP_ABI)
    args = event["args"]
    result = {
        **(_normalize_common(log_item, chain_id) if chain_id is not None else {}),
        "event_name": "Swap",
        "version": "v2",
        "sender": _addr(args["sender"]),
        "recipient": _addr(args["to"]),
        "amount0_in": int(args["amount0In"]),
        "amount1_in": int(args["amount1In"]),
        "amount0_out": int(args["amount0Out"]),
        "amount1_out": int(args["amount1Out"]),
    }
    if result["amount0_in"] > 0:
        result.update({"token_in_index": 0, "amount_in": result["amount0_in"], "token_out_index": 1, "amount_out": result["amount1_out"]})
    elif result["amount1_in"] > 0:
        result.update({"token_in_index": 1, "amount_in": result["amount1_in"], "token_out_index": 0, "amount_out": result["amount0_out"]})
    else:
        raise ValueError("Invalid V2 Swap: neither amount0In nor amount1In is positive")
    return result


def decode_v3_swap(log_item: dict[str, Any], chain_id: int | None = None) -> dict[str, Any]:
    event = decode_event(log_item, V3_SWAP_ABI)
    args = event["args"]
    amount0 = int(args["amount0"])
    amount1 = int(args["amount1"])
    if amount0 == 0 and amount1 == 0:
        raise ValueError("Invalid V3 Swap: both token deltas are zero")
    result = {
        **(_normalize_common(log_item, chain_id) if chain_id is not None else {}),
        "event_name": "Swap",
        "version": "v3",
        "sender": _addr(args["sender"]),
        "recipient": _addr(args["recipient"]),
        "amount0": amount0,
        "amount1": amount1,
        "sqrtPriceX96": int(args["sqrtPriceX96"]),
        "liquidity": int(args["liquidity"]),
        "tick": int(args["tick"]),
    }
    # V3 Swap amounts are pool balance deltas: positive = input to pool, negative = output.
    if amount0 > 0:
        result.update({"token_in_index": 0, "amount_in": amount0, "token_out_index": 1, "amount_out": -amount1 if amount1 < 0 else 0})
    elif amount1 > 0:
        result.update({"token_in_index": 1, "amount_in": amount1, "token_out_index": 0, "amount_out": -amount0 if amount0 < 0 else 0})
    else:
        raise ValueError("Invalid V3 Swap: neither token delta is positive")
    return result
