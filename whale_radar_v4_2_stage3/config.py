from __future__ import annotations

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(".env", override=True)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _json(name: str, default):
    raw = os.getenv(name)
    if not raw:
        return default
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a JSON list")
    return value


@dataclass(frozen=True)
class Settings:
    rpc_http_url: str
    rpc_ws_url: str
    chain_id: int
    db_path: str
    backfill_enabled: bool
    backfill_start_block: int
    backfill_chunk_size: int
    router_monitor_enabled: bool
    router_poll_confirmations: int
    router_registry: list
    factory_registry: list


def load_settings() -> Settings:
    from constants import DEFAULT_FACTORY_REGISTRY, DEFAULT_ROUTER_REGISTRY

    return Settings(
        rpc_http_url=os.getenv("RPC_HTTP_URL", "").strip(),
        rpc_ws_url=os.getenv("RPC_WS_URL", "").strip(),
        chain_id=_int("CHAIN_ID", 1),
        db_path=os.getenv("DB_PATH", "whale_radar.db"),
        backfill_enabled=_bool("BACKFILL_ENABLED", False),
        backfill_start_block=_int("BACKFILL_START_BLOCK", 0),
        backfill_chunk_size=_int("BACKFILL_CHUNK_SIZE", 2000),
        router_monitor_enabled=_bool("ROUTER_MONITOR_ENABLED", False),
        router_poll_confirmations=_int("ROUTER_POLL_CONFIRMATIONS", 2),
        router_registry=_json("ROUTER_REGISTRY_JSON", DEFAULT_ROUTER_REGISTRY),
        factory_registry=_json("FACTORY_REGISTRY_JSON", DEFAULT_FACTORY_REGISTRY),
    )


def validate_settings(s: Settings) -> None:
    if not s.rpc_http_url.startswith(("http://", "https://")):
        raise ValueError("RPC_HTTP_URL must start with http:// or https://")
    if not s.rpc_ws_url.startswith(("ws://", "wss://")):
        raise ValueError("RPC_WS_URL must start with ws:// or wss://")
    if s.chain_id <= 0:
        raise ValueError("CHAIN_ID must be positive")
    if s.backfill_chunk_size <= 0:
        raise ValueError("BACKFILL_CHUNK_SIZE must be positive")
