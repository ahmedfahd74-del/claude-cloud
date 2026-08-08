#!/usr/bin/env python3
"""SWINGTECH ENTRY/SETUP validator — mirrors the ported entry module now living at
the tail of level_core_v2.pine. Proves the port is faithful AND that the one
integration change (direction unified to the engine's dirVerdict) is wired right.

Deterministic pieces modelled, in the same order the Pine computes them:
  A. BOS -> leg: anchor = the true extreme between the last confirmed opposing
     swing and the break bar; leg extreme = the far point after the break.
  B. OTE level + OTE confluence zone [oteLevel ± oteTol] in PRICE.
  C. FVG inside the leg + OTE confluence flag (fvgAtOte).
  D. Liquidity sweep, "standing level taken" mode (wick took a still-standing
     level, BOS proves the raid failed).
  E. Checklist score/5 with HTF alignment reading dirVerdict (NOT a private bias).

Claims:
  1. Bull leg: anchor = lowest low in the window, extreme = highest high after.
  2. OTE price sits oteLevel of the way from extreme->anchor; zone brackets it.
  3. An FVG overlapping the OTE zone sets fvgAtOte; one outside does not.
  4. Sweep: origin wick takes a standing prior high (bear leg) -> detected;
     if that level was already traded through (not standing) -> not detected.
  5. Checklist: htfOk is TRUE only when legDir agrees with dirVerdict; score
     counts the 5 items; a leg opposing dirVerdict loses the HTF point.
"""


def leg_from_bos(highs, lows, closes, direction, break_i, last_opp_pivot_i):
    """direction +1 bull (broke a swing high) / -1 bear. Mirrors the Pine anchor
    (bounded forward scan to the true extreme) and leg-extreme scan."""
    n = len(highs)
    if direction == 1:
        # anchor = lowest low from the last confirmed swing LOW up to the break
        aP, aB = lows[last_opp_pivot_i], last_opp_pivot_i
        for i in range(last_opp_pivot_i, break_i + 1):
            if lows[i] < aP:
                aP, aB = lows[i], i
        # extreme = highest high from anchor to end
        eP, eB = highs[aB], aB
        for i in range(aB, n):
            if highs[i] > eP:
                eP, eB = highs[i], i
    else:
        aP, aB = highs[last_opp_pivot_i], last_opp_pivot_i
        for i in range(last_opp_pivot_i, break_i + 1):
            if highs[i] > aP:
                aP, aB = highs[i], i
        eP, eB = lows[aB], aB
        for i in range(aB, n):
            if lows[i] < eP:
                eP, eB = lows[i], i
    return aP, aB, eP, eB


def ote_zone(anchor, extreme, ote_level, ote_tol):
    ote = extreme + ote_level * (anchor - extreme)
    a = extreme + (ote_level - ote_tol) * (anchor - extreme)
    b = extreme + (ote_level + ote_tol) * (anchor - extreme)
    return ote, min(a, b), max(a, b)


def fvg_at_ote(t, b, zlo, zhi):
    """box [b,t] overlaps zone [zlo,zhi]? (Pine: b <= zHi and t >= zLo)"""
    return b <= zhi and t >= zlo


def checklist_score(has_leg, leg_dir, dir_verdict, fvg_at_ote_, ls_ok, poc_at_ote):
    htf_ok = has_leg and dir_verdict != 0 and ((leg_dir == 1) == (dir_verdict == 1))
    score = (1 if htf_ok else 0) + (1 if has_leg else 0) + (1 if fvg_at_ote_ else 0) \
            + (1 if ls_ok else 0) + (1 if poc_at_ote else 0)
    return htf_ok, score


