# Whale Radar V4.2 — Stage 3: Swap Decoder

Stage 3 turns raw Uniswap V2/V3 Swap logs into a normalized trade representation.

## Implemented
- V2 `Swap(address,uint256,uint256,uint256,uint256,address)` decoding.
- V3 `Swap(address,address,int256,int256,uint160,uint128,int24)` decoding.
- Correct V3 signed delta handling: positive delta is token input to the pool; negative delta is token output.
- Normalized trade model with event identity, sender, recipient, origin, token indexes/addresses, raw amounts, input/output amounts.
- SQLite `trades` table with deduplication and reorg `removed` state.
- Router monitor now persists decoded swaps instead of only storing discovery metadata.
- Unknown pools seen through router receipts remain discoverable and are stored conservatively until token metadata is resolved.

Uniswap's official V2 interface defines the six Swap fields including sender, four amount fields, and `to`; V3 defines sender, recipient, signed amount0/amount1, post-swap price/liquidity/tick. citeturn0search4turn0search1

## What is NOT in Stage 3
- token decimals/metadata RPC cache
- USD pricing
- wallet aggregation
- whale detection/confidence
- risk scoring
- Telegram alerts

Those come after the decoder is verified.

## Local checks
The fixture-shape tests require no RPC and validate the ABI word layout, including signed V3 values.

On your Windows machine, inside the V4.2 Stage 3 folder:

```bat
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest -q
```

## Live Mainnet check
After putting a newly rotated key in `.env`:

```bat
python smoke_test_stage3.py
```

Paste only the output. Never paste `RPC_HTTP_URL` or the API key.
