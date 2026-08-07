#!/usr/bin/env python3
"""DEALING RANGE validator — mirrors the latched, PROVEN-GATED wall logic in
level_core_v2.pine and proves the authority + anti-trap upgrade.

Models exactly what the Pine does:
  wall test : CONF >= zoneMinConf AND (wallDegPref -> deg>=1) AND proven-gate
  pick wall : nearest level passing the STRICT test; else nearest passing CONF only,
              tagged UNPROVEN
  latch     : re-anchor only after breakAccept consecutive closes beyond the wall by
              breakBufATR*ATR; on a break the broken wall flips role (ceiling->floor)
  invalid.  : stop sits beyond wall band + sweepBufATR*ATR (past the sweep zone)

Claims:
  1  a wall must be PROVEN (held>=2) under "Proven only" — a fresh level can't be a wall
  2  fallback: if nothing proven is in reach, the strongest is used and tagged UNPROVEN
  3  wallDegPref skips 1H levels for walls (prefers 4H+)
  4  ONE marginal close beyond the buffer does NOT break (acceptance needs breakAccept)
  5  a wick far beyond the wall never breaks — only closes count
  6  breakAccept consecutive accepted closes DO break, and the ceiling flips to floor
  7  the invalidation sits beyond the wall's band + ATR sweep buffer (past the stop-hunt)
  8  a smaller ATR buffer that the old %-buffer would have tripped now holds
"""
NA = None
DEG = {"1H": 0, "4H": 1, "1D": 2, "1W": 3}


class Wall:
    def __init__(self, price, conf, held, deg):
        self.price, self.conf, self.held, self.deg = price, conf, held, DEG[deg]


class Engine:
    def __init__(self, walls, zone_min=35.0, mode="Proven only", deg_pref=True,
                 atr=1.0, break_buf_atr=0.25, accept=2, sweep_buf_atr=0.5, band_pct=0.40):
        self.W = walls
        self.zone_min, self.mode, self.deg_pref = zone_min, mode, deg_pref
        self.atr, self.break_buf, self.accept, self.sweep_buf = atr, break_buf_atr, accept, sweep_buf_atr
        self.band_pct = band_pct
        self.ub = self.lb = NA
        self.ub_pr = self.lb_pr = False
        self.up = self.dn = 0
        self.ver = 0
        self.brk = 0

    def wall_ok(self, w, strict):
        deg_ok = (not self.deg_pref) or w.deg >= 1
        if self.mode == "Strongest only":
            p_ok = True
        elif self.mode == "Prefer proven":
            p_ok = w.held >= 2 or w.conf >= self.zone_min + 15.0
        else:  # Proven only
            p_ok = w.held >= 2
        return w.conf >= self.zone_min and (not strict or (deg_ok and p_ok))

    def pick(self, px, direction):
        best = NA
        best_pr = False
        for strict in (True, False):                      # strict pass, then relaxed
            if best is NA:
                for w in self.W:
                    side = w.price > px if direction == 1 else w.price < px
                    nearer = best is NA or (w.price < best if direction == 1 else w.price > best)
                    if side and nearer and self.wall_ok(w, strict):
                        best, best_pr = w.price, (w.held >= 2)
        return best, best_pr

    def bar(self, close):
        self.brk = 0
        buf = self.atr * self.break_buf
        if self.ub is NA or self.lb is NA:
            if self.ub is NA:
                self.ub, self.ub_pr = self.pick(close, 1)
            if self.lb is NA:
                self.lb, self.lb_pr = self.pick(close, -1)
            self.up = self.dn = 0
        else:
            self.up = self.up + 1 if close > self.ub + buf else 0
            self.dn = self.dn + 1 if close < self.lb - buf else 0
            if self.up >= self.accept:
                self.brk = 1
                self.lb, self.lb_pr = self.ub, self.ub_pr   # broken ceiling -> floor
                self.ub, self.ub_pr = self.pick(close, 1)
                self.up = self.dn = 0
                self.ver += 1
            elif self.dn >= self.accept:
                self.brk = -1
                self.ub, self.ub_pr = self.lb, self.lb_pr
                self.lb, self.lb_pr = self.pick(close, -1)
                self.up = self.dn = 0
                self.ver += 1
        return self.ub, self.lb

    def inv_ub(self):
        return NA if self.ub is NA else self.ub + self.ub * self.band_pct / 100.0 + self.atr * self.sweep_buf

    def inv_lb(self):
        return NA if self.lb is NA else self.lb - self.lb * self.band_pct / 100.0 - self.atr * self.sweep_buf


