"""Swing Engine — Pine Section 5 port.

Adaptive-leg pivot detector: the bar `leg` bars back is a swing if it is the
extreme of the [i-2*leg .. i] window. A swing is confirmed `leg` bars after it
prints — no future data, no repaint. The returned level is anchored between
wick and body per `anchor` (0=wick, 0.5=wick/body mid, 1=body edge).
"""
from __future__ import annotations

from dataclasses import dataclass

from .indicators import Bar
from .regime import RegimeState


@dataclass(frozen=True)
class Swing:
    price: float
    is_high: bool
    pivot_index: int     # bar index of the swing itself
    confirm_index: int   # bar index where it became known
    confirm_ts: int      # epoch seconds when it became known (bar CLOSE time)


def detect_swings(bars: list[Bar], regimes: list[RegimeState], tf_seconds: int,
                  anchor: float = 0.0) -> list[Swing]:
    out: list[Swing] = []
    for i in range(len(bars)):
        leg = regimes[i].leg
        p = i - leg
        if p < 0:
            continue
        lo_bound = max(0, i - 2 * leg)
        hv = bars[p].high
        lv = bars[p].low
        is_high = True
        is_low = True
        for j in range(lo_bound, i + 1):
            if j == p:
                continue
            if bars[j].high > hv:
                is_high = False
            if bars[j].low < lv:
                is_low = False
            if not is_high and not is_low:
                break
        body_hi = max(bars[p].open, bars[p].close)
        body_lo = min(bars[p].open, bars[p].close)
        confirm_ts = bars[i].ts + tf_seconds
        if is_high:
            out.append(Swing(hv * (1 - anchor) + body_hi * anchor, True, p, i, confirm_ts))
        if is_low:
            out.append(Swing(lv * (1 - anchor) + body_lo * anchor, False, p, i, confirm_ts))
    return out
