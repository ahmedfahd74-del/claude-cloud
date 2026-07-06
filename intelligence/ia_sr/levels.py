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
    price: float              # IDENTITY = wick extreme, FROZEN at birth — never
                              # reassigned. This is what makes a level the same
                              # institutional object on every timeframe.
    is_res: bool
    body: float = 0.0         # origin-candle body edge (display anchor ONLY)
    touches: float = 0.0      # GRAVITY-WEIGHTED touch mass (prox × rejection × momentum)
    react_sum: float = 0.0
    vol_sum: float = 0.0
    birth: int = 0            # bar index the level was confirmed (immutable)
    last_touch: int = 0       # base-bar index of last activity
    score: float = 50.0
    sweeps: int = 0
    breaks: int = 0           # break-quality mass: clean close-through=2, wick=1
    broken: bool = False

    def display_price(self, anchor: float = 0.0) -> float:
        """Where the line is DRAWN: wick (0) → mid (0.5) → body (1). Purely
        visual — identity `price` is unchanged, so anchor cannot alter which
        levels exist, their scores, ranking or confluence."""
        return self.price * (1.0 - anchor) + self.body * anchor

    @property
    def proven(self) -> bool:
        """A confirmed institutional level that must not be evicted by the cap
        (only intentional invalidation removes it)."""
        return self.touches >= 1.0 or self.score >= 60.0