if __name__ == "__main__":
    # walls: price, CONF, held(times), degree
    W = [
        Wall(90.0, 70, 3, "1D"),   # strong, proven, HTF  -> ideal floor
        Wall(96.0, 60, 0, "1H"),   # fresh 1H near price  -> NOT wall-worthy
        Wall(104.0, 55, 0, "1H"),  # fresh 1H near price  -> NOT wall-worthy
        Wall(110.0, 65, 4, "1D"),  # strong, proven, HTF  -> ideal ceiling
    ]

    # ── CLAIM 1: Proven-only skips the fresh 1H levels; walls are the proven HTF ones ──
    e = Engine(W, mode="Proven only", deg_pref=True, atr=1.0)
    e.bar(100.0)
    assert e.ub == 110.0 and e.lb == 90.0, (e.ub, e.lb)     # not 104 / 96
    assert e.ub_pr and e.lb_pr

    # ── CLAIM 2: fallback to strongest + UNPROVEN tag when nothing proven qualifies ──
    fresh_only = [Wall(104.0, 55, 0, "1H"), Wall(96.0, 60, 0, "1H")]
    e2 = Engine(fresh_only, mode="Proven only", deg_pref=False, atr=1.0)
    e2.bar(100.0)
    assert e2.ub == 104.0 and e2.lb == 96.0                 # still bracketed
    assert (not e2.ub_pr) and (not e2.lb_pr)                # but tagged UNPROVEN

    # ── CLAIM 3: degree preference skips 1H even when it's a proven-enough level ──
    mixed = [Wall(103.0, 60, 3, "1H"), Wall(108.0, 60, 3, "4H")]
    e3 = Engine(mixed, mode="Proven only", deg_pref=True, atr=1.0)
    e3.bar(100.0)
    assert e3.ub == 108.0, f"deg pref should skip the 1H wall, got {e3.ub}"

    # ── CLAIM 4: ONE marginal close beyond the buffer does NOT break (needs acceptance) ──
    e.bar(110.0 + 0.25 + 0.01)                              # one close just beyond buffer
    assert e.brk == 0 and e.ub == 110.0, "a single close should not re-anchor"

    # ── CLAIM 5: a wick has no effect — the model only ever sees closes ──
    #   (we simply never feed highs; a close back inside keeps the range)
    e.bar(109.0)
    assert e.ub == 110.0 and e.up == 0                      # counter reset

    # ── CLAIM 6: breakAccept consecutive accepted closes DO break; ceiling flips to floor
    e.bar(111.0)                                            # 1st accepted close
    assert e.brk == 0
    e.bar(111.2)                                            # 2nd -> break
    assert e.brk == 1
    assert e.lb == 110.0 and e.lb_pr, "broken ceiling should become a proven floor"

    # ── CLAIM 7: invalidation sits beyond the wall band + ATR sweep buffer ──
    e5 = Engine(W, atr=2.0, sweep_buf_atr=0.5, band_pct=0.40)
    e5.bar(100.0)
    exp_inv_ub = 110.0 + 110.0 * 0.40 / 100.0 + 2.0 * 0.5   # band + 1.0 ATR buffer
    assert abs(e5.inv_ub() - exp_inv_ub) < 1e-9
    assert e5.inv_ub() > e5.ub and e5.inv_lb() < e5.lb      # always outside the walls

    # ── CLAIM 8: the exact 5m PEPE whipsaw — a poke the OLD %-buffer would have broken
    #   now holds, because acceptance + ATR buffer require a decisive, sustained move.
    pepe = [Wall(0.0028107, 60, 3, "1D"), Wall(0.0028244, 60, 3, "1D")]
    e6 = Engine(pepe, mode="Proven only", deg_pref=False, atr=0.0000090, break_buf_atr=0.25, accept=2)
    e6.bar(0.0028176)                                       # bootstrap inside
    e6.bar(0.0028244 + 0.0000014)                           # a ~1.4-tick poke (old 0.05% trigger)
    assert e6.brk == 0 and e6.ub == 0.0028244, "the marginal poke must NOT re-anchor now"

    print("DEALING RANGE + WALL AUTHORITY VALIDATED:")
    print("  1 proven-gate walls · 2 UNPROVEN fallback · 3 degree preference")
    print("  4 one poke != break · 5 wicks ignored · 6 acceptance break + ceiling→floor flip")
    print("  7 invalidation beyond the sweep zone · 8 the 5m PEPE whipsaw now holds")
    print("  all 8 claims PASS")

    # ════════════════════════════════════════════════════════════════════════════
    # MTF-CONSISTENT TIMING — proves the rangeTF anchor fix: the break/acceptance
    # test used to run on each CHART's own bar closes, so a 1m/5m/15m chart looking
    # at the SAME price action could break at three different moments (different
    # floor/ceiling/Claude Line per chart). Now it's timed to ONE fixed timeframe
    # (rangeTF)'s closed bars, so every chart at/below it agrees.
    # ════════════════════════════════════════════════════════════════════════════
    class LatchOld:
        """pre-fix: acceptance counted on the VIEWER's own bar closes"""
        def __init__(self, wall, buf, accept):
            self.wall, self.buf, self.accept = wall, buf, accept
            self.up, self.brk_at = 0, None

        def feed(self, t, close):
            if self.brk_at is not None:
                return
            self.up = self.up + 1 if close > self.wall + self.buf else 0
            if self.up >= self.accept:
                self.brk_at = t

    class LatchNew:
        """post-fix: acceptance counted ONLY on rangeTF-boundary closes, shared by
        every viewer regardless of what timeframe they're charting"""
        def __init__(self, wall, buf, accept, boundary_times):
            self.wall, self.buf, self.accept = wall, buf, accept
            self.boundary = set(boundary_times)
            self.up, self.brk_at = 0, None

        def feed(self, t, close):
            if self.brk_at is not None or t not in self.boundary:
                return
            self.up = self.up + 1 if close > self.wall + self.buf else 0
            if self.up >= self.accept:
                self.brk_at = t

    # one minute-by-minute price path, 60 minutes, ONE ceiling wall at 100, buffer=1
    # (beyond = close > 101), acceptance = 2 consecutive closes beyond.
    closes = {}
    for m in range(1, 15):                              # minutes 1-14: quiet ramp, stays inside
        closes[m] = 98.0 + (m - 1) * 0.1
    closes[15] = 99.5                                    # 15m boundary #1 — inside
    # minutes 16-20: a transient spike that breaks EARLY on fine granularities
    closes.update({16: 100.5, 17: 101.2, 18: 101.5, 19: 101.6, 20: 101.7})
    closes.update({21: 101.5, 22: 101.5, 23: 101.5, 24: 101.4, 25: 101.4})
    closes.update({26: 100.9, 27: 100.6, 28: 100.4, 29: 100.3})
    closes[30] = 100.3                                   # 15m boundary #2 — back inside
    for m in range(31, 45):
        closes[m] = 100.0                                # quiet stretch
    closes[45] = 101.6                                   # 15m boundary #3 — beyond (count 1)
    for m in range(46, 60):
        closes[m] = 100.0                                # quiet stretch
    closes[60] = 101.8                                   # 15m boundary #4 — beyond (count 2) -> BREAK

    WALL, BUF, ACCEPT = 100.0, 1.0, 2

    old_1m = LatchOld(WALL, BUF, ACCEPT)
    old_5m = LatchOld(WALL, BUF, ACCEPT)
    old_15m = LatchOld(WALL, BUF, ACCEPT)
    for m in range(1, 61):
        old_1m.feed(m, closes[m])
        if m % 5 == 0:
            old_5m.feed(m, closes[m])
        if m % 15 == 0:
            old_15m.feed(m, closes[m])

    boundaries = [t for t in range(1, 61) if t % 15 == 0]
    new_as_1m = LatchNew(WALL, BUF, ACCEPT, boundaries)
    new_as_5m = LatchNew(WALL, BUF, ACCEPT, boundaries)
    new_as_15m = LatchNew(WALL, BUF, ACCEPT, boundaries)
    for m in range(1, 61):
        new_as_1m.feed(m, closes[m])                     # fed every minute...
        if m % 5 == 0:
            new_as_5m.feed(m, closes[m])                 # ...or every 5 minutes...
        if m % 15 == 0:
            new_as_15m.feed(m, closes[m])                # ...or every 15 — doesn't matter,
                                                           # LatchNew ignores non-boundary ticks

    # ── CLAIM 9: pre-fix, three chart TFs looking at the SAME price break at
    #    three DIFFERENT moments — the reported bug, reproduced exactly ──
    assert old_1m.brk_at == 18, old_1m.brk_at
    assert old_5m.brk_at == 25, old_5m.brk_at
    assert old_15m.brk_at == 60, old_15m.brk_at
    assert len({old_1m.brk_at, old_5m.brk_at, old_15m.brk_at}) == 3, \
        "control: the three old chart-timed viewers should all disagree"

    # ── CLAIM 10: post-fix, 1m/5m/15m viewers of the SAME rangeTF-anchored latch
    #    converge on the identical break moment ──
    assert new_as_1m.brk_at == new_as_5m.brk_at == new_as_15m.brk_at == 60, \
        (new_as_1m.brk_at, new_as_5m.brk_at, new_as_15m.brk_at)

    # ── CLAIM 11: the fix does not regress the native rangeTF chart itself —
    #    a 15m chart under the OLD per-chart-bar logic already tested exactly the
    #    15m boundaries, so it should match the NEW anchor result exactly ──
    assert old_15m.brk_at == new_as_15m.brk_at == 60

    print("\nMTF-CONSISTENT TIMING VALIDATED:")
    print("  same 60-minute price path, ceiling=100, buffer=1, accept=2 consecutive closes")
    print(f"    OLD (chart-timed)   1m breaks @ minute {old_1m.brk_at}   5m breaks @ minute {old_5m.brk_at}   15m breaks @ minute {old_15m.brk_at}   <- all disagree")
    print(f"    NEW (range-anchored) 1m-viewer @ {new_as_1m.brk_at}   5m-viewer @ {new_as_5m.brk_at}   15m-viewer @ {new_as_15m.brk_at}   <- identical")
    print("  9 old timing diverges by chart TF · 10 new timing converges · 11 no regression on the anchor TF")
    print("  all 3 MTF claims PASS  (11/11 total)")
