# IA-SR Intelligence Layer (Python)

The brain of the two-layer institutional platform. Pine (`pine/sr_engine.pine`,
v1.0, feature-complete) is the execution + visualization terminal for the open
chart; this package is everything Pine cannot do: market-wide scanning,
1m→Weekly multi-timeframe analysis, opportunity ranking, portfolio exposure
control and performance-based calibration. Pure stdlib — no required
dependencies; `yfinance` is optional for live data.

## Quick start

```bash
cd intelligence

# offline demo scan (deterministic synthetic data)
python -m ia_sr scan

# live market scan (pip install yfinance)
python -m ia_sr scan --feed yfinance --symbols EURUSD,XAUUSD,BTCUSD

# settle open signals against fresh bars → updates calibration
python -m ia_sr resolve --feed yfinance

# expected vs realised win rate per probability bucket
python -m ia_sr calibration

# receive the Pine Section-16 JSON export (TradingView alert webhook → POST /pine)
python -m ia_sr webhook --port 8787

# tests
python -m unittest discover -s tests
```

## How it maps to Pine (parity contract)

Every engine module is a section-for-section port of `pine/sr_engine.pine` —
same formulas, same weights, same gates (see `ia_sr/__init__.py` for the map).
The Pine JSON export is the single source of truth for any open chart; stored
payloads (webhook) are the parity dataset. When Pine and Python disagree on a
chart Pine is watching, Pine wins and the gap is a Python calibration bug.

## Workflow

1. `scan` runs the full engine on every symbol and ranks opportunities.
2. The signal filter keeps only directional, High-Quality+ setups above the
   probability floor; the portfolio controller then rejects correlated or
   over-budget entries.
3. Validated plans are recorded in SQLite; `resolve` settles them using the
   same lifecycle as the Pine trade journal (fill window, stop-first race,
   timeout) and feeds the calibration buckets.
4. `calibrate()` shrinks future probabilities toward realised win rates once
   a bucket has ≥20 samples — the learning loop.
5. You open the top-ranked chart in TradingView, where the Pine terminal
   produces the authoritative trade plan.
