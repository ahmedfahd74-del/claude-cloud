"""Pure calculation primitives (Pine Sections 2-3 equivalents).

All functions take/return plain Python lists; warm-up bars are float('nan').
Loops are deliberate: they mirror Pine's per-bar semantics for parity testing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

NAN = float("nan")


@dataclass(frozen=True)
class Bar:
    ts: int          # bar OPEN time, epoch seconds (UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def isnan(x: float) -> bool:
    return x != x


def clamp(x: float, lo: float, hi: float) -> float:
    """Pine f_clamp."""
    return max(lo, min(hi, x))


def safe_div(a: float, b: float) -> float:
    """Pine f_div — 0.0 on zero/nan denominator."""
    if b == 0 or isnan(b):
        return 0.0
    return a / b


def norm01(v: float, k: float) -> float:
    """Pine f_norm01 — soft-scale v into 0..1 (k maps to ~0.5)."""
    if k == 0:
        return 0.0
    return clamp(v / (v + k), 0.0, 1.0)


def sma(values: list[float], length: int) -> list[float]:
    out = [NAN] * len(values)
    acc = 0.0
    n = 0
    for i, v in enumerate(values):
        if isnan(v):
            continue
        acc += v
        n += 1
        if n > length:
            # find value leaving the window (values are nan-free once started)
            acc -= values[i - length]
            n -= 1
        if n == length:
            out[i] = acc / length
    return out


def stdev(values: list[float], length: int) -> list[float]:
    """Population stdev over a rolling window (matches ta.stdev)."""
    out = [NAN] * len(values)
    for i in range(length - 1, len(values)):
        window = values[i - length + 1: i + 1]
        if any(isnan(v) for v in window):
            continue
        m = sum(window) / length
        out[i] = math.sqrt(sum((v - m) ** 2 for v in window) / length)
    return out


def ema(values: list[float], length: int) -> list[float]:
    out = [NAN] * len(values)
    alpha = 2.0 / (length + 1)
    prev = NAN
    for i, v in enumerate(values):
        if isnan(v):
            continue
        prev = v if isnan(prev) else alpha * v + (1 - alpha) * prev
        out[i] = prev
    return out


def rma(values: list[float], length: int) -> list[float]:
    """Wilder's moving average (Pine ta.rma), SMA-seeded like Pine."""
    out = [NAN] * len(values)
    prev = NAN
    acc = 0.0
    n = 0
    for i, v in enumerate(values):
        if isnan(v):
            continue
        if isnan(prev):
            acc += v
            n += 1
            if n == length:
                prev = acc / length
                out[i] = prev
            continue
        prev = (prev * (length - 1) + v) / length
        out[i] = prev
    return out


def true_range(bars: list[Bar]) -> list[float]:
    out = [NAN] * len(bars)
    for i, b in enumerate(bars):
        if i == 0:
            out[i] = b.high - b.low
        else:
            pc = bars[i - 1].close
            out[i] = max(b.high - b.low, abs(b.high - pc), abs(b.low - pc))
    return out


def atr(bars: list[Bar], length: int) -> list[float]:
    """Pine ta.atr — RMA of true range."""
    return rma(true_range(bars), length)
