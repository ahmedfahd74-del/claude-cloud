"""Adaptive Engine — Pine Sections 3-4 port.

Classifies each bar's regime from unitless, asset-agnostic signals and emits
the adaptive parameters every downstream module consumes. Works on any
timeframe of any asset with no tuning, exactly like the Pine build.
"""
from __future__ import annotations

from dataclasses import dataclass

from .indicators import Bar, NAN, atr, clamp, ema, isnan, safe_div, sma, stdev

MAXLEG = 14  # Pine MAXLEG — hard ceiling on the adaptive pivot leg


@dataclass
class RegimeState:
    atr_fast: float
    atr_safe: float
    vol_regime: float
    vol_mult: float
    trend: float          # normalised EMA slope (Pine slopeRaw / per-TF tr)
    trend_str: float
    trend_up: bool
    is_trending: bool
    is_compress: bool
    is_expand: bool
    vol_ratio: float
    high_liq: bool
    low_liq: bool
    news: bool
    regime_txt: str
    leg: int
    ad_zone: float
    ad_atr: float
    ad_react: float
    ad_min_score: int
    ad_merge: float


def trend_sign(tr: float) -> int:
    """Pine f_trendSign."""
    if isnan(tr):
        return 0
    return 1 if tr > 0.15 else -1 if tr < -0.15 else 0


def trend_state(tr: float) -> str:
    """Pine f_trendState."""
    s = trend_sign(tr)
    return "BULL" if s > 0 else "BEAR" if s < 0 else "RANGE"


def compute_regime(bars: list[Bar], sens_bias: float = 1.0) -> list[RegimeState]:
    n = len(bars)
    closes = [b.close for b in bars]
    vols = [b.volume for b in bars]
    a_fast = atr(bars, 14)
    a_slow = atr(bars, 50)
    ema34 = ema(closes, 34)
    basis = sma(closes, 20)
    bbw = [safe_div(sd, bs) if not (isnan(sd) or isnan(bs)) else NAN
           for sd, bs in zip(stdev(closes, 20), basis)]
    bbw_avg = sma([0.0 if isnan(v) else v for v in bbw], 100)
    vol_avg = sma(vols, 20)

    out: list[RegimeState] = []
    for i in range(n):
        af = a_fast[i]
        atr_safe = closes[i] * 0.001 if isnan(af) else af
        vol_regime = safe_div(af, a_slow[i]) if not isnan(af) else 0.0
        vol_mult = clamp(vol_regime, 0.5, 2.5)

        slope = 0.0
        if i >= 10 and not isnan(ema34[i]) and not isnan(ema34[i - 10]):
            slope = safe_div(ema34[i] - ema34[i - 10], af)
        trend_str_v = clamp(abs(slope), 0.0, 3.0)
        trend_up = slope > 0
        is_trending = trend_str_v > 1.0

        is_compress = (not isnan(bbw_avg[i]) and not isnan(bbw[i])
                       and bbw[i] < bbw_avg[i] * 0.80)
        is_expand = (not isnan(bbw_avg[i]) and not isnan(bbw[i])
                     and bbw[i] > bbw_avg[i] * 1.20)

        vol_ratio = safe_div(vols[i], vol_avg[i]) if not isnan(vol_avg[i]) else 0.0
        high_liq = vol_ratio > 1.3
        low_liq = vol_ratio < 0.6

        atr_spike = i >= 5 and not isnan(a_fast[i - 5]) and safe_div(af, a_fast[i - 5]) > 1.6
        gap_move = i >= 1 and safe_div(abs(bars[i].open - closes[i - 1]), af) > 0.8
        news = bool(atr_spike or gap_move)

        regime_txt = ("NEWS / SHOCK" if news else
                      "EXPANSION / BREAKOUT" if is_expand else
                      "COMPRESSION / RANGE" if is_compress else
                      ("TREND " + ("UP" if trend_up else "DOWN")) if is_trending else
                      "NEUTRAL")

        leg = int(clamp(round(5 * vol_mult / sens_bias), 3, MAXLEG))
        out.append(RegimeState(
            atr_fast=af,
            atr_safe=atr_safe,
            vol_regime=vol_regime,
            vol_mult=vol_mult,
            trend=slope,
            trend_str=trend_str_v,
            trend_up=trend_up,
            is_trending=is_trending,
            is_compress=is_compress,
            is_expand=is_expand,
            vol_ratio=vol_ratio,
            high_liq=high_liq,
            low_liq=low_liq,
            news=news,
            regime_txt=regime_txt,
            leg=leg,
            ad_zone=clamp(vol_mult * (1.4 if is_expand else 0.7 if is_compress else 1.0) * sens_bias, 0.4, 3.0),
            ad_atr=clamp(1.0 * vol_mult, 0.6, 2.5),
            ad_react=clamp(0.8 * vol_mult, 0.4, 2.0),
            ad_min_score=int(clamp(45 + (20 if news else 0) + (10 if low_liq else 0), 40, 80)),
            ad_merge=clamp(0.6 * vol_mult, 0.3, 1.5),
        ))
    return out
