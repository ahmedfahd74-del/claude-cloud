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
    eff_ratio: float = 0.5    # Kaufman efficiency: ~1 clean trend, ~0 chop
    auto_strict: float = 0.0  # live strictness shift (Pine autoStrict, ±10)


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

        # Market noise (Kaufman efficiency ratio over 20 bars) + the live
        # ADAPTIVE-FIRST strictness shift (Pine Section 4 autoStrict parity):
        # shock/chop/low liquidity tighten; clean high-participation trends loosen.
        if i >= 20:
            path = sum(abs(closes[k] - closes[k - 1]) for k in range(i - 19, i + 1))
            eff_ratio = clamp(safe_div(abs(closes[i] - closes[i - 20]), path), 0.0, 1.0)
        else:
            eff_ratio = 0.5
        auto_strict = clamp((6.0 if news else 0.0) + (3.0 if low_liq else 0.0)
                            + (2.0 if is_compress else 0.0) + (0.5 - eff_ratio) * 10.0
                            - (4.0 if is_trending and high_liq else 0.0), -10.0, 10.0)

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
            eff_ratio=eff_ratio,
            auto_strict=auto_strict,
        ))
    return out


def mode_adjust(mode: str, st: RegimeState) -> tuple[float, float, float, float]:
    """Pine mode tuning (ADAPTIVE FIRST) → (prob_adj, score_adj, qual_adj, wick).

    "Adaptive (Auto)" derives the shifts live from the regime; the named
    presets are manual overrides. These feed ONLY gates, probability
    thresholds and sweep sensitivity — never detection or the level book.
    """
    if mode == "Conservative":
        return 5.0, 10.0, 8.0, 1.0
    if mode == "Balanced":
        return 0.0, 0.0, 0.0, 0.8
    if mode == "Aggressive":
        return -5.0, -10.0, -8.0, 0.7
    if mode == "Ultra Aggressive":
        return -10.0, -20.0, -14.0, 0.6
    a = st.auto_strict
    return a * 0.8, a * 1.5, a * 1.2, clamp(0.8 + a * 0.02, 0.6, 1.0)
