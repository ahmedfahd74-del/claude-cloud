"""Methodology ablation study — rule-level instrumentation.

ONE historical pass records, at every evaluation point:
  · the pass/fail of EVERY individual methodology rule
    (iiz, htf2, align1h, m30, sweep, bos, retest, rr)
  · a candidate trade plan built from the same structural logic
  · the simulated forward outcome of that candidate (fill → stop/TP1 race,
    timeout by sign), plus MFE and whether TP1 printed after a stop-out.

Every question — step funnel, remove-one-rule ablations, rule contribution,
confusion matrix (rejected winners vs accepted losers), per-market and
per-HTF-combination performance, loser attribution — is then a FILTER over
this single candidate table, so all answers come from the same data.

The rule logic below mirrors methodology.py exactly; this module only adds
instrumentation (no early return), it does not define a second methodology.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import ScanConfig
from .datafeed import Feed
from .methodology import _last_atr, _major_daily_levels, _stack_targets
from .structure import StructureState, analyze_structure, swept

FILL_WIN = 40
LIFE = 200

RULE_ORDER = ["iiz", "htf2", "align1h", "m30", "sweep", "bos", "retest", "rr"]
STEP_OF = {"iiz": 1, "htf2": 2, "align1h": 3, "m30": 3,
           "sweep": 4, "bos": 4, "retest": 4, "rr": 5}

MARKET_OF = {
    "EURUSD": "forex", "GBPUSD": "forex", "USDJPY": "forex", "AUDUSD": "forex",
    "USDCAD": "forex", "USDCHF": "forex", "NZDUSD": "forex", "EURGBP": "forex",
    "EURJPY": "forex", "GBPJPY": "forex",
    "XAUUSD": "gold", "XAGUSD": "gold",
    "BTCUSD": "crypto", "ETHUSD": "crypto", "SOLUSD": "crypto",
}


@dataclass
class Candidate:
    symbol: str
    market: str
    i: int                       # exec bar index at evaluation
    direction: str
    rules: dict[str, bool]
    votes: dict[str, int]
    interaction: str
    dist_atr: float
    entry: float
    stop: float
    tp1: float
    tp3: float
    planned_rr: float
    outcome: str = "open"        # win / loss / timeout / cancelled
    realised_r: float = 0.0
    fill_i: int | None = None
    exit_i: int | None = None
    mfe_r: float = 0.0           # max favourable excursion while open (R)
    tp1_after_stop: bool = False  # stopped, but TP1 printed within LIFE after

    def passes(self, keys: list[str]) -> bool:
        return all(self.rules[k] for k in keys)

    @property
    def hold(self) -> int | None:
        return (self.exit_i - self.fill_i) if self.fill_i is not None and self.exit_i is not None else None


@dataclass
class Study:
    candidates: list[Candidate]
    evaluated: int
    bars_per_symbol: dict[str, int]

    def variant(self, keys: list[str]) -> dict:
        """Stats of the chain formed by `keys`, non-overlapping per symbol."""
        take = sorted((c for c in self.candidates if c.passes(keys)),
                      key=lambda c: (c.symbol, c.i))
        kept: list[Candidate] = []
        busy_until: dict[str, int] = {}
        for c in take:
            if c.i >= busy_until.get(c.symbol, -1):
                kept.append(c)
                busy_until[c.symbol] = (c.exit_i if c.exit_i is not None
                                        else c.i + FILL_WIN)
        closed = [c for c in kept if c.outcome in ("win", "loss", "timeout")]
        wins = [c for c in closed if c.realised_r > 0]
        n = len(closed)
        eq = peak = mdd = 0.0
        for c in closed:
            eq += c.realised_r
            peak = max(peak, eq)
            mdd = min(mdd, eq - peak)
        total_kbars = sum(self.bars_per_symbol.values()) / 1000.0
        return {
            "trades": len(kept),
            "closed": n,
            "per_1k_bars": len(kept) / total_kbars if total_kbars else 0.0,
            "win_rate": 100.0 * len(wins) / n if n else None,
            "expectancy_r": sum(c.realised_r for c in closed) / n if n else None,
            "avg_planned_rr": (sum(c.planned_rr for c in kept) / len(kept)) if kept else None,
            "max_dd_r": mdd,
            "avg_hold": (sum(c.hold for c in closed if c.hold is not None)
                         / max(1, sum(1 for c in closed if c.hold is not None))),
        }


def run_study(feed: Feed, cfg: ScanConfig | None = None, *, history: int = 3500,
              stride: int = 4, warmup: int = 400) -> Study:
    cfg = cfg or ScanConfig()
    exec_sec = int(cfg.tf_minutes(cfg.exec_tf) * 60)
    cands: list[Candidate] = []
    evaluated = 0
    bars_per_symbol: dict[str, int] = {}

    for symbol in cfg.symbols:
        ex = feed.bars(symbol, cfg.exec_tf, history)
        if len(ex) < warmup + 200:
            continue
        bars_per_symbol[symbol] = len(ex) - warmup
        htf_all = {tf: feed.bars(symbol, tf, 600)
                   for tf in cfg.level_tfs if tf != cfg.exec_tf}
        tf_sec = {tf: int(cfg.tf_minutes(tf) * 60) for tf in htf_all}
        # caches keyed by closed-bar count (a TF's structure only changes when
        # one of its bars closes) — this is what makes one pass affordable.
        struct_cache: dict[tuple[str, int], StructureState] = {}
        book_cache: dict[int, object] = {}
        cut_idx = {tf: 0 for tf in htf_all}

        for i in range(warmup, len(ex), stride):
            cutoff = ex[i].ts + exec_sec
            sliced: dict[str, list] = {}
            for tf, bars in htf_all.items():
                k = cut_idx[tf]
                while k < len(bars) and bars[k].ts + tf_sec[tf] <= cutoff:
                    k += 1
                cut_idx[tf] = k
                sliced[tf] = bars[:k]
            c = _evaluate_point(symbol, ex, i, sliced, cfg, struct_cache, book_cache)
            evaluated += 1
            if c is not None:
                _simulate(c, ex)
                cands.append(c)
        # cut_idx is monotonic per symbol — safe because i only increases
    return Study(cands, evaluated, bars_per_symbol)


def _structure(cache, tf: str, bars: list, leg: int) -> StructureState:
    key = (tf, len(bars))
    st = cache.get(key)
    if st is None:
        st = analyze_structure(bars, leg) if len(bars) > 10 else StructureState()
        cache[key] = st
    return st


def _daily_book(cache, daily: list, cfg: ScanConfig):
    key = len(daily)
    bk = cache.get(key)
    if bk is None:
        from .backtest import _build_daily_book
        bk = _build_daily_book(daily, cfg)
        cache.clear()            # keep only the newest (books are cumulative)
        cache[key] = bk
    return bk


def _evaluate_point(symbol, ex, i, sliced, cfg, struct_cache, book_cache):
    """Mirror of methodology gates WITHOUT early return; returns a Candidate
    whenever a directional hypothesis + plan can be formed, tagged with every
    rule's pass/fail."""
    price = ex[i].close
    daily = sliced.get("1d", [])
    if len(daily) < 40:
        return None
    d_atr = _last_atr(daily)
    book = _daily_book(book_cache, daily, cfg)

    majors = _major_daily_levels(book, cfg.major_min_score)
    nearest = min(majors, key=lambda lv: abs(lv.price - price), default=None)
    if nearest is None:
        return None
    dist = abs(nearest.price - price)
    zone = cfg.iiz_atr * d_atr
    r_iiz = dist <= zone
    exec_slice = ex[max(0, i - 8): i + 1]
    was_far = any(abs(b.close - nearest.price) > zone for b in exec_slice[:-1])
    broke = ((price > nearest.price) != (exec_slice[0].close > nearest.price)
             if len(exec_slice) >= 8 else False)
    interaction = ("break-retest" if broke else "reacting" if was_far else "approaching") if r_iiz else ""

    votes = {}
    for tf in ("1w", "1d", "4h"):
        b = sliced.get(tf, [])
        votes[tf] = _structure(struct_cache, tf, b, cfg.swing_len_htf).trend if len(b) > 10 else 0
    up = sum(1 for v in votes.values() if v > 0)
    dn = sum(1 for v in votes.values() if v < 0)
    net = sum(votes.values())
    want = 1 if net > 0 else -1 if net < 0 else 0
    if want == 0:
        return None              # no directional hypothesis → not a candidate
    r_htf2 = max(up, dn) >= 2

    h1b = sliced.get("1h", [])
    h1 = _structure(struct_cache, "1h", h1b, cfg.swing_len_htf)
    r_align = (h1.trend == want and h1.last_event is not None
               and h1.last_event.direction == want
               and h1.recent_event(None, cfg.align_lookback, len(h1b) - 1))
    m30b = sliced.get("30m", [])
    m30 = _structure(struct_cache, "30m", m30b, cfg.swing_len_exec)
    r_m30 = (m30.trend != -want) if len(m30b) > 10 else True

    ex_bars = ex[: i + 1]
    ex_st = analyze_structure(ex_bars[-min(len(ex_bars), 420):], cfg.swing_len_exec)
    off = len(ex_bars) - min(len(ex_bars), 420)
    e_atr = _last_atr(ex_bars[-100:])
    buf = 0.10 * e_atr
    li = len(ex_bars) - 1 - off
    r_bos = (ex_st.last_event is not None and ex_st.last_event.direction == want
             and li - ex_st.last_event.index <= cfg.exec_lookback)
    lows = [s.price for s in ex_st.swings if not s.is_high]
    highs = [s.price for s in ex_st.swings if s.is_high]
    r_sweep = False
    sweep_price = None
    for k in range(max(0, li - cfg.exec_lookback), li + 1):
        if want > 0 and lows:
            lvl = min(lows, key=lambda x: abs(x - ex_bars[off + k].low))
            if swept(ex_bars, off + k, lvl, False, buf):
                r_sweep, sweep_price = True, ex_bars[off + k].low
                break
        if want < 0 and highs:
            lvl = min(highs, key=lambda x: abs(x - ex_bars[off + k].high))
            if swept(ex_bars, off + k, lvl, True, buf):
                r_sweep, sweep_price = True, ex_bars[off + k].high
                break
    broken_level = ex_st.protected_high if want > 0 else ex_st.protected_low
    r_retest = (broken_level is not None
                and abs(price - broken_level) <= cfg.retest_atr * e_atr)

    # candidate plan — same construction as methodology Step 5
    entry = (broken_level if broken_level is not None
             and abs(price - broken_level) <= cfg.retest_atr * e_atr else price)
    if want > 0:
        sl_base = sweep_price if sweep_price is not None else (ex_st.protected_low or (entry - e_atr))
        stop = min(sl_base, entry - 0.5 * e_atr) - buf
        risk = entry - stop
        struct = sorted(x for x in (highs + [nearest.price]) if x >= entry + 0.5 * risk)
        tp1, tp2, tp3 = _stack_targets(struct, entry, risk, +1)
    else:
        sl_base = sweep_price if sweep_price is not None else (ex_st.protected_high or (entry + e_atr))
        stop = max(sl_base, entry + 0.5 * e_atr) + buf
        risk = stop - entry
        struct = sorted((x for x in (lows + [nearest.price]) if x <= entry - 0.5 * risk), reverse=True)
        tp1, tp2, tp3 = _stack_targets(struct, entry, risk, -1)
    if risk <= 0:
        return None
    rr = abs(tp3 - entry) / risk
    r_rr = rr >= cfg.min_rr

    return Candidate(
        symbol=symbol, market=MARKET_OF.get(symbol, "other"), i=i,
        direction="LONG" if want > 0 else "SHORT",
        rules={"iiz": r_iiz, "htf2": r_htf2, "align1h": r_align, "m30": r_m30,
               "sweep": r_sweep, "bos": r_bos, "retest": r_retest, "rr": r_rr},
        votes=votes, interaction=interaction, dist_atr=dist / max(d_atr, 1e-12),
        entry=entry, stop=stop, tp1=tp1, tp3=tp3, planned_rr=rr)


