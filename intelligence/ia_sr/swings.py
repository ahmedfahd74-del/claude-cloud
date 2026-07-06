"""Swing Engine — Pine Section 5 port.

Adaptive-leg pivot detector: the bar `leg` bars back is a swing if it is the
extreme of the [i-2*leg .. i] window. A swing is confirmed `leg` bars after it
prints — no future data, no repaint.

STABILITY CONTRACT (V3 hardening): a swing's IDENTITY is always the wick
extreme — the exact price institutions defend. The candle's body edge is
carried alongside as `body` purely so the display layer can anchor the drawn
line to wick / mid / body WITHOUT changing the level's identity, score, merge
behaviour or ranking. Detection never blends the anchor into the price.
"""
from __future__ import annotations

from dataclasses import dataclass

from .indicators import Bar
from .regime import RegimeState


@dataclass(frozen=True)
class Swing:
    price: float         # IDENTITY = wick extreme (frozen, anchor-independent)
    is_high: bool
    pivot_index: int     # bar index of the swing itself
    confirm_index: int   # bar index where it became known
    confirm_ts: int      # epoch seconds when it became known (bar CLOSE time)
    body: float = 0.0    # body edge of the pivot candle (display anchor only)


def detect_swings(bars: list[Bar], regimes: list[RegimeState],
                  tf_seconds: int) -> list[Swing]:
    """Confirmed swings. `price` is always the wick extreme; `body` is the
    same-side body edge (open/close) for optional display anchoring."""
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
            out.append(Swing(hv, True, p, i, confirm_ts, body_hi))
        if is_low:
            out.append(Swing(lv, False, p, i, confirm_ts, body_lo))
    return out
