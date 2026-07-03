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
from .decision import DecisionState, evaluate as evaluate_decision
from .indicators import Bar, NAN
from .levels import LevelBook
from .plan import GateConfig, TradePlan, build as build_plan
from .probability import ProbabilityState, evaluate as evaluate_probability
from .regime import RegimeState, compute_regime
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
    books: list[LevelBook] = []
    pending: list[tuple[LevelBook, list[Swing]]] = []
    tf_regimes: dict[str, list[RegimeState]] = {}
    for tf in cfg.level_tfs:
        bars = bars_by_tf.get(tf)
        if not bars or len(bars) < 40:
            continue
        regs = compute_regime(bars, cfg.sens_bias)
        tf_regimes[tf] = regs
        swings = detect_swings(bars, regs, int(cfg.tf_minutes(tf) * 60))
        book = LevelBook(tf=tf, weight=cfg.tf_weight(tf), tf_minutes=cfg.tf_minutes(tf),
                         base_minutes=base_min, max_levels=cfg.max_levels_per_tf)
        last = regs[-1]
        book.atr_tf = last.atr_fast if last.atr_fast == last.atr_fast else last.atr_safe
        books.append(book)
        pending.append((book, sorted(swings, key=lambda s: s.confirm_ts)))

    # Base-clock replay (Pine chart execution).
    smc = SMCState()
    cursors = [0] * len(pending)
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
        prev_close = base[i - 1].close if i > 0 else bar.close
        for book in books:
            book.update_breaks(bar, prev_close, i, st)
            book.update_touches(bar, i, st)
        smc.update(base, i, st)
        if i % 10 == 0 or i == len(base) - 1:
            for book in books:
                others = [o for o in books if o is not book]
                book.score_levels(others, i, st, smc.bonus)

    # Final-bar decision stack (Pine Sections 10/11/14).
    last_i = len(base) - 1
    st = base_regimes[last_i]
    trends = {tf: _last_trend(regs) for tf, regs in tf_regimes.items()}
    tr_w = trends.get("1w", NAN)
    tr_d = trends.get("1d", NAN)
    tr_h4 = trends.get("4h", NAN)
    tr_h1 = trends.get("1h", st.trend if cfg.base_tf == "1h" else NAN)

    dc = evaluate_decision(base, last_i, st, books, tr_w, tr_d, tr_h4)
    obu, obd, fbu, fbd = smc.near_flags(base[last_i])
    pb = evaluate_probability(st, dc, tr_w, tr_d, tr_h4, tr_h1, obu, obd, fbu, fbd)
    plan = build_plan(base[last_i].close, st, dc, pb, books,
                      GateConfig(cfg.min_prob, cfg.min_rr, cfg.min_sr_conf,
                                 cfg.account_risk_pct))
    return Analysis(symbol=symbol, price=base[last_i].close, ts=base[last_i].ts,
                    regime=st, decision=dc, probability=pb, plan=plan,
                    books=books, trends=trends)
