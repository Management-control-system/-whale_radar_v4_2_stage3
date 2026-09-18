from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from models import EventIdentity, NormalizedTrade, PoolRecord


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS pools (
    chain_id INTEGER NOT NULL,
    pool_address TEXT NOT NULL,
    dex TEXT NOT NULL,
    version TEXT NOT NULL,
    token0 TEXT NOT NULL,
    token1 TEXT NOT NULL,
    fee INTEGER,
    tick_spacing INTEGER,
    factory_address TEXT,
    discovered_by TEXT NOT NULL,
    first_seen_block INTEGER,
    first_seen_block_hash TEXT,
    tx_hash TEXT,
    log_index INTEGER,
    metadata_json TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (chain_id, pool_address)
);

CREATE INDEX IF NOT EXISTS idx_pools_factory
ON pools(chain_id, factory_address);

CREATE INDEX IF NOT EXISTS idx_pools_tokens
ON pools(chain_id, token0, token1);

CREATE TABLE IF NOT EXISTS trades (
    event_key TEXT PRIMARY KEY,
    chain_id INTEGER NOT NULL,
    pool_address TEXT NOT NULL,
    dex TEXT NOT NULL,
    version TEXT NOT NULL,
    tx_hash TEXT NOT NULL,
    block_number INTEGER NOT NULL,
    block_hash TEXT NOT NULL,
    log_index INTEGER NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT,
    origin TEXT,
    token0 TEXT,
    token1 TEXT,
    amount0 TEXT NOT NULL,
    amount1 TEXT NOT NULL,
    token_in TEXT,
    token_out TEXT,
    amount_in TEXT,
    amount_out TEXT,
    raw_json TEXT NOT NULL,
    removed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_trades_pool ON trades(chain_id, pool_address);
CREATE INDEX IF NOT EXISTS idx_trades_sender ON trades(chain_id, sender);
CREATE INDEX IF NOT EXISTS idx_trades_block ON trades(chain_id, block_number);

CREATE TABLE IF NOT EXISTS events (
    event_key TEXT PRIMARY KEY,
    chain_id INTEGER NOT NULL,
    block_number INTEGER NOT NULL,
    block_hash TEXT NOT NULL,
    tx_hash TEXT NOT NULL,
    log_index INTEGER NOT NULL,
    address TEXT NOT NULL,
    topic0 TEXT NOT NULL,
    event_type TEXT NOT NULL,
    removed INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def open(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        await self.db.executescript(SCHEMA)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()
            self.db = None

    async def record_event(self, identity: EventIdentity, log_item: dict, event_type: str) -> bool:
        assert self.db is not None
        payload = json.dumps(log_item, separators=(",", ":"), sort_keys=True)
        cur = await self.db.execute(
            """INSERT INTO events
               (event_key, chain_id, block_number, block_hash, tx_hash, log_index,
                address, topic0, event_type, removed, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(event_key) DO UPDATE SET
                   removed=excluded.removed,
                   payload_json=excluded.payload_json,
                   event_type=excluded.event_type
               """,
            (
                identity.key(), identity.chain_id, identity.block_number,
                identity.block_hash, identity.tx_hash, identity.log_index,
                log_item["address"].lower(), log_item["topics"][0].lower(),
                event_type, 1 if log_item.get("removed") else 0, payload,
            ),
        )
        await self.db.commit()
        return cur.rowcount == 1 and not log_item.get("removed")

    async def upsert_pool(self, pool: PoolRecord):
        assert self.db is not None
        await self.db.execute(
            """INSERT INTO pools
            (chain_id, pool_address, dex, version, token0, token1, fee, tick_spacing,
             factory_address, discovered_by, first_seen_block, first_seen_block_hash,
             tx_hash, log_index, metadata_json, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(chain_id, pool_address) DO UPDATE SET
                dex=excluded.dex,
                version=excluded.version,
                token0=excluded.token0,
                token1=excluded.token1,
                fee=COALESCE(excluded.fee, pools.fee),
                tick_spacing=COALESCE(excluded.tick_spacing, pools.tick_spacing),
                factory_address=COALESCE(excluded.factory_address, pools.factory_address),
                discovered_by=CASE
                    WHEN instr(',' || pools.discovered_by || ',', ',' || excluded.discovered_by || ',') > 0
                        THEN pools.discovered_by
                    ELSE pools.discovered_by || ',' || excluded.discovered_by
                END,
                active=1
            """,
            (
                pool.chain_id, pool.pool_address.lower(), pool.dex, pool.version,
                pool.token0.lower(), pool.token1.lower(), pool.fee, pool.tick_spacing,
                pool.factory_address.lower() if pool.factory_address else None,
                pool.discovered_by, pool.first_seen_block, pool.first_seen_block_hash,
                pool.tx_hash, pool.log_index, pool.metadata_json,
            ),
        )
        await self.db.commit()

    async def get_pool(self, chain_id: int, pool_address: str):
        assert self.db is not None
        cur = await self.db.execute(
            "SELECT chain_id,pool_address,dex,version,token0,token1,fee,tick_spacing,discovered_by,active FROM pools WHERE chain_id=? AND pool_address=?",
            (chain_id, pool_address.lower()),
        )
        return await cur.fetchone()

    async def record_trade(self, trade: NormalizedTrade, removed: bool = False) -> bool:
        assert self.db is not None
        await self.db.execute(
            """INSERT INTO trades
            (event_key,chain_id,pool_address,dex,version,tx_hash,block_number,block_hash,log_index,
             sender,recipient,origin,token0,token1,amount0,amount1,token_in,token_out,amount_in,amount_out,raw_json,removed)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_key) DO UPDATE SET removed=excluded.removed, raw_json=excluded.raw_json""",
            (trade.event_key, trade.chain_id, trade.pool_address.lower(), trade.dex, trade.version,
             trade.tx_hash, trade.block_number, trade.block_hash, trade.log_index, trade.sender.lower(),
             trade.recipient.lower() if trade.recipient else None, trade.origin.lower() if trade.origin else None,
             trade.token0.lower() if trade.token0 else None, trade.token1.lower() if trade.token1 else None,
             str(trade.amount0), str(trade.amount1), trade.token_in.lower() if trade.token_in else None,
             trade.token_out.lower() if trade.token_out else None, str(trade.amount_in) if trade.amount_in is not None else None,
             str(trade.amount_out) if trade.amount_out is not None else None, trade.raw_json, 1 if removed else 0),
        )
        await self.db.commit()
        return not removed

    async def count_trades(self) -> int:
        assert self.db is not None
        cur = await self.db.execute("SELECT COUNT(*) FROM trades WHERE removed=0")
        row = await cur.fetchone()
        return int(row[0])

    async def mark_pool_inactive(self, chain_id: int, pool_address: str):
        assert self.db is not None
        await self.db.execute(
            "UPDATE pools SET active=0 WHERE chain_id=? AND pool_address=?",
            (chain_id, pool_address.lower()),
        )
        await self.db.commit()

    async def count_pools(self) -> int:
        assert self.db is not None
        cur = await self.db.execute("SELECT COUNT(*) FROM pools WHERE active=1")
        row = await cur.fetchone()
        return int(row[0])

    async def get_pools(self):
        assert self.db is not None
        cur = await self.db.execute(
            "SELECT chain_id,pool_address,dex,version,token0,token1,fee,tick_spacing,discovered_by,active FROM pools ORDER BY first_seen_block"
        )
        return await cur.fetchall()
