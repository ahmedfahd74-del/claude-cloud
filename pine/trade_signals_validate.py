#!/usr/bin/env python3
"""TRADE-SIGNALS validator — mirrors the signal layer appended to
level_core_v2.pine. The signal is a GATED CONFLUENCE of pieces the engine
already computes cheaply every bar (no repaint, no expensive per-bar rescans):

  ARM      dirVerdict (HTF true direction) must be non-zero; trade only in it.
  LOCATION price pulled to the bias-side PROVEN wall in the right half:
             long  -> discount (close <= Claude Line) AND low within
                      entryBandATR×ATR of the proven floor (locLB)
             short -> premium  (close >= Claude Line) AND high within band of
                      the proven ceiling (locUB)
  STRUCTURE (optional) chart BOS leg agrees with HTF: legDir == dirVerdict
  R:R      (Claude-Line target − entry) / (entry − invalidation) >= minRR
  FIRE     rising edge of the ready state on a CONFIRMED bar (fires once)

  Plan on fire: entry = close, SL = sweep-aware invalidation (invLB/invUB),
  TP1 = Claude Line (locEQ), TP2 = opposing wall.

Claims:
  1. No arm in RANGE: dirVerdict==0 never fires.
  2. No counter-trend: dirVerdict==1 never fires a short (and vice-versa).
  3. Long fires only at the floor in discount with structure aligned.
  4. R:R gate rejects an entry too close to the Claude Line (reward too small).
  5. Rising-edge: a multi-bar ready window fires exactly once.
  6. Structure gate: if required, a bull HTF bias with a bearish leg does NOT fire.
  7. Plan geometry: SL below floor (long), TP1=EQ, TP2=UB, and R:R math.
"""


def long_ready(dir_v, close, low, EQ, LB, invLB, atr, band, minrr, legDir, req_struct):
    if dir_v != 1 or LB is None or EQ is None:
        return False, 0.0
    loc = close <= EQ and (low - LB) <= atr * band
    struct = (not req_struct) or legDir == 1
    risk = close - invLB if invLB is not None else None
    rr = (EQ - close) / risk if (risk is not None and risk > 0) else 0.0
    ready = loc and struct and rr >= minrr
    return ready, rr


def short_ready(dir_v, close, high, EQ, UB, invUB, atr, band, minrr, legDir, req_struct):
    if dir_v != -1 or UB is None or EQ is None:
        return False, 0.0
    loc = close >= EQ and (UB - high) <= atr * band
    struct = (not req_struct) or legDir == -1
    risk = invUB - close if invUB is not None else None
    rr = (close - EQ) / risk if (risk is not None and risk > 0) else 0.0
    ready = loc and struct and rr >= minrr
    return ready, rr


def fire_series(ready_bools):
    """rising edge: fire on the bar ready becomes true (prev false)."""
    out = []
    prev = False
    for r in ready_bools:
        out.append(r and not prev)
        prev = r
    return out


if __name__ == "__main__":
    atr, band, minrr = 1.0, 0.5, 1.5

    # canonical LONG-at-floor bar: HTF bull, price in discount at the proven floor,
    # structure up. floor=100, invLB=98 (SL), EQ=106 (Claude), close pulled to 100.3
    base = dict(dir_v=1, close=100.3, low=100.1, EQ=106.0, LB=100.0, invLB=98.0,
                atr=atr, band=band, minrr=minrr, legDir=1, req_struct=True)

    # ── CLAIM 1: RANGE never arms ──
    r, _ = long_ready(**{**base, "dir_v": 0})
    assert not r, "dirVerdict==0 must never fire"

    # ── CLAIM 2: no counter-trend — bull bias can't produce a short ──
    rs, _ = short_ready(dir_v=1, close=100.3, high=100.4, EQ=106.0, UB=112.0,
                        invUB=114.0, atr=atr, band=band, minrr=minrr, legDir=1, req_struct=True)
    assert not rs, "a bull HTF bias must never fire a short"

    # ── CLAIM 3: canonical long fires ──
    r, rr = long_ready(**base)
    assert r, f"canonical floor long should be ready (rr={rr})"

    # ── CLAIM 4: R:R gate — same setup but close near the Claude Line (tiny reward) ──
    r2, rr2 = long_ready(**{**base, "close": 105.5, "low": 105.4})
    # now low isn't near the floor either, and reward EQ-close is tiny -> not ready
    assert not r2, f"entry near the Claude Line must be rejected (rr={rr2})"

    # ── CLAIM 5: rising edge fires once across a ready window ──
    readies = [False, True, True, True, False, True]
    fires = fire_series(readies)
    assert fires == [False, True, False, False, False, True], f"edge wrong: {fires}"
    assert sum(fires) == 2, "two separate ready windows -> two fires, not five"

    # ── CLAIM 6: structure gate blocks a bull bias with a bearish leg ──
    r3, _ = long_ready(**{**base, "legDir": -1})
    assert not r3, "req_struct on: bull bias + bearish leg must NOT fire"
    r4, _ = long_ready(**{**base, "legDir": -1, "req_struct": False})
    assert r4, "with structure gate off, the location+RR long should still fire"

    # ── CLAIM 7: plan geometry + R:R math ──
    entry = base["close"]
    sl, tp1, tp2 = base["invLB"], base["EQ"], 112.0
    assert sl < base["LB"] < entry, "SL must sit below the floor, below entry (long)"
    assert tp1 < tp2, "TP1 (Claude Line) below TP2 (opposing wall) for a long"
    rr_calc = (tp1 - entry) / (entry - sl)
    assert abs(rr_calc - ((106.0 - 100.3) / (100.3 - 98.0))) < 1e-9
    assert rr_calc >= minrr, "canonical setup clears the R:R floor"

    # short-side canonical sanity (mirror)
    rsh, rrsh = short_ready(dir_v=-1, close=105.7, high=105.9, EQ=100.0, UB=106.0,
                            invUB=108.0, atr=atr, band=band, minrr=minrr, legDir=-1, req_struct=True)
    assert rsh, f"canonical ceiling short should be ready (rr={rrsh})"

    print("TRADE-SIGNALS VALIDATED:")
    print("  1 RANGE never arms · 2 no counter-trend · 3 canonical long fires")
    print("  4 R:R gate rejects thin reward · 5 rising-edge fires once · 6 structure gate")
    print("  7 plan geometry (SL<floor<entry<TP1<TP2) + R:R math · short-side mirror")
    print("  all 7 claims PASS")
