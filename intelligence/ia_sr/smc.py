"""Liquidity / SMC engine — Pine Section 8 port.

Unfilled fair value gaps (3-bar imbalance) and the most recent order block per
side, tracked over confirmed bars. Feeds the level-score SMC bonus and the
probability engine's OB/FVG proximity terms.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .indicators import Bar
from .regime import RegimeState


@dataclass
class FVG:
    top: float
    bottom: float
    bull: bool


@dataclass
class SMCState:
    fvgs: list[FVG] = field(default_factory=list)
    ob_bull: tuple[float, float] | None = None   # (top, bottom)
    ob_bear: tuple[float, float] | None = None

    def update(self, bars: list[Bar], i: int, st: RegimeState) -> None:
        """Process bar i (uses offsets [1..3] like Pine's confirmed-bar logic)."""
        if i >= 3:
            b1, b3 = bars[i - 1], bars[i - 3]
            bull_fvg = b1.low > b3.high
            bear_fvg = b1.high < b3.low
            if bull_fvg or bear_fvg:
                top = b1.low if bull_fvg else b3.low
                bot = b3.high if bull_fvg else b1.high
                self.fvgs.insert(0, FVG(top, bot, bull_fvg))
                del self.fvgs[30:]
        bar = bars[i]
        self.fvgs = [f for f in self.fvgs
                     if not (bar.low <= f.bottom if f.bull else bar.high >= f.top)]
        if i >= 2:
            b1, b2 = bars[i - 1], bars[i - 2]
            disp = abs(b1.close - b1.open) > st.atr_safe * 1.2
            if disp and b1.close > b1.open and b2.close < b2.open:
                self.ob_bull = (b2.high, b2.low)
            if disp and b1.close < b1.open and b2.close > b2.open:
                self.ob_bear = (b2.high, b2.low)

    def bonus(self, price: float) -> float:
        """Pine f_smcBonus — 0..1 footprint strength at a price."""
        b = 0.0
        for f in self.fvgs:
            if f.bottom <= price <= f.top:
                b = max(b, 0.6)
                break
        if self.ob_bull and self.ob_bull[1] <= price <= self.ob_bull[0]:
            b = max(b, 0.7)
        if self.ob_bear and self.ob_bear[1] <= price <= self.ob_bear[0]:
            b = max(b, 0.7)
        return b

    def near_flags(self, bar: Bar) -> tuple[bool, bool, bool, bool]:
        """(ob_bull_near, ob_bear_near, fvg_bull_near, fvg_bear_near) at a bar."""
        obu = bool(self.ob_bull and bar.low <= self.ob_bull[0] and bar.high >= self.ob_bull[1])
        obd = bool(self.ob_bear and bar.low <= self.ob_bear[0] and bar.high >= self.ob_bear[1])
        fbu = fbd = False
        for f in self.fvgs:
            if f.bottom <= bar.close <= f.top:
                if f.bull:
                    fbu = True
                else:
                    fbd = True
                break
        return obu, obd, fbu, fbd
