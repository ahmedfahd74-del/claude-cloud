#!/usr/bin/env python3
"""DEALING RANGE validator — models the latched auction logic in level_core_v2.pine
and proves it fixes the jumping/vanishing that the old price-relative lookup caused.

OLD (broken):  locUB = nearest swing >= close, re-picked EVERY bar
NEW (latched): boundaries held in state; re-anchor ONLY on a confirmed CLOSE beyond a
               boundary by > breakBufPct; on a break the broken boundary FLIPS role.

Claims checked:
  1. touching a boundary does NOT move the range (the reported bug)
  2. a WICK through a boundary does NOT move it — only a CLOSE beyond does
  3. a marginal close inside the buffer does NOT move it
  4. a real break re-anchors, and the broken ceiling becomes the new floor
  5. the Claude Line is stable while price works inside the range
  6. the version counter counts REAL breaks only (not price movement)
  7. head-to-head: OLD jumps on the same walk where NEW holds
"""

NA = None


def strong_above(levels, px):
    c = [p for p, cf in levels if p > px]
    return min(c) if c else NA


def strong_below(levels, px):
    c = [p for p, cf in levels if p < px]
    return max(c) if c else NA


class OldEngine:
    """price-relative lookup, re-evaluated every bar (what the engine used to do)"""
    def __init__(self, levels):
        self.levels = levels
        self.ver = 0
        self.ub = self.lb = NA

    def bar(self, close, high=None, low=None):
        c = [p for p, cf in self.levels if p >= close]
        ub = min(c) if c else NA
        c = [p for p, cf in self.levels if p <= close]
        lb = max(c) if c else NA
        if (ub, lb) != (self.ub, self.lb):
            self.ver += 1
        self.ub, self.lb = ub, lb
        return ub, lb


class NewEngine:
    """latched dealing range (what the engine does now)"""
    def __init__(self, levels, buf_pct=0.05):
        self.levels = levels
        self.buf_pct = buf_pct
        self.ub = self.lb = NA
        self.ver = 0
        self.brk = 0

    def bar(self, close, high=None, low=None):
        # NOTE: high/low are deliberately ignored — only the CLOSE can break the range
        self.brk = 0
        buf = close * self.buf_pct / 100.0
        if self.ub is NA or self.lb is NA:
            if self.ub is NA:
                self.ub = strong_above(self.levels, close)
            if self.lb is NA:
                self.lb = strong_below(self.levels, close)
        elif close > self.ub + buf:
            self.brk = 1
            self.lb = self.ub                        # broken ceiling -> new floor
            self.ub = strong_above(self.levels, close)
            self.ver += 1
        elif close < self.lb - buf:
            self.brk = -1
            self.ub = self.lb                        # broken floor -> new ceiling
            self.lb = strong_below(self.levels, close)
            self.ver += 1
        return self.ub, self.lb

    def eq(self):
        return (self.ub + self.lb) / 2 if (self.ub is not NA and self.lb is not NA) else NA


if __name__ == "__main__":
    # scored levels: (price, CONF). All clear the qualifying threshold.
    LV = [(85.0, 60), (92.0, 55), (96.0, 70), (104.0, 65), (108.0, 58), (115.0, 62)]

    # ── CLAIM 1: touching a boundary does not move the range ──
    e = NewEngine(LV)
    e.bar(100.0)                                   # bootstrap -> 96 .. 104
    assert (e.lb, e.ub) == (96.0, 104.0), (e.lb, e.ub)
    before = (e.lb, e.ub, e.eq())
    e.bar(104.0)                                   # price CLOSES exactly ON the ceiling
    assert (e.lb, e.ub, e.eq()) == before, "range moved on a touch!"

    # ── CLAIM 2: a wick far through the ceiling does not move it — close is inside ──
    e.bar(103.0, high=112.0, low=95.0)             # big wick above 104 and below 96
    assert (e.lb, e.ub) == (96.0, 104.0), "a wick moved the range!"

    # ── CLAIM 3: a marginal close beyond, inside the buffer, does not move it ──
    e.bar(104.04)                                  # buffer at 0.05% of ~104 is ~0.052
    assert (e.lb, e.ub) == (96.0, 104.0), "a marginal poke moved the range!"

    # ── CLAIM 4: a real break re-anchors; the broken ceiling becomes the new floor ──
    v0 = e.ver
    e.bar(106.0)                                   # decisive close above 104
    assert e.brk == 1
    assert e.lb == 104.0, f"broken ceiling should become the floor, got {e.lb}"
    assert e.ub == 108.0, f"new ceiling should be the next level up, got {e.ub}"
    assert e.ver == v0 + 1

    # ── CLAIM 5: Claude Line holds still while price works inside the range ──
    e2 = NewEngine(LV)
    e2.bar(100.0)
    eqs = []
    for px in [100.0, 103.0, 103.9, 104.0, 103.5, 97.0, 96.0, 96.5, 100.0]:
        e2.bar(px)
        eqs.append(e2.eq())
    assert len(set(eqs)) == 1, f"Claude Line moved inside the range: {sorted(set(eqs))}"

    # ── CLAIM 6: every move is a REAL break — the range never drifts on its own ──
    # this walk deliberately breaks up twice, so TWO re-anchors is correct behaviour;
    # what matters is that the number of moves equals the number of counted breaks.
    e3 = NewEngine(LV)
    moves = 0
    prev = None
    for px in [100.0, 103.0, 104.0, 104.1, 107.9, 108.0, 108.1]:
        e3.bar(px)
        cur = (e3.lb, e3.ub)
        if prev is not None and cur != prev:
            moves += 1
        prev = cur
    assert moves == e3.ver, f"{moves} moves but only {e3.ver} breaks counted — silent drift"

    # ── CLAIM 7: head-to-head on the REPORTED bug — price working inside the range ──
    # price touches the ceiling, pulls back, then touches the floor. Nothing breaks.
    walk = [100.0, 103.9, 104.0, 103.0, 97.0, 96.0, 96.5, 100.0]
    old, new = OldEngine(LV), NewEngine(LV)
    old_eq, new_eq = [], []
    for px in walk:
        ub, lb = old.bar(px)
        old_eq.append((ub + lb) / 2 if (ub is not NA and lb is not NA) else NA)
        new.bar(px)
        new_eq.append(new.eq())
    old_jumps = sum(1 for a, b in zip(old_eq, old_eq[1:]) if a != b)
    new_jumps = sum(1 for a, b in zip(new_eq, new_eq[1:]) if a != b)
    assert old_jumps > 0, "control: the old engine should misbehave on this walk"
    assert new_jumps == 0, f"new engine moved {new_jumps}x with no break"
    assert new.ver == 0, "no break occurred, so the version must not increment"

    print("DEALING RANGE VALIDATED (latched, sourced from the scored book):")
    print(f"  walk (price works INSIDE the range, touching both boundaries):\n    {walk}")
    print(f"    OLD price-relative lookup : Claude Line moved {old_jumps}x  {old_eq}")
    print(f"    NEW latched range         : Claude Line moved {new_jumps}x  {new_eq}")
    print("  1 touch does not move it · 2 wick does not move it · 3 buffer holds marginal pokes")
    print("  4 real break re-anchors + broken ceiling becomes the floor")
    print("  5 Claude Line stable inside the range · 6 no silent drift (moves == breaks)")
    print("  7 head-to-head on the reported bug")
    print("  all 7 claims PASS")
