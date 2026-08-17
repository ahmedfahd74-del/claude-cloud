"""Market Structure — the shared primitive for the institutional methodology.

Pure price-action structure per timeframe: fractal swing pivots labelled
HH / HL / LH / LL, then BOS (break of structure = continuation) and CHoCH
(change of character = reversal) from confirmed CLOSES through the protected
swing. Trend is derived from the BOS/CHoCH sequence, never an indicator.

Non-repainting: a pivot is confirmed `swing_len` bars after it prints, and
breaks are counted only on a bar close beyond the level. This is the ONE
structure engine Pine and Python share (Steps 2, 3 and 4 all read it).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .indicators import Bar


@dataclass(frozen=True)
class SwingPoint:
    price: float
    is_high: bool
    index: int              # bar index of the pivot itself
    confirm_index: int      # bar index where it became known
    label: str              # HH / HL / LH / LL (vs the prior same-type swing)


@dataclass(frozen=True)
class StructureEvent:
    kind: str               # BOS / CHoCH
    direction: int          # +1 up, -1 down
    price: float            # the broken swing level
    index: int              # bar index of the breaking close


@dataclass
class StructureState:
    trend: int = 0                          # +1 up, -1 down, 0 undecided
    last_event: StructureEvent | None = None
    protected_high: float | None = None     # swing high defended in an uptrend
    protected_low: float | None = None      # swing low defended in a downtrend
    last_high: float | None = None          # most recent confirmed swing high
    last_low: float | None = None           # most recent confirmed swing low
    swings: list[SwingPoint] = field(default_factory=list)
    events: list[StructureEvent] = field(default_factory=list)

    @property
    def trend_txt(self) -> str:
        return "BULL" if self.trend > 0 else "BEAR" if self.trend < 0 else "RANGE"

    def recent_event(self, kind: str | None, within: int, at_index: int) -> bool:
        """A BOS/CHoCH (of `kind`, or any) within `within` bars of `at_index`."""
        for ev in reversed(self.events):
            if at_index - ev.index > within:
                break
            if kind is None or ev.kind == kind:
                return True
        return False


def _fractal_pivots(bars: list[Bar], leg: int) -> list[tuple[int, int, float]]:
    """Confirmed fractal pivots as (pivot_index, confirm_index, price, is_high).

    A bar `leg` back is a swing high if it is the strict max of the surrounding
    2*leg+1 window (mirror for lows). Confirmed `leg` bars later — no repaint.
    """
    out: list[tuple[int, int, float, bool]] = []
    n = len(bars)
    for i in range(leg, n - leg):
        hi, lo = bars[i].high, bars[i].low
        is_high = all(bars[j].high <= hi for j in range(i - leg, i + leg + 1) if j != i)
        is_low = all(bars[j].low >= lo for j in range(i - leg, i + leg + 1) if j != i)
        if is_high:
            out.append((i, i + leg, hi, True))
        if is_low:
            out.append((i, i + leg, lo, False))
    out.sort(key=lambda t: (t[1], t[0]))
    return out


def analyze_structure(bars: list[Bar], swing_len: int = 3) -> StructureState:
    """Build the structure state from a timeframe's bars (oldest first)."""
    st = StructureState()
    if len(bars) < 2 * swing_len + 2:
        return st

    pivots = _fractal_pivots(bars, swing_len)
    prev_high: float | None = None
    prev_low: float | None = None
    # Walk pivots in confirmation order, labelling HH/HL/LH/LL.
    for (pi, ci, price, is_high) in pivots:
        if is_high:
            label = "HH" if prev_high is not None and price > prev_high else "LH"
            st.swings.append(SwingPoint(price, True, pi, ci, label))
            prev_high = price
            st.last_high = price
        else:
            label = "HL" if prev_low is not None and price > prev_low else "LL"
            st.swings.append(SwingPoint(price, False, pi, ci, label))
            prev_low = price
            st.last_low = price

    # Replay closes to detect BOS / CHoCH against the running protected swing.
    # protected_high/low track the last confirmed swing available at each bar.
    ph = pl = None
    ph_idx = pl_idx = -1
    swings_by_confirm = sorted(st.swings, key=lambda s: s.confirm_index)
    si = 0
    for i in range(len(bars)):
        while si < len(swings_by_confirm) and swings_by_confirm[si].confirm_index <= i:
            sp = swings_by_confirm[si]
            if sp.is_high:
                ph, ph_idx = sp.price, sp.index
            else:
                pl, pl_idx = sp.price, sp.index
            si += 1
        c = bars[i].close
        if ph is not None and c > ph and i > ph_idx:
            kind = "BOS" if st.trend >= 0 else "CHoCH"
            ev = StructureEvent(kind, 1, ph, i)
            st.events.append(ev)
            st.last_event = ev
            st.trend = 1
            st.protected_high = ph
            st.protected_low = pl
            ph = None            # consume the broken level; wait for next pivot
        elif pl is not None and c < pl and i > pl_idx:
            kind = "BOS" if st.trend <= 0 else "CHoCH"
            ev = StructureEvent(kind, -1, pl, i)
            st.events.append(ev)
            st.last_event = ev
            st.trend = -1
            st.protected_low = pl
            st.protected_high = ph
            pl = None
    return st


def swept(bars: list[Bar], i: int, level: float, is_high: bool,
          buffer: float) -> bool:
    """Liquidity sweep at bar i: wick pierces `level` by > buffer, body closes
    back inside (a stop-hunt, not a break)."""
    b = bars[i]
    if is_high:
        return b.high > level + buffer and b.close < level
    return b.low < level - buffer and b.close > level
