from __future__ import annotations

import asyncio
import logging

from config import load_settings, validate_settings
from db import Database
from factory_discovery import backfill, live_factory_monitor
from router_monitor import monitor_router_blocks
from rpc import RpcClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def main():
    settings = load_settings()
    validate_settings(settings)

    rpc = RpcClient(settings.rpc_http_url)
    chain_id = int(await rpc.call("eth_chainId", []), 16)
    if chain_id != settings.chain_id:
        raise RuntimeError(f"RPC chain_id={chain_id}, configured={settings.chain_id}")

    latest = int(await rpc.call("eth_blockNumber", []), 16)
    db = Database(settings.db_path)
    await db.open()

    try:
        if settings.backfill_enabled:
            await backfill(
                db, rpc, settings.chain_id, settings.factory_registry,
                settings.backfill_start_block, latest, settings.backfill_chunk_size,
            )
        else:
            logging.info("Backfill disabled; eth_getLogs will NOT be called by startup.")

        tasks = [
            asyncio.create_task(
                live_factory_monitor(db, settings.rpc_ws_url, settings.chain_id, settings.factory_registry)
            )
        ]
        if settings.router_monitor_enabled:
            tasks.append(asyncio.create_task(
                monitor_router_blocks(
                    db, rpc, settings.rpc_ws_url, settings.chain_id, settings.router_registry
                )
            ))
        else:
            logging.info("Router monitoring disabled.")

        await asyncio.gather(*tasks)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
