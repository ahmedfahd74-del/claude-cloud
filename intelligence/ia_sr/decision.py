"""Decision Engine — Pine Section 10 port.

Derives the reusable decision metrics and the priority-ordered Market State
from what the earlier engines already produced. No new detection logic.
"""
from __future__ import annotations

from dataclasses import dataclass

from .indicators import Bar, clamp, safe_div
from .levels import LevelBook, nearest
from .regime import RegimeState, trend_sign


@dataclass
class DecisionState:
    dist_res_atr: float
    score_res: float
    dist_sup_atr: float
    score_sup: float
    near_res: bool
    near_sup: bool
    htf_align: int
    htf_bull: bool
    htf_bear: bool
    mom: float
    accum: bool
    dist: bool
    sweep_res: bool
    sweep_sup: bool
    market_state: str


def evaluate(bars: list[Bar], i: int, st: RegimeState, books: list[LevelBook],
             tr_w: float, tr_d: float, tr_h4: float) -> DecisionState:
    bar = bars[i]
    d_res, s_res, d_sup, s_sup = nearest(books, bar.close)
    dist_res_atr = safe_div(d_res, st.atr_fast)
    dist_sup_atr = safe_div(d_sup, st.atr_fast)
    near_res = dist_res_atr < 0.5
    near_sup = dist_sup_atr < 0.5

    htf_align = trend_sign(tr_w) + trend_sign(tr_d) + trend_sign(tr_h4)

    mom = safe_div(bar.close - bars[i - 10].close, st.atr_fast) if i >= 10 else 0.0
    mom_prev = safe_div(bars[i - 5].close - bars[i - 15].close, st.atr_fast) if i >= 15 else 0.0
    decel = abs(mom) < abs(mom_prev)

    lookback = bars[max(0, i - 19): i + 1]
    rng_hi = max(b.high for b in lookback)
    rng_lo = min(b.low for b in lookback)
    pos = safe_div(bar.close - rng_lo, rng_hi - rng_lo)
    range_env = not st.is_trending and not st.is_expand
    accum = range_env and pos < 0.40 and st.high_liq
    dist = range_env and pos > 0.60 and st.high_liq

    wick_up = safe_div(bar.high - max(bar.open, bar.close), st.atr_fast)
    wick_dn = safe_div(min(bar.open, bar.close) - bar.low, st.atr_fast)
    sweep_res = wick_up > 0.8 and near_res
    sweep_sup = wick_dn > 0.8 and near_sup
    sweep_bar = sweep_res or sweep_sup

    htf_bull = htf_align > 0
    htf_bear = htf_align < 0
    state = "Range"
    if st.news and sweep_bar:
        state = "Liquidity Hunt"
    elif st.is_compress:
        state = "Breakout Preparation"
    elif st.is_expand and st.is_trending:
        state = "Trend Expansion"
    elif st.is_trending and decel:
        state = "Trend Exhaustion"
    elif st.is_trending:
        state = "Momentum Continuation"
    elif accum:
        state = "Accumulation"
    elif dist:
        state = "Distribution"
    elif ((near_res and htf_bear and s_res >= st.ad_min_score)
          or (near_sup and htf_bull and s_sup >= st.ad_min_score)):
        state = "Reversal Risk"

    return DecisionState(
        dist_res_atr=dist_res_atr, score_res=s_res,
        dist_sup_atr=dist_sup_atr, score_sup=s_sup,
        near_res=near_res, near_sup=near_sup,
        htf_align=htf_align, htf_bull=htf_bull, htf_bear=htf_bear,
        mom=clamp(mom, -10.0, 10.0), accum=accum, dist=dist,
        sweep_res=sweep_res, sweep_sup=sweep_sup,
        market_state=state,
    )
