"""Probability & Trade-Quality Engine — Pine Section 11 port.

Same signed-evidence model and weights as Pine's netBull. Every contribution
is returned as an (points, label) pair so explanations never diverge from the
number they explain (Pine f_evidence parity).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .decision import DecisionState
from .regime import RegimeState, trend_sign
from .indicators import clamp


@dataclass
class ProbabilityState:
    bull_prob: float
    bear_prob: float
    bias: str                      # LONG / SHORT / NEUTRAL
    quality: str
    q_points: float
    evidence: list[tuple[float, str]] = field(default_factory=list)

    @property
    def dir_prob(self) -> float:
        return (self.bull_prob if self.bias == "LONG"
                else self.bear_prob if self.bias == "SHORT" else 0.0)

    def evidence_text(self, sep: str = ", ") -> str:
        return sep.join(f"{'+' if p > 0 else ''}{p:.0f} {label}"
                        for p, label in self.evidence)


def evaluate(st: RegimeState, dc: DecisionState,
             tr_w: float, tr_d: float, tr_h4: float, tr_h1: float,
             ob_bull_near: bool, ob_bear_near: bool,
             fvg_bull_near: bool, fvg_bear_near: bool) -> ProbabilityState:
    ev: list[tuple[float, str]] = []

    def add(points: float, label: str) -> None:
        if points != 0:
            ev.append((points, label))

    add(18.0 * trend_sign(tr_w), "Weekly " + ("bull" if tr_w > 0 else "bear"))
    add(15.0 * trend_sign(tr_d), "Daily " + ("bull" if tr_d > 0 else "bear"))
    add(12.0 * trend_sign(tr_h4), "4H " + ("bull" if tr_h4 > 0 else "bear"))
    add(6.0 * trend_sign(tr_h1), "1H " + ("bull" if tr_h1 > 0 else "bear"))
    if dc.near_sup:
        add(dc.score_sup * 0.14, f"Support({dc.score_sup:.0f})")
    if dc.near_res:
        add(-dc.score_res * 0.14, f"Resistance({dc.score_res:.0f})")
    if ob_bull_near:
        add(10.0, "Bull OB")
    if ob_bear_near:
        add(-10.0, "Bear OB")
    if fvg_bull_near:
        add(9.0, "Bull FVG")
    if fvg_bear_near:
        add(-9.0, "Bear FVG")
    if dc.sweep_sup:
        add(12.0, "Sweep down")
    if dc.sweep_res:
        add(-12.0, "Sweep up")
    m = 10.0 * clamp(dc.mom, -1.0, 1.0)
    if abs(dc.mom) > 0.3:
        add(m, "Momentum")
    if dc.accum:
        add(8.0, "Accumulation")
    if dc.dist:
        add(-8.0, "Distribution")

    net_bull = sum(p for p, _ in ev) + (m if abs(dc.mom) <= 0.3 else 0.0)
    bull = clamp(50.0 + net_bull * 0.6, 2.0, 98.0)
    bear = 100.0 - bull
    bias = "LONG" if bull >= 58 else "SHORT" if bull <= 42 else "NEUTRAL"

    edge = abs(bull - 50.0)
    confl = max(dc.score_sup, dc.score_res)
    bad_regime = st.news or (dc.market_state == "Range" and edge < 15)
    q = 0.0 if bad_regime else edge * 0.9 + confl * 0.35 + abs(dc.htf_align) * 7.0
    quality = ("No Trade" if q < 18 else "Poor" if q < 30 else "Average" if q < 45
               else "Good" if q < 62 else "High Quality" if q < 80 else "Excellent")

    return ProbabilityState(bull_prob=bull, bear_prob=bear, bias=bias,
                            quality=quality, q_points=q, evidence=ev)
