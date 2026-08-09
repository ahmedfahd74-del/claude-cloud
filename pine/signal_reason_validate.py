#!/usr/bin/env python3
"""SIGNAL-REASON validator — mirrors the filter-reason gauntlet added to the
trade-signals layer in level_core_v2.pine. Idea borrowed from sr_system's
brain.py: every "no trade" states WHY, in gate order, so the chart explains its
own silence instead of leaving you guessing.

Gauntlet precedence (first failing gate wins), per bias direction:
  fired?        -> FIRED (0 long / 1 short)      [the event outranks everything]
  signals off   -> code -1
  dir == 0      -> NO BIAS (HTF range)           code 2
  no wall       -> NO WALL in reach              code 3
  not at wall   -> WAIT (not at floor/ceiling)   code 4
  structure     -> WAIT (structure not aligned)  code 5
  R:R too low   -> SKIP (R:R < minRR)            code 6
  all pass      -> READY                         code 7

Claims:
  1. dir==0 -> NO BIAS regardless of location.
  2. long bias, price not at floor -> code 4 (location gate).
  3. at floor but leg misaligned (reqStruct) -> code 5, NOT 6.
  4. at floor + aligned + thin reward -> code 6 (R:R gate).
  5. all gates pass -> READY (7); if it's the fire bar -> FIRED (0).
  6. signals off -> -1;  no wall -> 3.
  7. short-side mirror.
"""


def signal_reason(sig_on, dir_v, LB, UB, EQ, invLB, invUB, close, low, high,
                  legDir, req_struct, atr, band, minRR, long_fire, short_fire):
    if long_fire:
        return 0, "FIRED LONG"
    if short_fire:
        return 1, "FIRED SHORT"
    if not sig_on:
        return -1, "signals off"
    if dir_v == 0:
        return 2, "NO BIAS (HTF range)"
    walls_ok = LB is not None and UB is not None and EQ is not None
    if not walls_ok:
        return 3, "NO WALL in reach"
    if dir_v == 1:
        loc = close <= EQ and (low - LB) <= atr * band
        str_ok = (not req_struct) or legDir == 1
        risk = (close - invLB) if invLB is not None else None
        rr = (EQ - close) / risk if (risk is not None and risk > 0) else 0.0
        if not loc:
            return 4, "WAIT: not at floor"
        if not str_ok:
            return 5, "WAIT: structure not aligned"
        if rr < minRR:
            return 6, f"SKIP: R:R {rr:.1f} < {minRR:.1f}"
        return 7, "READY: LONG"
    else:
        loc = close >= EQ and (UB - high) <= atr * band
        str_ok = (not req_struct) or legDir == -1
        risk = (invUB - close) if invUB is not None else None
        rr = (close - EQ) / risk if (risk is not None and risk > 0) else 0.0
        if not loc:
            return 4, "WAIT: not at ceiling"
        if not str_ok:
            return 5, "WAIT: structure not aligned"
        if rr < minRR:
            return 6, f"SKIP: R:R {rr:.1f} < {minRR:.1f}"
        return 7, "READY: SHORT"


if __name__ == "__main__":
    atr, band, minRR = 1.0, 0.5, 1.5
    # canonical long-at-floor: floor 100, ceil 112, EQ 106, invLB 98, close pulled to 100.3
    base = dict(sig_on=True, dir_v=1, LB=100.0, UB=112.0, EQ=106.0, invLB=98.0, invUB=114.0,
                close=100.3, low=100.1, high=100.5, legDir=1, req_struct=True,
                atr=atr, band=band, minRR=minRR, long_fire=False, short_fire=False)

    # 1: no bias
    assert signal_reason(**{**base, "dir_v": 0})[0] == 2

    # 2: long bias but price up near the mean (not at floor)
    assert signal_reason(**{**base, "close": 105.0, "low": 104.8})[0] == 4

    # 3: at floor but leg misaligned -> structure gate (5), not R:R
    assert signal_reason(**{**base, "legDir": -1})[0] == 5

    # 4: at floor, aligned, but reward too thin -> R:R gate (6)
    #    move close very near EQ so reward is tiny but still "at floor" via band? Instead
    #    keep at floor and raise minRR so RR fails deterministically.
    r = signal_reason(**{**base, "minRR": 5.0})
    assert r[0] == 6, r

    # 5: all gates pass -> READY (7); and on the fire bar -> FIRED (0)
    assert signal_reason(**base)[0] == 7
    assert signal_reason(**{**base, "long_fire": True})[0] == 0

    # 6: signals off / no wall
    assert signal_reason(**{**base, "sig_on": False})[0] == -1
    assert signal_reason(**{**base, "LB": None})[0] == 3

    # precedence: structure(5) reported before R:R even when BOTH fail
    both_bad = signal_reason(**{**base, "legDir": -1, "minRR": 99.0})
    assert both_bad[0] == 5, "structure gate must precede R:R gate"

    # 7: short-side mirror — at ceiling, aligned bear leg, good RR
    sh = dict(sig_on=True, dir_v=-1, LB=88.0, UB=100.0, EQ=94.0, invLB=86.0, invUB=102.0,
              close=99.7, low=99.5, high=99.9, legDir=-1, req_struct=True,
              atr=atr, band=band, minRR=minRR, long_fire=False, short_fire=False)
    assert signal_reason(**sh)[0] == 7
    assert signal_reason(**{**sh, "close": 95.0, "high": 95.2})[0] == 4   # not at ceiling
    assert signal_reason(**{**sh, "short_fire": True})[0] == 1

    print("SIGNAL-REASON VALIDATED:")
    print("  1 no-bias · 2 location · 3 structure-before-rr · 4 rr gate")
    print("  5 ready/fired · 6 off/no-wall · 7 short mirror · precedence holds")
    print("  all claims PASS")
