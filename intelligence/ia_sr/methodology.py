"""Institutional Methodology — THE single decision core.

This replaces the old evidence/probability decision engine. Every consumer
(scanner, dashboard, report, learning, Pine parity) reads its output through
the same adapter, so Pine and Python share one methodology:

  Step 1  Daily context   — trade only inside an Institutional Interest Zone
                            (IIZ): within k×DailyATR of a MAJOR Daily level.
  Step 2  HTF direction    — Weekly / Daily / 4H structure (BOS/CHoCH, HH-HL);
                            a bias needs ≥2 of 3 to agree.
  Step 3  Alignment        — 1H must align with the bias THROUGH structure
                            (a BOS/CHoCH in the bias direction); 30M confirms.
  Step 4  Execution        — on the execution TF: liquidity sweep → BOS/CHoCH
                            back in the bias direction → retest/confirmation.
  Step 5  Trade plan       — entry / stop / TP1-3 / R:R from structure.

Tier A = every step satisfied (sweep + break + retest, RR ≥ min). Tier B =
context + direction + alignment present but execution not fully confirmed
(watch). Anything failing an earlier gate is rejected with the reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import ScanConfig
from .indicators import Bar, atr as atr_series, clamp, safe_div
from .levels import LevelBook
from .structure import StructureState, analyze_structure, swept


@dataclass
class Step:
    n: int
    name: str
    passed: bool
    detail: str


@dataclass
class MethodologyResult:
    active: bool                 # Step 1 gate — interacting with a Daily level
    bias: str                    # LONG / SHORT / NEUTRAL
    tier: str                    # A / B / C
    phase: str                   # human label of how far the workflow reached
    steps: list[Step] = field(default_factory=list)
    reject_reason: str = ""
    # context
    iiz: bool = False
    interaction: str = ""        # approaching / reacting / break-retest
    daily_level: float | None = None
    htf_agree: int = 0
    htf_votes: dict[str, int] = field(default_factory=dict)
    # plan
    direction: str = "NEUTRAL"
    entry: float | None = None
    stop: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    tp3: float | None = None
    rr: float = 0.0
    confidence: float = 0.0      # 0-100 surrogate for the old dir_prob
    gate_score: float = 0.0
    evidence: list[str] = field(default_factory=list)


def _last_atr(bars: list[Bar], length: int = 14) -> float:
    a = atr_series(bars, length)
    for v in reversed(a):
        if v == v and v > 0:      # skip NaN
            return v
    return abs(bars[-1].close) * 0.005 if bars else 0.0


def _major_daily_levels(book: LevelBook | None, min_score: float) -> list:
    if book is None:
        return []
    strong = [lv for lv in book.levels if not lv.broken and lv.score >= min_score]
    return strong or [lv for lv in book.levels if not lv.broken]


def _stack_targets(struct: list[float], entry: float, risk: float,
                   sign: int) -> tuple[float, float, float]:
    """Three strictly-progressing targets: prefer structural levels, fill gaps
    with R-multiples. Guarantees TP1→TP3 move away from entry monotonically."""
    out: list[float] = []
    fallback = [entry + sign * risk * m for m in (1.0, 2.0, 3.0)]
    for k in range(3):
        floor = entry + sign * risk * (k + 1) * 0.5      # min progression per leg
        cand = next((x for x in struct
                     if (x > (out[-1] if out else entry) if sign > 0
                         else x < (out[-1] if out else entry))), None)
        pick = cand if cand is not None and (cand >= floor if sign > 0 else cand <= floor) else fallback[k]
        if out and ((pick <= out[-1]) if sign > 0 else (pick >= out[-1])):
            pick = out[-1] + sign * risk * 0.75
        out.append(pick)
        struct = [x for x in struct if (x > pick if sign > 0 else x < pick)]
    return out[0], out[1], out[2]


def _swing_highs(st: StructureState) -> list[float]:
    return [s.price for s in st.swings if s.is_high]


def _swing_lows(st: StructureState) -> list[float]:
    return [s.price for s in st.swings if not s.is_high]


def evaluate_methodology(bars_by_tf: dict[str, list[Bar]],
                         daily_book: LevelBook | None,
                         cfg: ScanConfig) -> MethodologyResult:
    steps: list[Step] = []
    exec_bars = bars_by_tf.get(cfg.exec_tf) or bars_by_tf.get(cfg.base_tf)
    if not exec_bars:
        return MethodologyResult(False, "NEUTRAL", "C", "no data",
                                 reject_reason="no execution-timeframe data")
    price = exec_bars[-1].close
    daily_bars = bars_by_tf.get("1d", [])
    d_atr = _last_atr(daily_bars) if daily_bars else _last_atr(exec_bars)

    # ── STEP 1 · Daily context / IIZ ────────────────────────────────────────
    majors = _major_daily_levels(daily_book, cfg.major_min_score)
    zone = cfg.iiz_atr * d_atr
    nearest = min(majors, key=lambda lv: abs(lv.price - price), default=None)
    dist = abs(nearest.price - price) if nearest else 1e18
    iiz = nearest is not None and dist <= zone
    interaction = ""
    if iiz:
        # sub-type from recent execution behaviour around the level.
        was_far = any(abs(b.close - nearest.price) > zone for b in exec_bars[-8:-1])
        broke = ((price > nearest.price) != (exec_bars[-8].close > nearest.price)
                 if len(exec_bars) >= 8 else False)
        interaction = ("break-retest" if broke else "reacting" if was_far else "approaching")
    steps.append(Step(1, "Daily context (IIZ)", iiz,
                      f"{interaction} {nearest.price:.6g} ({dist / max(d_atr, 1e-9):.2f} ATR)"
                      if nearest else "no major Daily level"))
    if not iiz:
        return MethodologyResult(False, "NEUTRAL", "C", "Step 1: no Daily interaction",
                                 steps=steps, iiz=False,
                                 reject_reason="price not in a Daily IIZ",
                                 daily_level=nearest.price if nearest else None)

    # ── STEP 2 · HTF direction (W / D / 4H structure, ≥2 agree) ──────────────
    votes: dict[str, int] = {}
    for tf in ("1w", "1d", "4h"):
        b = bars_by_tf.get(tf)
        votes[tf] = analyze_structure(b, cfg.swing_len_htf).trend if b and len(b) > 10 else 0
    up = sum(1 for v in votes.values() if v > 0)
    dn = sum(1 for v in votes.values() if v < 0)
    bias = "LONG" if up >= 2 else "SHORT" if dn >= 2 else "NEUTRAL"
    agree = max(up, dn)
    steps.append(Step(2, "HTF direction", bias != "NEUTRAL",
                      f"W/D/4H votes {votes} → {bias} ({agree}/3)"))
    if bias == "NEUTRAL":
        return MethodologyResult(True, "NEUTRAL", "C", "Step 2: no HTF agreement",
                                 steps=steps, iiz=True, interaction=interaction,
                                 daily_level=nearest.price, htf_agree=agree, htf_votes=votes,
                                 reject_reason="fewer than 2 of W/D/4H agree")
    want = 1 if bias == "LONG" else -1

    # ── STEP 3 · Alignment (1H aligns THROUGH structure; 30M confirms) ───────
    h1 = bars_by_tf.get("1h")
    h1_st = analyze_structure(h1, cfg.swing_len_htf) if h1 and len(h1) > 10 else StructureState()
    last_i_h1 = len(h1) - 1 if h1 else 0
    h1_aligned = (h1_st.trend == want
                  and h1_st.recent_event(None, cfg.align_lookback, last_i_h1)
                  and h1_st.last_event is not None and h1_st.last_event.direction == want)
    m30 = bars_by_tf.get("30m")
    m30_ok = True
    if m30 and len(m30) > 10:
        m30_ok = analyze_structure(m30, cfg.swing_len_exec).trend != -want   # not opposing
    steps.append(Step(3, "1H alignment (structure)", h1_aligned,
                      f"1H trend {h1_st.trend_txt}"
                      + (f", {h1_st.last_event.kind} {'up' if h1_st.last_event.direction > 0 else 'down'}"
                         if h1_st.last_event else ", no break")
                      + (", 30M ok" if m30_ok else ", 30M opposes")))

    # ── STEP 4 · Execution (sweep → BOS/CHoCH in bias dir → retest) ──────────
    ex_st = analyze_structure(exec_bars, cfg.swing_len_exec)
    e_atr = _last_atr(exec_bars)
    li = len(exec_bars) - 1
    ex_break = (ex_st.recent_event(None, cfg.exec_lookback, li)
                and ex_st.last_event is not None and ex_st.last_event.direction == want)
    # sweep of bias-opposite liquidity within the window
    buf = 0.10 * e_atr
    sweep = False
    sweep_price = None
    lows = _swing_lows(ex_st)
    highs = _swing_highs(ex_st)
    for k in range(max(0, li - cfg.exec_lookback), li + 1):
        if want > 0 and lows:
            lvl = min(lows, key=lambda x: abs(x - exec_bars[k].low))
            if swept(exec_bars, k, lvl, False, buf):
                sweep, sweep_price = True, exec_bars[k].low
                break
        if want < 0 and highs:
            lvl = min(highs, key=lambda x: abs(x - exec_bars[k].high))
            if swept(exec_bars, k, lvl, True, buf):
                sweep, sweep_price = True, exec_bars[k].high
                break
    broken_level = ex_st.protected_high if want > 0 else ex_st.protected_low
    retest = (broken_level is not None and abs(price - broken_level) <= cfg.retest_atr * e_atr)
    exec_full = ex_break and sweep and retest
    exec_partial = ex_break and (sweep or retest)
    steps.append(Step(4, "Execution trigger", exec_full,
                      f"sweep={'Y' if sweep else 'N'} break={'Y' if ex_break else 'N'} "
                      f"retest={'Y' if retest else 'N'}"))

    # ── STEP 5 · Trade plan (from structure) ────────────────────────────────
    entry = stop = tp1 = tp2 = tp3 = None
    rr = 0.0
    if exec_partial or exec_full:
        entry = (broken_level if broken_level is not None
                 and abs(price - broken_level) <= cfg.retest_atr * e_atr else price)
        if want > 0:
            sl_base = sweep_price if sweep_price is not None else (ex_st.protected_low or (entry - e_atr))
            stop = min(sl_base, entry - 0.5 * e_atr) - buf
            risk = entry - stop
            # structural targets beyond entry, at least 0.5R out, monotonic;
            # fill any gaps with R-multiples so TP1<TP2<TP3 always holds.
            struct = sorted(x for x in (highs + [nearest.price]) if x >= entry + 0.5 * risk)
            tp1, tp2, tp3 = _stack_targets(struct, entry, risk, +1)
        else:
            sl_base = sweep_price if sweep_price is not None else (ex_st.protected_high or (entry + e_atr))
            stop = max(sl_base, entry + 0.5 * e_atr) + buf
            risk = stop - entry
            struct = sorted((x for x in (lows + [nearest.price]) if x <= entry - 0.5 * risk), reverse=True)
            tp1, tp2, tp3 = _stack_targets(struct, entry, risk, -1)
        rr = abs(tp3 - entry) / risk if risk > 0 else 0.0

    # ── Tiering + confidence ────────────────────────────────────────────────
    aligned_full = h1_aligned and m30_ok
    tierA = (iiz and interaction in ("reacting", "break-retest") and agree >= 2
             and aligned_full and exec_full and rr >= cfg.min_rr)
    tierB = (agree >= 2 and (h1_aligned or exec_partial)
             and (exec_partial or exec_full) and entry is not None)
    tier = "A" if tierA else "B" if tierB else "C"

    # confidence: HTF agreement + alignment + execution completeness + zone quality
    conf = (18.0 * agree
            + (14.0 if h1_aligned else 0.0) + (6.0 if m30_ok else 0.0)
            + (12.0 if sweep else 0.0) + (12.0 if ex_break else 0.0) + (10.0 if retest else 0.0)
            + (8.0 if interaction in ("reacting", "break-retest") else 4.0))
    conf = clamp(conf, 0.0, 100.0)
    gs = clamp(20.0 * agree + (15.0 if h1_aligned else 0.0)
               + (15.0 if sweep else 0.0) + (15.0 if ex_break else 0.0)
               + (15.0 if retest else 0.0) + clamp(rr / max(cfg.min_rr, 0.1) * 10.0, 0.0, 10.0),
               0.0, 100.0)

    reject = ""
    if tier == "C":
        reject = ("Step 3: 1H not aligned" if not h1_aligned and not exec_partial
                  else "Step 4: no execution trigger" if not exec_partial
                  else "Step 5: R:R below minimum" if entry is not None and rr < cfg.min_rr
                  else "incomplete setup")

    phase = ("Tier A — execute" if tier == "A"
             else "Tier B — watch" if tier == "B"
             else "Step 4: execution" if h1_aligned
             else "Step 3: alignment")
    evidence = [f"IIZ {interaction} @ {nearest.price:.6g}",
                f"HTF {bias} {agree}/3 {votes}",
                f"1H {'aligned' if h1_aligned else 'not aligned'}",
                f"exec sweep={'Y' if sweep else 'N'}/break={'Y' if ex_break else 'N'}/retest={'Y' if retest else 'N'}"]

    return MethodologyResult(
        active=True, bias=bias, tier=tier, phase=phase, steps=steps,
        reject_reason=reject, iiz=iiz, interaction=interaction,
        daily_level=nearest.price, htf_agree=agree, htf_votes=votes,
        direction=bias if tier in ("A", "B") else "NEUTRAL",
        entry=entry, stop=stop, tp1=tp1, tp2=tp2, tp3=tp3, rr=rr,
        confidence=conf, gate_score=gs, evidence=evidence,
    )