@dataclass
class LevelBook:
    tf: str
    weight: float             # Pine Store.w
    tf_minutes: float
    base_minutes: float
    max_levels: int = 8
    atr_tf: float = 0.0       # this TF's own ATR (kept current by caller)
    noise: float = 0.5        # measured tape wickiness 0..1 (V3 self-adaptive:
                              # hot/wicky tape widens merge, break and reaction
                              # geometry automatically — crypto vs FX vs indices
                              # differ with NO settings change)
    levels: list[Level] = field(default_factory=list)

    @property
    def _adapt(self) -> float:
        """Noise-driven geometry multiplier. REVERTED to 1.0 (neutral): the
        self-adaptive-geometry experiment regressed the ablation vs V2's fixed
        geometry, so it is disabled pending a formulation that measures better.
        The `noise` field is still populated for the Power Line / diagnostics."""
        return 1.0

    @property
    def fhor(self) -> float:
        """TF-scaled freshness horizon in base bars (Pine Store.fhor)."""
        return clamp(500.0 * self.tf_minutes / max(self.base_minutes, 1.0), 500.0, 5000.0)

    MERGE_FRAC = 0.5             # merge radius as a fraction of the level's TF ATR

    def _merge_dist(self, atr_safe: float, ad_merge: float) -> float:
        """TF-STABLE merge radius. Depends ONLY on this level's own timeframe
        ATR — never the varying base-bar ATR or per-bar regime multiplier — so
        whether two swings are the same institutional object is deterministic
        and identical on every timeframe that reads the book. (atr_safe is the
        fallback before the TF ATR is known.)"""
        base = self.atr_tf if self.atr_tf > 0 else atr_safe
        return base * self.MERGE_FRAC

    def add(self, price: float, is_res: bool, bar_index: int,
            atr_safe: float, ad_merge: float, body: float | None = None) -> None:
        """Add a confirmed level: merge-dedupe (evidence only — NEVER moves an
        existing level's price), else create it with a FROZEN identity price,
        then enforce the cap deterministically.

        A same-side swing inside the merge radius of an existing level is the
        SAME institutional object: it adds touch evidence, it does not create,
        move, or duplicate a level. This is the core of cross-timeframe parity.
        """
        body = price if body is None else body
        md = self._merge_dist(atr_safe, ad_merge)
        for lv in self.levels:
            if abs(lv.price - price) <= md:
                if lv.is_res == is_res and not lv.broken:
                    lv.touches += 0.5             # evidence only — price FROZEN
                    lv.last_touch = bar_index
                return
        self.levels.insert(0, Level(price=price, is_res=is_res, body=body,
                                    birth=bar_index, last_touch=bar_index))
        self._enforce_cap()

    def _enforce_cap(self) -> None:
        """Deterministic, protective eviction. Confirmed 'proven' levels and the
        structural extremes are never removed under the normal cap — only a
        broken or unproven level goes, chosen by an EXPLICIT total order
        (broken-first, then lowest score, then lowest price) so the same inputs
        always evict the same level. A hard ceiling (3× cap) is the only thing
        that can retire a proven level, keeping memory bounded without letting
        levels vanish non-deterministically."""
        while len(self.levels) > self.max_levels:
            idx = self._evict_index()
            if idx is None:
                break
            self.levels.pop(idx)

    def _evict_index(self) -> int | None:
        n = len(self.levels)
        if n <= 1:
            return None
        hi_idx = lo_idx = -1
        hi_p, lo_p = -1.0e18, 1.0e18
        for j, lv in enumerate(self.levels):
            if not lv.broken:
                if lv.price > hi_p:
                    hi_p, hi_idx = lv.price, j
                if lv.price < lo_p:
                    lo_p, lo_idx = lv.price, j
        protected = {0, hi_idx, lo_idx}
        over_hard = n > self.max_levels * 3
        cands = [j for j in range(1, n)
                 if j not in protected
                 and (over_hard or self.levels[j].broken or not self.levels[j].proven)]
        if not cands:
            return None
        return min(cands, key=lambda j: (0 if self.levels[j].broken else 1,
                                         self.levels[j].score, self.levels[j].price))

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
            buf = max(st.atr_safe * 0.25, self.atr_tf * 0.15) * st.ad_atr * self._adapt
            crossed = (abs(bar.close - lv.price) > buf
                       and (bar.close - lv.price) * (prev_close - lv.price) < 0)
            if not crossed:
                continue
            if bar_index - lv.last_touch >= 3:
                bc += 1
                lv.last_touch = bar_index
                # Break quality: decisive close-through (2) vs marginal/wick (1).
                lv.breaks += 2 if safe_div(abs(bar.close - lv.price), st.atr_fast) > 0.6 else 1
            if mode == "Remove":
                self.levels.pop(i)
            elif mode == "Keep":
                lv.is_res = bar.close < lv.price   # institutional polarity flip
            else:  # Dim
                lv.broken = True
        return bc

    def update_touches(self, bar: Bar, bar_index: int, st: RegimeState,
                       mom_x: float = 1.0) -> int:
        """Pine f_touchUpdate (v2 TOUCH GRAVITY): every interaction adds
        weighted touch mass — proximity (near-misses are partial touches) ×
        rejection strength × momentum at interaction. Debounced by 3 bars.
        """
        hc = 0
        for lv in self.levels:
            if lv.broken:
                continue
            buf = st.atr_safe * st.ad_react * self._adapt
            hit = bar.high >= lv.price - buf and bar.low <= lv.price + buf
            dist = min(abs(bar.high - lv.price), abs(bar.low - lv.price))
            near = not hit and dist <= buf * 2.0
            if (hit or near) and bar_index - lv.last_touch >= 3:
                rej = bar.high - bar.close if lv.is_res else bar.close - bar.low
                react = clamp(safe_div(rej, st.atr_fast), 0.0, 3.0)
                prox = 1.0 if hit else clamp(1.0 - (dist - buf) / buf, 0.2, 0.6)
                tw = prox * (1.0 + 0.5 * clamp(react, 0.0, 1.0)) * (0.75 + 0.25 * mom_x)
                lv.touches += tw
                lv.react_sum += react * (1.0 if hit else 0.4)
                lv.vol_sum += st.vol_ratio * prox
                lv.last_touch = bar_index
                if hit:
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
            sc = clamp(100.0 * raw * (0.6 + 0.4 * self.weight), 0.0, 100.0)
            # Lifecycle break penalty — clean breaks hurt most (Pine parity).
            lv.score = sc * clamp(1.0 - 0.12 * min(lv.breaks, 3), 0.5, 1.0)


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