def _simulate(c: Candidate, ex: list) -> None:
    d = 1 if c.direction == "LONG" else -1
    risk = abs(c.entry - c.stop)
    r_tp1 = abs(c.tp1 - c.entry) / risk
    stop_i = None
    for j in range(c.i + 1, min(len(ex), c.i + FILL_WIN + LIFE + 1)):
        b = ex[j]
        if c.fill_i is None:
            if (b.low <= c.entry if d > 0 else b.high >= c.entry):
                c.fill_i = j
            elif j - c.i > FILL_WIN:
                c.outcome = "cancelled"
                return
            continue
        fav = (b.high - c.entry) * d / risk if d > 0 else (c.entry - b.low) / risk
        c.mfe_r = max(c.mfe_r, fav)
        if stop_i is None:
            if (b.low <= c.stop if d > 0 else b.high >= c.stop):
                c.outcome, c.realised_r, c.exit_i = "loss", -1.0, j
                stop_i = j            # keep walking to see if TP1 prints later
            elif (b.high >= c.tp1 if d > 0 else b.low <= c.tp1):
                c.outcome, c.realised_r, c.exit_i = "win", r_tp1, j
                return
            elif j - c.fill_i > LIFE:
                c.realised_r = (b.close - c.entry) * d / risk
                c.outcome, c.exit_i = "timeout", j
                return
        else:
            if (b.high >= c.tp1 if d > 0 else b.low <= c.tp1):
                c.tp1_after_stop = True
                return
            if j - stop_i > LIFE:
                return
    if c.fill_i is not None and c.outcome == "open":
        c.outcome = "timeout"
        c.exit_i = min(len(ex) - 1, c.fill_i + LIFE)
        c.realised_r = (ex[c.exit_i].close - c.entry) * d / risk


