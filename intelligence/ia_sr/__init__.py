"""IA-SR Institutional Intelligence Layer.

Python port of the Pine `IA-SR` engine (pine/sr_engine.pine) plus the
capabilities Pine cannot host: market-wide scanning, opportunity ranking,
portfolio exposure control and performance-based calibration.

Layering mirrors the Pine file section-for-section so the two runtimes can be
parity-tested against each other:

    indicators.py    Pine Section 2-3 primitives (ATR/EMA/SMA/stdev)
    regime.py        Sections 3-4  adaptive engine + parameter emission
    swings.py        Section 5     adaptive-leg swing detector
    levels.py        Sections 7+9  level book, TF-true geometry, scoring
    smc.py           Section 8     FVG / order blocks
    decision.py      Section 10    market state + decision metrics
    probability.py   Section 11    weighted evidence -> probability/quality
    plan.py          Section 14    trade plan + validation gates
    analysis.py      per-symbol MTF orchestration (the "chart" replay)
    scanner.py       multi-symbol scan + ranking + signal filtering
    portfolio.py     exposure/correlation control
    learning.py      outcome store + bucketed calibration
    datafeed.py      pluggable OHLCV feeds (synthetic / yfinance)
    webhook.py       stdlib receiver for the Pine JSON export (SSOT audit)
"""

__version__ = "0.1.0"
