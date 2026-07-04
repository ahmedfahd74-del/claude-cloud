"""Scan configuration: timeframes, weights and the default symbol universe."""
from __future__ import annotations

from dataclasses import dataclass, field

# Timeframe registry: key -> (minutes, level-book weight). Weights mirror the
# Pine stores; 1m/30m extend the Pine set as Python-only resolution.
TIMEFRAMES: dict[str, tuple[float, float]] = {
    "1M": (43200, 1.00),
    "1w": (10080, 1.00),
    "1d": (1440, 0.80),
    "4h": (240, 0.60),
    "1h": (60, 0.45),
    "30m": (30, 0.40),
    "15m": (15, 0.35),
    "5m": (5, 0.30),
    "1m": (1, 0.25),
}

# Default scan universe. Feed adapters map these to their own tickers.
DEFAULT_SYMBOLS = [
    # forex majors + crosses
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY",
    # crypto
    "BTCUSD", "ETHUSD", "SOLUSD",
    # commodities
    "XAUUSD", "XAGUSD", "WTIUSD",
    # indices
    "SPX500", "NAS100", "GER40",
]


@dataclass
class ScanConfig:
    symbols: list[str] = field(default_factory=lambda: list(DEFAULT_SYMBOLS))
    base_tf: str = "1h"                      # the "chart" the engine replays
    level_tfs: list[str] = field(default_factory=lambda: ["1w", "1d", "4h", "1h", "15m", "5m"])
    history_bars: int = 600                  # base bars replayed per symbol
    min_prob: float = 65.0
    min_rr: float = 2.0
    min_sr_conf: float = 60.0
    account_risk_pct: float = 1.0
    top_n: int = 10
    max_levels_per_tf: int = 8
    sens_bias: float = 1.0
    engine_mode: str = "Adaptive (Auto)"     # or Conservative/Balanced/Aggressive/Ultra Aggressive
    htf_only: bool = True                    # drop level TFs below the base TF (Pine v2.0.7 default)
    power_radius: float = 8.0                # Power Line search radius (daily ATR)
    power_min_score: float = 60.0
    power_trend_side: bool = True
    power_side_bias: float = 1.6

    def tf_minutes(self, tf: str) -> float:
        return TIMEFRAMES[tf][0]

    def tf_weight(self, tf: str) -> float:
        return TIMEFRAMES[tf][1]
