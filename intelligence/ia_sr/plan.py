"""Trade Execution Engine — Pine Section 14 port.

Builds the validated institutional plan: structural entry, bounded structural
stop (0.5-3.0 ATR), level-based targets with ATR fallback, and the exact
eight-gate validation used by Pine (including the reversal-favours-trade
exception). Rejections carry every failed gate, mirroring the Pine diagnostic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .decision import DecisionState
from .indicators import clamp
from .levels import LevelBook, gather
from .probability import ProbabilityState
from .regime import RegimeState


@dataclass
class GateConfig:
    min_prob: float = 65.0
    min_rr: float = 2.0
    min_sr_conf: float = 60.0
    account_risk_pct: float = 1.0
    prob_adj: float = 0.0      # adaptive/mode shift (Pine mProbAdj)
    score_adj: float = 0.0     # adaptive/mode shift (Pine mScoreAdj)


@dataclass
class TradePlan:
    valid: bool
    direction: str                     # LONG / SHORT / NEUTRAL
    entry: float | None = None
    stop: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    tp3: float | None = None
    rr: float = 0.0
    position_pct: float | None = None  # % notional for account_risk_pct
    gates: dict[str, bool] = field(default_factory=dict)
    fail_reasons: list[str] = field(default_factory=list)


def build(price: float, st: RegimeState, dc: DecisionState, pb: ProbabilityState,
          books: list[LevelBook], cfg: GateConfig = GateConfig()) -> TradePlan:
    long = pb.bias == "LONG"
    short = pb.bias == "SHORT"
    sign = 1 if long else -1
    atr = st.atr_fast if st.atr_fast == st.atr_fast else st.atr_safe
    sr_conf = dc.score_sup if long else dc.score_res if short else 0.0

    sups = gather(books, price, -1)
    ress = gather(books, price, 1)
    entry = (sups[0] if long and sups else ress[0] if short and ress else None)

    stop = None
    if entry is not None:
        if long:
            s0 = (sups[1] if len(sups) > 1 else entry - atr * 1.5) - atr * 0.25
            stop = clamp(s0, entry - atr * 3.0, entry - atr * 0.5)
        else:
            s0 = (ress[1] if len(ress) > 1 else entry + atr * 1.5) + atr * 0.25
            stop = clamp(s0, entry + atr * 0.5, entry + atr * 3.0)

    tps: list[float | None] = [None, None, None]
    if entry is not None:
        tgt = gather(books, entry, 1 if long else -1)
        for k in range(3):
            tps[k] = tgt[k] if len(tgt) > k else None
        if tps[0] is None:
            tps[0] = entry + sign * atr * 1.5
        if tps[1] is None:
            tps[1] = tps[0] + sign * atr * 1.5
        if tps[2] is None:
            tps[2] = tps[1] + sign * atr * 1.5

    rr = 0.0
    pos_pct = None
    if entry is not None and stop is not None and tps[2] is not None:
        risk = abs(entry - stop)
        rr = abs(tps[2] - entry) / risk if risk > 0 else 0.0
        stop_pct = risk / entry * 100 if entry else 0.0
        pos_pct = cfg.account_risk_pct / stop_pct * 100 if stop_pct else None

    rev_favors = (dc.near_sup and dc.htf_bull) if long else \
                 (dc.near_res and dc.htf_bear) if short else False
    # Adaptive/mode-shifted effective thresholds (Pine effMinProb/effMinScore).
    eff_min_prob = clamp(cfg.min_prob + cfg.prob_adj, 50.0, 98.0)
    eff_min_score = clamp(cfg.min_sr_conf + cfg.score_adj, 0.0, 100.0)
    gates = {
        "bias": long or short,
        "quality": pb.quality in ("Excellent", "High Quality"),
        "probability": pb.dir_prob >= eff_min_prob,
        "htf_align": dc.htf_align > 0 if long else dc.htf_align < 0 if short else False,
        "sr_confidence": sr_conf >= eff_min_score,
        "structure": dc.market_state != "Reversal Risk" or rev_favors,
        "levels": entry is not None and stop is not None and tps[0] is not None,
        "rr": rr >= cfg.min_rr,
    }
    fails = [name for name, ok in gates.items() if not ok]
    return TradePlan(
        valid=not fails,
        direction=pb.bias,
        entry=entry, stop=stop, tp1=tps[0], tp2=tps[1], tp3=tps[2],
        rr=rr, position_pct=pos_pct, gates=gates, fail_reasons=fails,
    )
