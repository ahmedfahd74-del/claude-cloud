"""Per-symbol multi-timeframe orchestration.

Replays the base timeframe ("the chart") exactly as Pine executes: each TF
computes its OWN regime and adaptive-leg swings on its own bars; confirmed
swings are committed to that TF's level book only once their confirm-time has
passed on the base clock (non-repaint); breaks/touches/sweeps accumulate on
base bars; scoring runs periodically and at the last bar; the Decision,
Probability and Trade engines read only what the earlier engines produced.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import ScanConfig
from .decision import DecisionState
from .indicators import Bar, NAN, clamp, safe_div
from .levels import LevelBook, PowerLine, power_pick
from .methodology import MethodologyResult, evaluate_methodology
from .plan import TradePlan
from .probability import ProbabilityState
from .regime import RegimeState, compute_regime, mode_adjust
from .smc import SMCState
from .swings import Swing, detect_swings


@dataclass
class Analysis:
    symbol: str
    price: float
    ts: int
    regime: RegimeState
    decision: DecisionState
    probability: ProbabilityState
    plan: TradePlan
    books: list[LevelBook]
    trends: dict[str, float]     # tf -> normalised EMA slope
    power: PowerLine | None = None
    sweep_pools: list[tuple[float, bool]] = None  # (price, swept_high) unmitigated
    methodology: MethodologyResult | None = None

    @property
    def why(self) -> str:
        return " · ".join(self.methodology.evidence) if self.methodology else ""


def _last_trend(regimes: list[RegimeState]) -> float:
    return regimes[-1].trend if regimes else NAN


def analyze(symbol: str, bars_by_tf: dict[str, list[Bar]],
            cfg: ScanConfig | None = None) -> Analysis:
    cfg = cfg or ScanConfig()
    base = bars_by_tf[cfg.base_tf][-cfg.history_bars:]
    if len(base) < 60:
        raise ValueError(f"{symbol}: need >=60 base bars, got {len(base)}")

    base_regimes = compute_regime(base, cfg.sens_bias)
    base_min = cfg.tf_minutes(cfg.base_tf)

    # Per-TF pipelines: own regime -> own adaptive swings -> pending queue.
    # HTF-only gating (Pine v2.0.7 default): TFs below the base are skipped —
    # sub-base data would be sampled/unreliable and creates phantom levels.
    books: list[LevelBook] = []
    pending: list[tuple[LevelBook, list[Swing]]] = []
    periods: list[tuple[LevelBook, list[tuple[int, float, float]]]] = []
    tf_regimes: dict[str, list[RegimeState]] = {}
    for tf in cfg.level_tfs:
        tf_min = cfg.tf_minutes(tf)
        if cfg.htf_only and tf_min < base_min:
            continue
        bars = bars_by_tf.get(tf)
        if not bars or len(bars) < 40:
            continue
        regs = compute_regime(bars, cfg.sens_bias)
        tf_regimes[tf] = regs
        swings = detect_swings(bars, regs, int(tf_min * 60))
        book = LevelBook(tf=tf, weight=cfg.tf_weight(tf), tf_minutes=tf_min,
                         base_minutes=base_min, max_levels=cfg.max_levels_per_tf)
        last = regs[-1]
        book.atr_tf = last.atr_fast if last.atr_fast == last.atr_fast else last.atr_safe
        books.append(book)
        pending.append((book, sorted(swings, key=lambda s: s.confirm_ts)))
        # Prev-period extremes (PDH/PDL, PWH/PWL, …): exact candle prices that
        # exist without swing confirmation — H1 and above (Pine v2.0.6 parity).
        if tf_min >= 60:
            ev = [(bars[k].ts, bars[k - 1].high, bars[k - 1].low)
                  for k in range(1, len(bars))]
            periods.append((book, ev))

    # Base-clock replay (Pine chart execution).
    smc = SMCState()
    cursors = [0] * len(pending)
    pcursors = [0] * len(periods)
    pools: list[tuple[float, bool]] = []   # (price, swept_high) unmitigated
    for i, bar in enumerate(base):
        st = base_regimes[i]
        bar_end = bar.ts + int(base_min * 60)
        for p, (book, swings) in enumerate(pending):
            c = cursors[p]
            while c < len(swings) and swings[c].confirm_ts <= bar_end:
                s = swings[c]
                book.add(s.price, s.is_high, i, st.atr_safe, st.ad_merge)
                c += 1
            cursors[p] = c
        for p, (book, ev) in enumerate(periods):
            c = pcursors[p]
            while c < len(ev) and ev[c][0] <= bar_end:
                book.add(ev[c][1], True, i, st.atr_safe, st.ad_merge)
                book.add(ev[c][2], False, i, st.atr_safe, st.ad_merge)
                c += 1
            pcursors[p] = c
        prev_close = base[i - 1].close if i > 0 else bar.close
        mom_x = clamp(safe_div(abs(bar.close - base[i - 3].close), st.atr_fast), 0.0, 2.0) if i >= 3 else 1.0
        for book in books:
            book.update_breaks(bar, prev_close, i, st)
            book.update_touches(bar, i, st, mom_x)
        smc.update(base, i, st)
        # Liquidity sweep pools (Pine v2.0.9 sweep lines): a wick beyond the
        # adaptive threshold AT a level harvests liquidity at its extreme; the
        # pool lives until a close through it spends the liquidity.
        pools = [(px, up) for px, up in pools
                 if not (bar.close > px if up else bar.close < px)]
        m_wick = mode_adjust(cfg.engine_mode, st)[3]
        wick_up = safe_div(bar.high - max(bar.open, bar.close), st.atr_fast)
        wick_dn = safe_div(min(bar.open, bar.close) - bar.low, st.atr_fast)
        near_band = st.atr_safe * st.ad_react
        if wick_up > m_wick and any(abs(lv.price - bar.high) <= near_band * 2
                                    for b in books for lv in b.levels if not lv.broken):
            if all(abs(px - bar.high) > st.atr_fast * 0.15 for px, _ in pools):
                pools.append((bar.high, True))
        if wick_dn > m_wick and any(abs(lv.price - bar.low) <= near_band * 2
                                    for b in books for lv in b.levels if not lv.broken):
            if all(abs(px - bar.low) > st.atr_fast * 0.15 for px, _ in pools):
                pools.append((bar.low, False))
        if len(pools) > 10:
            pools = pools[-10:]
        if i % 10 == 0 or i == len(base) - 1:
            for book in books:
                others = [o for o in books if o is not book]
                book.score_levels(others, i, st, smc.bonus)

    # ── SINGLE DECISION CORE: the institutional 5-step methodology ──────────
    # Replaces the old evidence/probability/gate stack. Its result is adapted
    # onto the existing ProbabilityState / DecisionState / TradePlan carriers
    # so scanner, dashboard, report and learning are unchanged.
    last_i = len(base) - 1
    st = base_regimes[last_i]
    price = base[last_i].close
    trends = {tf: _last_trend(regs) for tf, regs in tf_regimes.items()}

    daily_book = next((b for b in books if b.tf_minutes == 1440), None)
    mr = evaluate_methodology(bars_by_tf, daily_book, cfg)

    want = 1 if mr.bias == "LONG" else -1 if mr.bias == "SHORT" else 0
    mom = safe_div(price - base[last_i - 10].close, st.atr_fast) if last_i >= 10 else 0.0
    dc = DecisionState(
        dist_res_atr=0.0, score_res=0.0, dist_sup_atr=0.0, score_sup=0.0,
        near_res=False, near_sup=False,
        htf_align=mr.htf_agree * want, htf_bull=mr.bias == "LONG", htf_bear=mr.bias == "SHORT",
        mom=clamp(mom, -10.0, 10.0), accum=False, dist=False,
        sweep_res=False, sweep_sup=False, market_state=mr.phase)

    conf = mr.confidence
    bull = clamp(conf, 2.0, 98.0) if mr.bias == "LONG" else clamp(100.0 - conf, 2.0, 98.0)
    quality = ("Excellent" if mr.tier == "A" and conf >= 80 else
               "High Quality" if mr.tier == "A" else
               "Good" if mr.tier == "B" and conf >= 55 else
               "Average" if mr.tier == "B" else "No Trade")
    pb = ProbabilityState(bull_prob=bull, bear_prob=100.0 - bull, bias=mr.direction,
                          quality=quality, q_points=mr.gate_score,
                          evidence=[(0.0, s) for s in mr.evidence])

    plan = TradePlan(
        valid=mr.tier == "A", direction=mr.direction,
        entry=mr.entry, stop=mr.stop, tp1=mr.tp1, tp2=mr.tp2, tp3=mr.tp3, rr=mr.rr,
        gates={f"step{s.n}": s.passed for s in mr.steps},
        fail_reasons=[mr.reject_reason] if mr.reject_reason else [],
        tier=mr.tier, gate_score=mr.gate_score)

    # Power Line v2.1 retained as a visualization aid (distances in DAILY ATR).
    p_atr = daily_book.atr_tf if daily_book is not None and daily_book.atr_tf > 0 else \
        (st.atr_fast if st.atr_fast == st.atr_fast else st.atr_safe)
    power = power_pick(books, price, p_atr, dc.htf_bull, dc.htf_bear,
                       dc.mom, base_min, cfg.power_radius, cfg.power_min_score,
                       cfg.power_trend_side, cfg.power_side_bias)
    return Analysis(symbol=symbol, price=price, ts=base[last_i].ts,
                    regime=st, decision=dc, probability=pb, plan=plan,
                    books=books, trends=trends, power=power, sweep_pools=pools,
                    methodology=mr)
