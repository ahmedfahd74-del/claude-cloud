"""Methodology validation harness.

Walks history bar-by-bar, runs the SAME 5-step methodology the live engine
uses at each step, opens non-overlapping trades from Tier A/B setups, resolves
them against forward bars, and reports the robustness metrics — trade
frequency, win rate, average planned & realised R, max drawdown, average hold
time, Tier A vs B share, and a histogram of rejection reasons.

No optimisation: fixed default thresholds, one pass, deterministic feed. The
goal is to prove the methodology holds up before any weight tuning.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import ScanConfig
from .datafeed import Feed
from .levels import LevelBook
from .methodology import evaluate_methodology
from .structure import analyze_structure  # noqa: F401 (kept for parity imports)
from .config import TIMEFRAMES

FILL_WIN = 40      # exec bars a limit entry may wait to fill
LIFE = 200         # exec bars before an open trade times out


@dataclass
class Trade:
    symbol: str
    direction: str
    tier: str
    entry: float
    stop: float
    tp1: float
    tp3: float
    planned_rr: float
    open_i: int
    fill_i: int | None = None
    exit_i: int | None = None
    outcome: str = "open"     # win / loss / timeout / cancelled
    realised_r: float = 0.0   # R to exit (TP1 = +planned R to tp1; stop = -1)


@dataclass
class BacktestResult:
    trades: list[Trade]
    evaluated: int
    rejects: dict[str, int]
    per_symbol: dict[str, int]

    def summary(self) -> dict:
        closed = [t for t in self.trades if t.outcome in ("win", "loss", "timeout")]
        wins = [t for t in closed if t.outcome == "win"]
        n = len(closed)
        rr = [t.planned_rr for t in self.trades if t.planned_rr > 0]
        holds = [t.exit_i - t.fill_i for t in closed if t.fill_i is not None and t.exit_i is not None]
        tierA = sum(1 for t in self.trades if t.tier == "A")
        tierB = sum(1 for t in self.trades if t.tier == "B")
        # equity curve in R → max drawdown
        eq = 0.0
        peak = 0.0
        mdd = 0.0
        for t in closed:
            eq += t.realised_r
            peak = max(peak, eq)
            mdd = min(mdd, eq - peak)
        return {
            "opportunities": len(self.trades),
            "filled": len([t for t in self.trades if t.fill_i is not None]),
            "closed": n,
            "win_rate": (100.0 * len(wins) / n) if n else None,
            "avg_planned_rr": (sum(rr) / len(rr)) if rr else None,
            "avg_realised_r": (sum(t.realised_r for t in closed) / n) if n else None,
            "expectancy_r": (sum(t.realised_r for t in closed) / n) if n else None,
            "max_drawdown_r": mdd,
            "avg_hold_bars": (sum(holds) / len(holds)) if holds else None,
            "tierA_pct": (100.0 * tierA / len(self.trades)) if self.trades else None,
            "tierB_pct": (100.0 * tierB / len(self.trades)) if self.trades else None,
            "evaluated_points": self.evaluated,
            "reject_reasons": dict(sorted(self.rejects.items(), key=lambda kv: -kv[1])),
        }


def _slice(bars: list, cutoff_ts: int, tf_seconds: int) -> list:
    """Bars fully CLOSED at or before cutoff_ts (non-repainting HTF read)."""
    return [b for b in bars if b.ts + tf_seconds <= cutoff_ts]


def _build_daily_book(daily_bars: list, cfg: ScanConfig) -> LevelBook:
    """A lightweight Daily level book from confirmed daily swings (Step-1 source)."""
    from .regime import compute_regime
    from .swings import detect_swings
    book = LevelBook(tf="1d", weight=0.8, tf_minutes=1440,
                     base_minutes=cfg.tf_minutes(cfg.exec_tf), max_levels=cfg.max_levels_per_tf)
    if len(daily_bars) < 40:
        return book
    regs = compute_regime(daily_bars, cfg.sens_bias)
    book.atr_tf = regs[-1].atr_fast if regs[-1].atr_fast == regs[-1].atr_fast else regs[-1].atr_safe
    swings = detect_swings(daily_bars, regs, 86400)
    for i, b in enumerate(daily_bars):
        st = regs[i]
        for s in swings:
            if s.confirm_index == i:
                book.add(s.price, s.is_high, i, st.atr_safe, st.ad_merge, s.body)
        book.update_breaks(b, daily_bars[i - 1].close if i else b.close, i, st)
        book.update_touches(b, i, st)
    others: list[LevelBook] = []
    book.score_levels(others, len(daily_bars) - 1, regs[-1], lambda p: 0.0)
    return book


def run(feed: Feed, cfg: ScanConfig | None = None, *, history: int = 4000,
        stride: int = 4, warmup: int = 400) -> BacktestResult:
    cfg = cfg or ScanConfig()
    trades: list[Trade] = []
    rejects: dict[str, int] = {}
    per_symbol: dict[str, int] = {}
    evaluated = 0
    exec_sec = int(cfg.tf_minutes(cfg.exec_tf) * 60)

    for symbol in cfg.symbols:
        ex = feed.bars(symbol, cfg.exec_tf, history)
        if len(ex) < warmup + 200:
            continue
        htf = {tf: feed.bars(symbol, tf, 600) for tf in cfg.level_tfs if tf != cfg.exec_tf}
        open_trade: Trade | None = None

        i = warmup
        while i < len(ex) - 1:
            # resolve an open trade before considering a new one (sequential)
            if open_trade is not None:
                _step_resolve(open_trade, ex, i)
                if open_trade.outcome != "open":
                    open_trade = None
                i += 1
                continue

            if i % stride != 0:
                i += 1
                continue
            cutoff = ex[i].ts + exec_sec
            bt = {cfg.exec_tf: ex[: i + 1]}
            for tf, bars in htf.items():
                bt[tf] = _slice(bars, cutoff, int(cfg.tf_minutes(tf) * 60))
            daily_book = _build_daily_book(bt.get("1d", []), cfg)
            mr = evaluate_methodology(bt, daily_book, cfg)
            evaluated += 1
            if mr.reject_reason:
                rejects[mr.reject_reason] = rejects.get(mr.reject_reason, 0) + 1
            if mr.tier in ("A", "B") and mr.entry and mr.stop and mr.tp1:
                risk = abs(mr.entry - mr.stop)
                if risk > 0:
                    open_trade = Trade(symbol, mr.bias, mr.tier, mr.entry, mr.stop,
                                       mr.tp1, mr.tp3, mr.rr, i)
                    trades.append(open_trade)
                    per_symbol[symbol] = per_symbol.get(symbol, 0) + 1
            i += 1

    return BacktestResult(trades, evaluated, rejects, per_symbol)


def _step_resolve(t: Trade, ex: list, i: int) -> None:
    """Advance a single trade one bar at index i (called each bar it is open)."""
    d = 1 if t.direction == "LONG" else -1
    bar = ex[i]
    risk = abs(t.entry - t.stop)
    r_to_tp1 = abs(t.tp1 - t.entry) / risk if risk else 0.0
    if t.fill_i is None:
        # limit fill: price trades to entry within the window
        hit = bar.low <= t.entry if d > 0 else bar.high >= t.entry
        if hit:
            t.fill_i = i
        elif i - t.open_i > FILL_WIN:
            t.outcome = "cancelled"
        return
    # in-trade: stop-first if both stop and tp1 touched on the same bar
    stop_hit = bar.low <= t.stop if d > 0 else bar.high >= t.stop
    tp_hit = bar.high >= t.tp1 if d > 0 else bar.low <= t.tp1
    if stop_hit:
        t.outcome, t.realised_r, t.exit_i = "loss", -1.0, i
    elif tp_hit:
        t.outcome, t.realised_r, t.exit_i = "win", r_to_tp1, i
    elif i - t.fill_i > LIFE:
        t.realised_r = (bar.close - t.entry) * d / risk if risk else 0.0
        t.outcome, t.exit_i = "timeout", i
