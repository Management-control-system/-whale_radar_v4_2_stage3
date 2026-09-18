"""Protocol constants for stage 1+2 (Ethereum mainnet).

Addresses are kept in config/registry so coverage is explicit rather than
claiming that every DEX/router is automatically covered.
"""

CHAIN_ID = 1

UNISWAP_V2_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
UNISWAP_V2_ROUTER02 = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

UNISWAP_V3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
UNISWAP_V3_SWAP_ROUTER02 = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"

# Current Uniswap Universal Router deployments on Ethereum mainnet.
UNISWAP_UNIVERSAL_ROUTER_V1 = "0xEf1c6E67703c7BD7107eed8303Fbe6EC2554BF6B"
UNISWAP_UNIVERSAL_ROUTER_V1_2 = "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
UNISWAP_UNIVERSAL_ROUTER_V2 = "0x66a9893cc07d91d95644aedd05d03f95e1dba8af"
UNISWAP_UNIVERSAL_ROUTER_V2_1_1 = "0x4C82D1fBFe28C977cBB58D8C7FF8FCF9F70a2cCA"

V2_PAIR_CREATED = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"
V3_POOL_CREATED = "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118"

V2_SWAP = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
V3_SWAP = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"

DEFAULT_FACTORY_REGISTRY = [
    {
        "dex": "uniswap_v2",
        "version": "v2",
        "factory": UNISWAP_V2_FACTORY,
        "event": "pair",
        "topic0": V2_PAIR_CREATED,
    },
    {
        "dex": "uniswap_v3",
        "version": "v3",
        "factory": UNISWAP_V3_FACTORY,
        "event": "pool",
        "topic0": V3_POOL_CREATED,
    },
]

DEFAULT_ROUTER_REGISTRY = [
    {"name": "uniswap_v2_router02", "address": UNISWAP_V2_ROUTER02},
    {"name": "uniswap_v3_swaprouter02", "address": UNISWAP_V3_SWAP_ROUTER02},
    {"name": "uniswap_universal_router_v1", "address": UNISWAP_UNIVERSAL_ROUTER_V1},
    {"name": "uniswap_universal_router_v1_2", "address": UNISWAP_UNIVERSAL_ROUTER_V1_2},
    {"name": "uniswap_universal_router_v2", "address": UNISWAP_UNIVERSAL_ROUTER_V2},
    {"name": "uniswap_universal_router_v2_1_1", "address": UNISWAP_UNIVERSAL_ROUTER_V2_1_1},
]

# Minimal ABI fragments. get_event_data MUST receive Web3().codec.
V2_PAIR_CREATED_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "token0", "type": "address"},
        {"indexed": True, "internalType": "address", "name": "token1", "type": "address"},
        {"indexed": False, "internalType": "address", "name": "pair", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "", "type": "uint256"},
    ],
    "name": "PairCreated",
    "type": "event",
}

V3_POOL_CREATED_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "token0", "type": "address"},
        {"indexed": True, "internalType": "address", "name": "token1", "type": "address"},
        {"indexed": True, "internalType": "uint24", "name": "fee", "type": "uint24"},
        {"indexed": False, "internalType": "int24", "name": "tickSpacing", "type": "int24"},
        {"indexed": False, "internalType": "address", "name": "pool", "type": "address"},
    ],
    "name": "PoolCreated",
    "type": "event",
}

V2_SWAP_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "amount0In", "type": "uint256"},
        {"indexed": False, "internalType": "uint256", "name": "amount1In", "type": "uint256"},
        {"indexed": False, "internalType": "uint256", "name": "amount0Out", "type": "uint256"},
        {"indexed": False, "internalType": "uint256", "name": "amount1Out", "type": "uint256"},
        {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
    ],
    "name": "Swap",
    "type": "event",
}

V3_SWAP_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
        {"indexed": True, "internalType": "address", "name": "recipient", "type": "address"},
        {"indexed": False, "internalType": "int256", "name": "amount0", "type": "int256"},
        {"indexed": False, "internalType": "int256", "name": "amount1", "type": "int256"},
        {"indexed": False, "internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
        {"indexed": False, "internalType": "uint128", "name": "liquidity", "type": "uint128"},
        {"indexed": False, "internalType": "int24", "name": "tick", "type": "int24"},
    ],
    "name": "Swap",
    "type": "event",
}
