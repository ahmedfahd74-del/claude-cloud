#!/usr/bin/env python3
"""MARKET STRUCTURE ENGINE validator — models the standalone state machine in
market_structure_engine.pine (Module 2). Price-only; NO S/R.

Proves the protected-swing break machine and the brain that sits on it:
  * a break (close) of the protected reference = BOS (with trend) or FLIP (against)
  * FLIP on the internal tier = CHoCH · FLIP on the external tier = MSS
  * trend follows the flip; protected low/high is the swing that must hold
  * HH/HL/LH/LL classification from consecutive same-side pivots
  * phase: internal aligned with external = IMPULSE, opposed = PULLBACK
  * swing strength = clamped ATR displacement of the break · confidence blend
  * determinism
"""
NONE = float("nan")
def isna(x): return x != x


class Tier:
    """One structure tier (internal OR external): protected-swing break machine.
    Mirrors the Pine per-bar logic exactly. `external` only changes the label a
    FLIP gets (MSS vs CHoCH) — the mechanics are identical."""
    def __init__(self, external=False):
        self.external = external
        self.up = NONE      # protected high (break up = bull event)
        self.dn = NONE      # protected low  (break dn = bear event)
        self.lastH = NONE
        self.lastL = NONE
        self.prevH = NONE
        self.prevL = NONE
        self.d = 0          # trend
        self.protHigh = NONE
        self.protLow = NONE
        self.lastHH = NONE; self.lastHL = NONE; self.lastLH = NONE; self.lastLL = NONE

    def pivot_high(self, price):
        isHH = isna(self.prevH) or price > self.prevH
        if isHH: self.lastHH = price
        else:    self.lastLH = price
        self.prevH = price
        self.lastH = price
        if isna(self.up):
            self.up = price
        return isHH

    def pivot_low(self, price):
        isLL = isna(self.prevL) or price < self.prevL
        if isLL: self.lastLL = price
        else:    self.lastHL = price
        self.prevL = price
        self.lastL = price
        if isna(self.dn):
            self.dn = price
        return isLL

    def on_close(self, close):
        """returns (event, strength_ref) where event in {'', 'BOS', 'CHoCH/MSS'}"""
        ev = ""
        broke = NONE
        if not isna(self.up) and close > self.up:
            flip = self.d == -1
            ev = ("MSS" if self.external else "CHoCH") if flip else "BOS"
            broke = self.up
            self.d = 1
            self.protLow = self.lastL
            self.protHigh = NONE
            self.dn = self.lastL
            self.up = NONE
        elif not isna(self.dn) and close < self.dn:
            flip = self.d == 1
            ev = ("MSS" if self.external else "CHoCH") if flip else "BOS"
            broke = self.dn
            self.d = -1
            self.protHigh = self.lastH
            self.protLow = NONE
            self.up = self.lastH
            self.dn = NONE
        return ev, broke


def phase(dir_int, dir_ext):
    return 0 if dir_ext == 0 else 1 if dir_int == dir_ext else 2

def confidence(dir_ext, dir_int, er, strength, wA=0.4, wE=0.35, wS=0.25):
    align = 1.0 if (dir_ext != 0 and dir_int == dir_ext) else 0.4 if dir_ext != 0 else 0.0
    return 100.0 * (wA*align + wE*er + wS*strength) / (wA+wE+wS)


if __name__ == "__main__":
    # ── CLAIM 1: first break establishes trend as BOS; protected level set ──
    X = Tier(external=True)
    X.pivot_low(100.0); X.pivot_high(110.0)      # up ref 110, dn ref 100
    ev, _ = X.on_close(111.0)                     # break above 110, trend was 0
    assert ev == "BOS" and X.d == 1               # establishing = BOS (not a flip)
    assert X.protLow == 100.0                      # the low that must hold
    assert isna(X.up)                              # up ref consumed

    # ── CLAIM 2: continuation break = BOS; counter break = MSS (external flip) ──
    X.pivot_high(120.0)                            # new HH → up ref 120
    ev, _ = X.on_close(121.0)
    assert ev == "BOS" and X.d == 1                # same direction → BOS
    X.pivot_low(105.0)                             # HL, dn ref already 100? dn was set on flip=protLow
    # force a downside flip: break the protected low
    ev, _ = X.on_close(99.0)
    assert ev == "MSS" and X.d == -1               # trend was bull → external flip = MSS
    assert X.protHigh == 120.0                     # last high becomes protected high

    # ── CLAIM 3: internal tier labels a flip CHoCH, not MSS ──
    I = Tier(external=False)
    I.pivot_low(50.0); I.pivot_high(60.0)
    assert I.on_close(61.0)[0] == "BOS"            # establish bull
    I.pivot_low(55.0)
    assert I.on_close(49.0)[0] == "CHoCH"          # internal flip = CHoCH

    # ── CLAIM 4: HH/HL/LH/LL classification ──
    H = Tier(external=True)
    assert H.pivot_high(100.0) is True             # first high = HH
    assert H.pivot_high(110.0) is True and H.lastHH == 110.0
    assert H.pivot_high(105.0) is False and H.lastLH == 105.0   # lower high
    assert H.pivot_low(90.0) is True and H.lastLL == 90.0       # first low = LL
    assert H.pivot_low(95.0) is False and H.lastHL == 95.0      # higher low

    # ── CLAIM 5: phase — internal aligned = IMPULSE, opposed = PULLBACK ──
    assert phase(1, 1) == 1 and phase(-1, 1) == 2 and phase(0, 1) == 2
    assert phase(1, 0) == 0                          # no external trend → no phase
    assert phase(-1, -1) == 1 and phase(1, -1) == 2

    # ── CLAIM 6: swing strength clamps at full displacement; confidence blend ──
    def strength(close, ref, atr, k):
        return min(1.0, abs(close - ref) / (atr * k))
    assert strength(112.0, 110.0, 1.0, 2.0) == 1.0   # 2 ATR clear → full
    assert abs(strength(110.5, 110.0, 1.0, 2.0) - 0.25) < 1e-9
    # confidence rises with alignment and with cleanliness/strength
    c_lo = confidence(1, -1, 0.2, 0.2)               # opposed internal, choppy
    c_hi = confidence(1,  1, 0.9, 0.9)               # aligned, clean, strong
    assert 0 <= c_lo < c_hi <= 100

    # ── CLAIM 7: deterministic — same bar stream → same events ──
    def run():
        t = Tier(external=True); out = []
        t.pivot_low(100.0); t.pivot_high(110.0)
        out.append(t.on_close(111.0)[0])
        t.pivot_high(120.0); out.append(t.on_close(121.0)[0])
        out.append(t.on_close(99.0)[0])
        return out
    assert run() == run()

    print("MARKET STRUCTURE ENGINE VALIDATED:")
    print("  protected-swing machine · BOS vs flip (CHoCH internal / MSS external),")
    print("  trend follows flip · protected low/high · HH/HL/LH/LL · phase (impulse/pullback),")
    print("  swing strength (clamped ATR displacement) + confidence blend · deterministic")
    print("  all 7 claims PASS")
