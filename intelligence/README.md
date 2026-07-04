# IA-SR Intelligence Layer (Python)

The brain of the two-layer institutional platform. Pine (`pine/sr_engine.pine`,
**v2.0.9, FROZEN**) is the execution + visualization terminal for the open
chart; this package is everything Pine cannot do: market-wide scanning,
1m→Weekly multi-timeframe analysis, opportunity ranking, portfolio exposure
control and performance-based calibration. Pure stdlib — no required
dependencies; `yfinance` is optional for live data.

Parity status: level engine matches frozen Pine v2.0.9 — touch gravity,
extreme-snap merge-refine, structural-extreme eviction guard, break-quality
mass, prev-period extreme levels (PDH/PDL/PWH/PWL/PMH/PML), HTF-only store
gating, adaptive-first mode system (Kaufman-ER `autoStrict`), Power Line v2.1
(daily-ATR distances, 4H+ candidate floor, trend-side launch preference,
status intelligence) and unmitigated liquidity sweep pools.

## Quick start

```bash
cd intelligence

# offline demo scan (deterministic synthetic data)
python -m ia_sr scan

# live market scan (pip install yfinance)
python -m ia_sr scan --feed yfinance --symbols EURUSD,XAUUSD,BTCUSD

# INSTITUTIONAL SESSION REPORT — Tier A/B trades, Power Line, probability,
# entry/stop/targets, R:R, evidence, portfolio exposure, calibration, parity
python -m ia_sr report --feed yfinance --out report.html

# WATCHLIST DASHBOARD — auto-rescanning web page (dark institutional theme)
python -m ia_sr dashboard --feed yfinance --port 8899 --interval 300

# CONTINUOUS LIVE LOOP — scan → record signals → resolve outcomes → report
python -m ia_sr live --feed yfinance --interval 900 --out report.html

# settle open signals against fresh bars → updates calibration
python -m ia_sr resolve --feed yfinance

# expected vs realised win rate per probability bucket
python -m ia_sr calibration

# receive the Pine Section-16 JSON export (TradingView alert webhook → POST /pine)
# every payload is stored raw + parsed for parity verification (GET /health to test)
python -m ia_sr webhook --port 8787

# tests
python -m unittest discover -s tests
```

## Pine → Python webhook (parity + learning)

1. In TradingView, enable **Data Export → Emit JSON decision alert** on the
   frozen IA-SR v2.0.9 indicator.
2. Create an alert on the indicator with *Any alert() function call* and set
   the webhook URL to `http://<your-host>:8787/pine`.
3. Run `python -m ia_sr webhook`. Every bar-close decision (bias, probability,
   tier, plan, Power Line) lands in SQLite — the session report's
   **Pine Parity** section then compares the latest Pine state against the
   Python scan per symbol and flags divergence.

## Swapping in a professional data source

The entire stack talks to one protocol — `Feed.bars(symbol, tf, limit)` in
`ia_sr/datafeed.py`. To replace yfinance with a professional real-time
provider (Polygon, Databento, a broker API, …):

1. Write one class with that method returning closed `Bar`s, oldest first.
2. Register it: `FEEDS["polygon"] = PolygonFeed`.
3. Use `--feed polygon` everywhere. Nothing else in the system changes.


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
