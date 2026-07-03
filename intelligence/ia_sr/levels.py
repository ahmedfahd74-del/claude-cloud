"""Level store + scoring — Pine Sections 7 + 9 port.

One LevelBook per timeframe. Geometry (merge radius, break buffer, confluence
band, EQH/EQL tolerance) scales with the level's OWN timeframe ATR, quality
eviction replaces FIFO, freshness horizon is TF-scaled and Keep-mode polarity
flips are applied — identical to the v1.0 Pine engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .indicators import Bar, clamp, norm01, safe_div
from .regime import RegimeState

# Pine Section 9 factor weights (sum = 1.0) — the learning engine's surface.
W_TOUCH = 0.16
W_REACT = 0.16
W_CONF = 0.24
W_TREND = 0.08
W_VOL = 0.06
W_FRESH = 0.10
W_SWEEP = 0.10
W_SMC = 0.10


@dataclass
class Level:
    price: float
    is_res: bool
    touches: int = 0
    react_sum: float = 0.0
    vol_sum: float = 0.0
    last_touch: int = 0       # base-bar index of last activity (also birth)
    score: float = 50.0
    sweeps: int = 0
    broken: bool = False


@dataclass
class LevelBook:
    tf: str
    weight: float             # Pine Store.w
    tf_minutes: float
    base_minutes: float
    max_levels: int = 6
    atr_tf: float = 0.0       # this TF's own ATR (kept current by caller)
    levels: list[Level] = field(default_factory=list)

    @property
    def fhor(self) -> float:
        """TF-scaled freshness horizon in base bars (Pine Store.fhor)."""
        return clamp(500.0 * self.tf_minutes / max(self.base_minutes, 1.0), 500.0, 5000.0)

    def _merge_dist(self, atr_safe: float, ad_merge: float) -> float:
        return max(atr_safe, self.atr_tf * 0.5) * ad_merge

    def add(self, price: float, is_res: bool, bar_index: int,
            atr_safe: float, ad_merge: float) -> None:
        """Pine f_addLevel: merge-dedupe, seed stats, quality eviction."""
        md = self._merge_dist(atr_safe, ad_merge)
        for lv in self.levels:
            if abs(lv.price - price) <= md:
                return
        self.levels.insert(0, Level(price=price, is_res=is_res, last_touch=bar_index))
        while len(self.levels) > self.max_levels:
            worst, ws = 1, 1.0e9
            for j in range(1, len(self.levels)):
                cs = self.levels[j].score - (100.0 if self.levels[j].broken else 0.0)
                if cs <= ws:
                    ws = cs
                    worst = j
            self.levels.pop(worst)

    def update_breaks(self, bar: Bar, prev_close: float, bar_index: int,
                      st: RegimeState, mode: str = "Keep") -> int:
        """Pine f_updateBreaks: TF-true buffer, debounced stats, polarity flip.

        Returns the number of counted break events this bar.
        """
        bc = 0
        for i in range(len(self.levels) - 1, -1, -1):
            lv = self.levels[i]
            if lv.broken:
                continue
            buf = max(st.atr_safe * 0.25, self.atr_tf * 0.15) * st.ad_atr
            crossed = (abs(bar.close - lv.price) > buf
                       and (bar.close - lv.price) * (prev_close - lv.price) < 0)
            if not crossed:
                continue
            if bar_index - lv.last_touch >= 3:
                bc += 1
                lv.last_touch = bar_index
            if mode == "Remove":
                self.levels.pop(i)
            elif mode == "Keep":
                lv.is_res = bar.close < lv.price   # institutional polarity flip
            else:  # Dim
                lv.broken = True
        return bc

    def update_touches(self, bar: Bar, bar_index: int, st: RegimeState) -> int:
        """Pine f_touchUpdate: debounced touch/reaction/volume/sweep stats."""
        hc = 0
        for lv in self.levels:
            if lv.broken:
                continue
            buf = st.atr_safe * st.ad_react
            if (bar.high >= lv.price - buf and bar.low <= lv.price + buf
                    and bar_index - lv.last_touch >= 3):
                rej = bar.high - bar.close if lv.is_res else bar.close - bar.low
                lv.touches += 1
                lv.react_sum += clamp(safe_div(rej, st.atr_fast), 0.0, 3.0)
                lv.vol_sum += st.vol_ratio
                lv.last_touch = bar_index
                hc += 1
                pierced = (bar.high > lv.price + buf and bar.close < lv.price) if lv.is_res \
                    else (bar.low < lv.price - buf and bar.close > lv.price)
                if pierced:
                    lv.sweeps += 1
        return hc

    def near_count(self, price: float, band: float) -> int:
        """Pine f_nearCount."""
        return sum(1 for lv in self.levels if abs(lv.price - price) <= band)

    def score_levels(self, others: list["LevelBook"], bar_index: int,
                     st: RegimeState, smc_bonus) -> None:
        """Pine f_scoreAndRender scoring half (no rendering)."""
        atr_ref = max(st.atr_safe, self.atr_tf * 0.5)
        band = atr_ref * st.ad_merge * 1.5
        for i, lv in enumerate(self.levels):
            if lv.broken:
                continue
            t = lv.touches
            avg_react = lv.react_sum / t if t > 0 else 0.0
            avg_vol = lv.vol_sum / t if t > 0 else 0.0
            recency = bar_index - lv.last_touch
            conf = sum(o.weight * o.near_count(lv.price, band) for o in others)
            aligned = (not st.trend_up) if lv.is_res else st.trend_up
            eq_count = sum(1 for j, o in enumerate(self.levels)
                           if j != i and o.is_res == lv.is_res
                           and abs(o.price - lv.price) <= atr_ref * 0.2)
            raw = (W_TOUCH * norm01(t, 3)
                   + W_REACT * norm01(avg_react, 1.0)
                   + W_CONF * norm01(conf, 2.0)
                   + W_TREND * ((1.0 if aligned else 0.35) if st.is_trending else 0.6)
                   + W_VOL * norm01(avg_vol, 1.0)
                   + W_FRESH * clamp(1.0 - recency / self.fhor, 0.0, 1.0)
                   + W_SWEEP * norm01(lv.sweeps, 2)
                   + W_SMC * clamp(smc_bonus(lv.price) + norm01(eq_count, 1) * 0.5, 0.0, 1.0))
            lv.score = clamp(100.0 * raw * (0.6 + 0.4 * self.weight), 0.0, 100.0)


def nearest(books: list[LevelBook], px: float) -> tuple[float, float, float, float]:
    """Pine f_nearest → (dist_above, score_above, dist_below, score_below)."""
    d_above = d_below = 1.0e9
    s_above = s_below = 0.0
    for book in books:
        for lv in book.levels:
            if lv.broken:
                continue
            if lv.price >= px:
                if lv.price - px < d_above:
                    d_above, s_above = lv.price - px, lv.score
            elif px - lv.price < d_below:
                d_below, s_below = px - lv.price, lv.score
    return d_above, s_above, d_below, s_below


def gather(books: list[LevelBook], px: float, direction: int) -> list[float]:
    """Pine f_gather: unbroken levels strictly above (+1) / below (-1), nearest-first."""
    arr = [lv.price for book in books for lv in book.levels
           if not lv.broken and (lv.price > px if direction == 1 else lv.price < px)]
    arr.sort(reverse=(direction == -1))
    return arr
