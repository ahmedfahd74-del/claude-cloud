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