# ── report assembly ───────────────────────────────────────────────────────────

def full_report(study: Study, cfg: ScanConfig) -> dict:
    cands = study.candidates
    resolved = [c for c in cands if c.outcome in ("win", "loss", "timeout")]

    # Q1 · funnel: first failing rule, in methodology order
    funnel: dict[str, int] = {k: 0 for k in RULE_ORDER}
    passed_all = 0
    # Q2 · winners lost at each step (candidate would have won)
    lost_winners: dict[str, int] = {k: 0 for k in RULE_ORDER}
    for c in resolved:
        fail = next((k for k in RULE_ORDER if not c.rules[k]), None)
        if fail is None:
            passed_all += 1
        else:
            funnel[fail] += 1
            if c.realised_r > 0:
                lost_winners[fail] += 1

    # Q3/Q4/Q5 · ablations: FULL, minus-one-rule, the SIMPLE chain, universe
    variants: dict[str, dict] = {"FULL (all rules)": study.variant(RULE_ORDER)}
    for k in RULE_ORDER:
        keys = [r for r in RULE_ORDER if r != k]
        variants[f"minus {k}"] = study.variant(keys)
    variants["SIMPLE (iiz+htf2+sweep+bos)"] = study.variant(["iiz", "htf2", "sweep", "bos"])
    variants["UNIVERSE (no rules)"] = study.variant([])

    # Q6 · confusion matrix vs the FULL chain
    cm = {"accepted_win": 0, "accepted_loss": 0, "rejected_win": 0, "rejected_loss": 0}
    for c in resolved:
        acc = c.passes(RULE_ORDER)
        win = c.realised_r > 0
        cm[("accepted" if acc else "rejected") + ("_win" if win else "_loss")] += 1

    # Q7 · per-market under the SIMPLE chain (enough volume to be meaningful)
    per_market: dict[str, dict] = {}
    simple_keys = ["iiz", "htf2", "sweep", "bos"]
    for mkt in ("forex", "gold", "crypto"):
        sub = Study([c for c in cands if c.market == mkt], 0,
                    {s: n for s, n in study.bars_per_symbol.items()
                     if MARKET_OF.get(s) == mkt})
        per_market[mkt] = sub.variant(simple_keys)

    # Q8 · which HTF vote combination wins (bias-level timeframe combo)
    combo: dict[str, dict] = {}
    for c in resolved:
        if not c.passes(simple_keys):
            continue
        agree = [tf for tf, v in c.votes.items()
                 if v == (1 if c.direction == "LONG" else -1)]
        key = "+".join(sorted(agree)) or "none"
        d_ = combo.setdefault(key, {"n": 0, "wins": 0, "r": 0.0})
        d_["n"] += 1
        d_["wins"] += 1 if c.realised_r > 0 else 0
        d_["r"] += c.realised_r
    for k, v in combo.items():
        v["win_rate"] = 100.0 * v["wins"] / v["n"] if v["n"] else None
        v["expectancy"] = v["r"] / v["n"] if v["n"] else None

    # Q9 · loser attribution on the SIMPLE chain
    attribution = {"execution_timing": 0, "htf_bias": 0, "level_selection": 0, "other": 0}
    losers = [c for c in resolved if c.passes(simple_keys) and c.realised_r < 0]
    for c in losers:
        if c.tp1_after_stop:
            attribution["execution_timing"] += 1       # idea right, entry/stop wrong
        elif c.mfe_r < 0.3:
            attribution["htf_bias"] += 1               # never went our way at all
        elif c.interaction == "approaching" or c.dist_atr > 0.35:
            attribution["level_selection"] += 1        # weak context at entry
        else:
            attribution["other"] += 1

    return {
        "candidates": len(cands), "resolved": len(resolved),
        "evaluated_points": study.evaluated,
        "funnel_first_fail": funnel, "passed_all": passed_all,
        "lost_winners_by_step": lost_winners,
        "variants": variants, "confusion_matrix": cm,
        "per_market_simple": per_market, "htf_combo": combo,
        "loser_attribution": attribution, "losers_analyzed": len(losers),
    }
