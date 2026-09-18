from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PoolRecord:
    chain_id: int
    pool_address: str
    dex: str
    version: str
    token0: str
    token1: str
    fee: int | None = None
    tick_spacing: int | None = None
    factory_address: str | None = None
    discovered_by: str = "factory"
    first_seen_block: int | None = None
    first_seen_block_hash: str | None = None
    tx_hash: str | None = None
    log_index: int | None = None
    metadata_json: str | None = None


@dataclass(frozen=True)
class EventIdentity:
    chain_id: int
    block_number: int
    block_hash: str
    tx_hash: str
    log_index: int

    def key(self) -> str:
        return f"{self.chain_id}:{self.block_number}:{self.block_hash.lower()}:{self.tx_hash.lower()}:{self.log_index}"


@dataclass(frozen=True)
class DecodedFactoryEvent:
    pool: PoolRecord
    event_name: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class NormalizedTrade:
    chain_id: int
    pool_address: str
    dex: str
    version: str
    tx_hash: str
    block_number: int
    block_hash: str
    log_index: int
    sender: str
    recipient: str | None
    origin: str | None
    token0: str | None
    token1: str | None
    amount0: int
    amount1: int
    token_in: str | None
    token_out: str | None
    amount_in: int | None
    amount_out: int | None
    raw_json: str

    @property
    def event_key(self) -> str:
        return EventIdentity(
            self.chain_id, self.block_number, self.block_hash, self.tx_hash, self.log_index
        ).key()