@dataclass
class PowerLine:
    """Pine POWER LINE v2.1: the single institutional level that matters."""
    price: float
    score: float
    is_res: bool
    dist_atr: float           # distance in DAILY ATR (chart-TF independent)
    status: str               # RETEST LIKELY / BROKEN / BREAK LIKELY / RESPECT EXPECTED / HOLDING


def _cluster_mass(books: list[LevelBook], price: float, band: float) -> float:
    """Confluence mass at a price: TF-weighted scores of every unbroken level
    within `band`. THE institutional signal — many timeframes defending one
    price = the level that controls the market."""
    m = 0.0
    for book in books:
        for lv in book.levels:
            if not lv.broken and abs(lv.price - price) <= band:
                m += lv.score * (0.6 + 0.4 * book.weight)
    return m


def power_pick(books: list[LevelBook], close: float, p_atr: float,
               htf_bull: bool, htf_bear: bool, mom: float,
               base_minutes: float, radius: float = 8.0, min_sc: float = 60.0,
               trend_side: bool = True, side_bias: float = 1.6,
               pools: list[tuple[float, bool]] | None = None,
               bar_index: int = 0) -> PowerLine | None:
    """V3 INSTITUTIONAL POWER LINE — the market's line of truth.

    Candidates: institutional TFs only (4H+ or the base TF if higher), so the
    pick is identical on every chart. Rank blends:
      · proximity (inverse-distance — where price is doing business)
      · squared TF importance (Weekly outranks 4H)
      · CLUSTER MASS (confluence: all books' levels stacked at that price)
      · liquidity-pool confluence (an unmitigated sweep pool at the level)
      · reaction recency (recently defended > stale)
      · trend-side preference (bull → the launch level below price)
    Falls back to the nearest live candidate when nothing sits in the radius.
    """
    floor = max(240.0, base_minutes)
    best_rank = -1.0
    best: Level | None = None
    fn: Level | None = None
    fn_d = 1.0e18
    band = 0.25 * p_atr
    for book in books:
        if book.tf_minutes < floor:
            continue
        for lv in book.levels:
            if lv.broken:
                continue
            d = safe_div(abs(close - lv.price), p_atr)
            if d < fn_d:
                fn_d, fn = d, lv
            if d > radius:
                continue
            prox = 1.0 / (0.30 + d)
            tfw = (0.55 + 0.45 * book.weight) ** 2
            scw = (0.85 + 0.15 * clamp(lv.score / 100.0, 0.0, 1.0)) * (1.0 if lv.score >= min_sc else 0.85)
            mass = _cluster_mass(books, lv.price, band)
            cw = 0.7 + 0.3 * clamp(mass / 150.0, 0.0, 1.0)
            pw = 1.0
            if pools and any(abs(px - lv.price) <= band for px, _ in pools):
                pw = 1.2                     # unmitigated liquidity AT the level
            rw = 1.0
            if bar_index and lv.last_touch:
                rw = 1.15 if bar_index - lv.last_touch <= 30 else 1.0
            below = lv.price < close
            side_w = 1.0
            if trend_side:
                if htf_bull:
                    side_w = side_bias if below else 1.0 / side_bias
                elif htf_bear:
                    side_w = 1.0 / side_bias if below else side_bias
            rank = prox * tfw * scw * cw * pw * rw * side_w
            if rank > best_rank:
                best_rank, best = rank, lv
    pick = best if best is not None else fn
    if pick is None:
        return None
    pdist = safe_div(abs(close - pick.price), p_atr)
    wrong = close > pick.price if pick.is_res else close < pick.price
    pressing = pdist < 0.5
    breaking = pressing and ((htf_bull and mom > 0.2) if pick.is_res
                             else (htf_bear and mom < -0.2))
    status = ("RETEST LIKELY" if wrong and pdist < 1.5 else
              "BROKEN — new side" if wrong else
              "BREAK LIKELY" if breaking else
              "RESPECT EXPECTED" if pressing else "HOLDING")
    return PowerLine(price=pick.price, score=pick.score, is_res=pick.is_res,
                     dist_atr=pdist, status=status)
