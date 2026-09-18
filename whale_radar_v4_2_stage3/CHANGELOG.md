# V4.2 Stage 1+2

- Fixed factory event decoding to use `Web3().codec`.
- Fixed the V3 identifier regression: `V3_POOL_CREATED`.
- Decode failures are logged instead of silently returning `None`.
- Added event identity and SQLite deduplication.
- Added explicit reorg `removed=true` handling.
- Added V2/V3 factory live monitoring.
- Added bounded optional factory backfill.
- Added router-targeted transaction monitoring via block receipts.
- Added real Ethereum mainnet Etherscan fixtures for V2/V3 factory events.
