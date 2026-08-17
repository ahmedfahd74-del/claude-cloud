# Retired validators

These test modules or logic that **no longer exist** in `level_core_v2.pine`.
They still pass in isolation, which is exactly why they were moved here — a
passing test for deleted code is false confidence, not coverage.

| File | Tested | Removed by |
|---|---|---|
| `location_engine_validate.py` | the price-relative `nearest swing >= close` lookup for the auction range | replaced by the latched dealing range — see `../dealing_range_validate.py` |
| `level_core_v2_entry_validate.py` | Entry Engine (M4) liquidity-sweep signals | Step 1: decision layers cut out of the S/R engine |
| `trade_card_validate.py` | Trade Card GO/NO-GO + risk sizing | Step 1 |
| `market_context_validate.py` | Market Context Engine (external leader/tide direction) | Step 1 |

Kept for reference only. Do not treat a pass here as coverage of the current engine.