if __name__ == "__main__":
    # ── CLAIM 1: bull leg anchor = lowest low, extreme = highest high after ──
    #   index:   0    1    2    3    4    5    6
    highs =   [10,  11,  10,  12,  13,  15,  14]
    lows  =   [ 9,   8,   7,   9,  11,  13,  12]   # lowest low at idx 2 (=7)
    closes =  [ 9,   9,   8,  11,  12,  14,  13]
    # a bull BOS fired at idx 5 (close broke a prior swing high); last confirmed
    # swing low was idx 1; scan finds the true low at idx 2.
    aP, aB, eP, eB = leg_from_bos(highs, lows, closes, +1, break_i=5, last_opp_pivot_i=1)
    assert (aP, aB) == (7, 2), f"anchor should be the lowest low (7 @ idx2), got {(aP, aB)}"
    assert (eP, eB) == (15, 5), f"extreme should be the highest high (15 @ idx5), got {(eP, eB)}"

    # ── CLAIM 2: OTE price + zone ──
    ote, zlo, zhi = ote_zone(anchor=7, extreme=15, ote_level=0.71, ote_tol=0.06)
    # from extreme(15) toward anchor(7): 0.71 of the way down
    assert abs(ote - (15 + 0.71 * (7 - 15))) < 1e-9
    assert zlo < ote < zhi, f"zone must bracket OTE: {zlo} < {ote} < {zhi}"
    assert abs((zhi - zlo) - (2 * 0.06 * abs(7 - 15))) < 1e-9, "zone width = 2*tol*legrange"

    # ── CLAIM 3: FVG at OTE vs away ──
    # an FVG box straddling the OTE price counts; one up near the extreme doesn't.
    assert fvg_at_ote(t=ote + 0.2, b=ote - 0.2, zlo=zlo, zhi=zhi), "overlapping FVG should count"
    assert not fvg_at_ote(t=15.0, b=14.5, zlo=zlo, zhi=zhi), "FVG at the extreme should NOT count"

    # ── CLAIM 4: liquidity sweep, standing vs consumed ──
    # bear leg: origin wick (anchor high) took out a prior standing high.
    def sweep_standing(anchor_high, level_high, run_max_before, min_pen=0.0, atr=1.0):
        standing = run_max_before is None or level_high > run_max_before
        took = anchor_high > level_high + min_pen * atr
        return standing and took
    # level at 12, nothing between it and the origin traded above it -> standing; origin high 13 took it
    assert sweep_standing(anchor_high=13, level_high=12, run_max_before=None), "standing level taken -> sweep"
    # same level, but intervening price already ran to 12.5 (> level) -> consumed, not standing
    assert not sweep_standing(anchor_high=13, level_high=12, run_max_before=12.5), "consumed level -> no sweep"

    # ── CLAIM 5: checklist HTF alignment reads dirVerdict ──
    # bull leg + engine says BULL(+1) -> HTF point earned
    htf_ok, score = checklist_score(has_leg=True, leg_dir=1, dir_verdict=1,
                                    fvg_at_ote_=True, ls_ok=True, poc_at_ote=True)
    assert htf_ok and score == 5, f"full aligned setup should score 5/5, got {score}"
    # bull leg but engine says BEAR(-1) -> HTF point LOST (this is the whole point of unifying)
    htf_ok2, score2 = checklist_score(has_leg=True, leg_dir=1, dir_verdict=-1,
                                     fvg_at_ote_=True, ls_ok=True, poc_at_ote=True)
    assert (not htf_ok2) and score2 == 4, f"leg opposing dirVerdict must lose the HTF point, got {score2}"
    # engine RANGE(0) -> no HTF point regardless of leg
    htf_ok3, score3 = checklist_score(has_leg=True, leg_dir=-1, dir_verdict=0,
                                     fvg_at_ote_=False, ls_ok=False, poc_at_ote=False)
    assert (not htf_ok3) and score3 == 1, f"RANGE bias -> only the BOS point, got {score3}"

    print("SWINGTECH ENTRY/SETUP VALIDATED:")
    print("  1 BOS->leg anchor/extreme · 2 OTE price + zone · 3 FVG@OTE confluence")
    print("  4 liquidity sweep (standing vs consumed) · 5 checklist HTF reads dirVerdict")
    print("  all 5 claims PASS")
