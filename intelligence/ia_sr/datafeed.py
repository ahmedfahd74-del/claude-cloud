"""Pluggable OHLCV feeds.

SyntheticFeed generates seeded regime-shifting random walks and aggregates
them to every timeframe — deterministic, offline, used by tests and demos.
YFinanceFeed maps the scan universe to Yahoo tickers (optional dependency).
"""
from __future__ import annotations

import math
import random
from typing import Protocol

from .config import TIMEFRAMES
from .indicators import Bar


class Feed(Protocol):
    def bars(self, symbol: str, tf: str, limit: int) -> list[Bar]:
        """Return up to `limit` most-recent bars, oldest first."""
        ...


def aggregate(bars: list[Bar], minutes: float) -> list[Bar]:
    """Aggregate finer bars into `minutes` buckets (bucket = ts // period)."""
    period = int(minutes * 60)
    out: list[Bar] = []
    cur: list[Bar] = []
    cur_bucket = None
    for b in bars:
        bucket = b.ts // period
        if cur_bucket is not None and bucket != cur_bucket:
            out.append(_merge(cur, cur_bucket * period))
            cur = []
        cur_bucket = bucket
        cur.append(b)
    if cur:
        out.append(_merge(cur, cur_bucket * period))
    return out


def _merge(bs: list[Bar], ts: int) -> Bar:
    return Bar(ts=ts, open=bs[0].open, high=max(b.high for b in bs),
               low=min(b.low for b in bs), close=bs[-1].close,
               volume=sum(b.volume for b in bs))


class SyntheticFeed:
    """Deterministic per-symbol random walk with trend/range/shock regimes."""

    def __init__(self, base_minutes: float = 5, total_bars: int = 40000, t0: int = 1_700_000_000):
        self.base_minutes = base_minutes
        self.total_bars = total_bars
        self.t0 = t0
        self._cache: dict[str, list[Bar]] = {}

    def _base(self, symbol: str) -> list[Bar]:
        if symbol in self._cache:
            return self._cache[symbol]
        rng = random.Random(symbol)
        price = 100.0 * (1 + rng.random())
        anchor = price          # long-run anchor: reversion stops the walk from
        drift = 0.0             # collapsing to ~0 (volatility drag) or exploding
        vol = 0.002
        bars: list[Bar] = []
        step = int(self.base_minutes * 60)
        for i in range(self.total_bars):
            if i % 500 == 0:  # regime shift
                drift = rng.choice([-1, 0, 0, 1]) * vol * 0.35
                vol = 0.002 * (0.5 + rng.random() * 2.0)
            o = price
            rev = 0.002 * math.log(anchor / price) if price > 0 else 0.0
            moves = [rng.gauss(drift + rev, vol) for _ in range(4)]
            path = [o]
            for m in moves:
                path.append(path[-1] * (1 + m))
            c = path[-1]
            hi = max(path) * (1 + abs(rng.gauss(0, vol * 0.3)))
            lo = min(path) * (1 - abs(rng.gauss(0, vol * 0.3)))
            v = abs(rng.gauss(1000, 400)) * (2.0 if abs(c - o) > vol * o else 1.0)
            bars.append(Bar(self.t0 + i * step, o, hi, lo, c, v))
            price = c
        self._cache[symbol] = bars
        return bars

    def bars(self, symbol: str, tf: str, limit: int) -> list[Bar]:
        minutes = TIMEFRAMES[tf][0]
        base = self._base(symbol)
        agg = base if minutes == self.base_minutes else aggregate(base, minutes)
        return agg[-limit:]


# Yahoo Finance ticker mapping for the default universe.
YF_TICKERS = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X", "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD", "SOLUSD": "SOL-USD",
    "XAUUSD": "GC=F", "XAGUSD": "SI=F", "WTIUSD": "CL=F",
    "SPX500": "^GSPC", "NAS100": "^NDX", "GER40": "^GDAXI",
}

_YF_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1h": "1h", "4h": "1h", "1d": "1d", "1w": "1wk", "1M": "1mo"}
_YF_PERIOD = {"1m": "5d", "5m": "1mo", "15m": "1mo", "30m": "1mo",
              "1h": "2y", "4h": "2y", "1d": "5y", "1w": "10y", "1M": "max"}


class YFinanceFeed:
    """Live market data via yfinance (pip install yfinance). 4h is built by
    aggregating 1h — Yahoo has no native 4h interval."""

    def __init__(self):
        import yfinance  # noqa: F401 — fail fast if missing
        self._yf = yfinance
        self._cache: dict[tuple[str, str], list[Bar]] = {}

    def bars(self, symbol: str, tf: str, limit: int) -> list[Bar]:
        key = (symbol, tf)
        if key not in self._cache:
            ticker = YF_TICKERS.get(symbol, symbol)
            df = self._yf.Ticker(ticker).history(
                period=_YF_PERIOD[tf], interval=_YF_INTERVAL[tf],
                auto_adjust=False)
            bars = [Bar(int(ts.timestamp()), float(r["Open"]), float(r["High"]),
                        float(r["Low"]), float(r["Close"]),
                        float(r.get("Volume", 0.0) or 0.0))
                    for ts, r in df.iterrows()]
            if tf == "4h":
                bars = aggregate(bars, 240)
            self._cache[key] = bars
        return self._cache[key][-limit:]
