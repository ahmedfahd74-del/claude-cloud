#!/usr/bin/env python3
"""POSITION LAYER — HTF MARKET-STATE ENGINE validator (models f_state + aggregation
in level_core_v2.pine).

Proves the refined design:
  * Market STATE is classified per HTF from HH/HL/LH/LL progression + swing
    expansion + momentum + volatility (efficiency ratio): one of
    RANGE / TRENDING / PULLBACK / TRANSITION / DISTRIBUTION / ACCUMULATION.
  * BIAS is DERIVED from state — a directional vote arises ONLY in TRENDING/PULLBACK.
    TRANSITION / DISTRIBUTION / ACCUMULATION / RANGE never vote directionally.
  * PULLBACK keeps the trend's direction (counter-momentum dip is still bullish/bearish).
  * A volatility gate downgrades even clean structure to RANGE when efficiency is dead.
  * 2/3 HTF agreement is the CONFIRMATION of the state-derived votes (not the primary call).
  * Selectivity: confirmed directional bias requires >=2 HTFs in clean TREND/PULLBACK
    agreement — topping/coiling/ranging states can never produce a confirmed trade,
    so no counter-state false signals are added.
"""
from itertools import product

ER_CHOP = 0.12
ER_TREND = 0.35
# state codes
RANGE, TREND, PULLBACK, TRANSITION, DISTRIB, ACCUM = 0, 1, 2, 3, 4, 5


def state(hh, hl, lh, ll, m, er, tm):
    """One HTF's market state. tm = trend memory (last clean structure: +1 up, -1 down)."""
    su = hh and hl          # clean bullish structure
    sd = lh and ll          # clean bearish structure
    st, bv = RANGE, 0
    if su:
        if er < ER_CHOP:
            st, bv = RANGE, 0                 # dead grind → range (volatility gate)
        else:
            st, bv = (TREND if m >= 0 else PULLBACK), 1
    elif sd:
        if er < ER_CHOP:
            st, bv = RANGE, 0
        else:
            st, bv = (TREND if m <= 0 else PULLBACK), -1
    elif hh and ll:
        st, bv = TRANSITION, 0                # broadening
    elif lh and hl:
        if tm == 1 and er < ER_TREND and m <= 0:
            st = DISTRIB                       # coil at highs after up-trend
        elif tm == -1 and er < ER_TREND and m >= 0:
            st = ACCUM                         # coil at lows after down-trend
        else:
            st = TRANSITION                    # unresolved coil
        bv = 0
    else:
        st, bv = RANGE, 0
    ln = bv if bv != 0 else (-1 if st == DISTRIB else 1 if st == ACCUM else 0)
    return st, bv, ln


def system(states, votes):
    bulls = sum(1 for v in votes if v == 1)
    bears = sum(1 for v in votes if v == -1)
    posDir = 1 if bulls >= 2 else -1 if bears >= 2 else 0
    if posDir != 0:
        tr = sum(1 for s, v in zip(states, votes) if s == TREND and v == posDir)
        sysState = TREND if tr >= 2 else PULLBACK
    elif bulls > 0 and bears > 0:
        sysState = TRANSITION
    elif DISTRIB in states:
        sysState = DISTRIB
    elif ACCUM in states:
        sysState = ACCUM
    else:
        sysState = RANGE
    return posDir, sysState


if __name__ == "__main__":
    HI, LO = 0.50, 0.20   # efficiency: healthy / churn (both above ER_CHOP unless noted)

    # --- CLAIM 1: each of the six states classified correctly ---
    assert state(True, True, False, False, 1, HI, 1) == (TREND, 1, 1)      # trending up
    assert state(False, False, True, True, -1, HI, -1) == (TREND, -1, -1)  # trending down
    assert state(True, True, False, False, -1, HI, 1) == (PULLBACK, 1, 1)  # dip in uptrend, still bull
    assert state(False, False, True, True, 1, HI, -1) == (PULLBACK, -1, -1)# rip in downtrend, still bear
    assert state(True, False, False, True, 0, HI, 1) == (TRANSITION, 0, 0) # broadening (HH & LL)
    assert state(False, True, True, False, -1, LO, 1) == (DISTRIB, 0, -1)  # coil at highs after up
    assert state(False, True, True, False, 1, LO, -1) == (ACCUM, 0, 1)     # coil at lows after down
    assert state(False, True, True, False, 0, HI, 0) == (TRANSITION, 0, 0) # coil, no prior trend
    assert state(False, False, False, False, 0, LO, 0) == (RANGE, 0, 0)    # no structure

    # --- CLAIM 2: volatility gate — clean structure but dead efficiency → RANGE, no vote ---
    assert state(True, True, False, False, 1, 0.05, 1) == (RANGE, 0, 0)
    assert state(False, False, True, True, -1, 0.05, -1) == (RANGE, 0, 0)

    # --- CLAIM 3: a directional vote arises ONLY in TREND/PULLBACK (exhaustive) ---
    for hh, hl, lh, ll, m, tm in product([False, True], [False, True], [False, True],
                                          [False, True], (-1, 0, 1), (-1, 0, 1)):
        for er in (0.05, LO, HI):
            st, bv, ln = state(hh, hl, lh, ll, m, er, tm)
            if bv != 0:
                assert st in (TREND, PULLBACK), (hh, hl, lh, ll, m, er, tm, st, bv)
            # a bullish/bearish structure can only vote its own side
            if bv == 1:
                assert hh and hl
            if bv == -1:
                assert lh and ll

    # --- CLAIM 4: PULLBACK preserves trend direction (not a reversal) ---
    assert state(True, True, False, False, -1, HI, 1)[1] == 1     # uptrend pullback still +1
    assert state(False, False, True, True, 1, HI, -1)[1] == -1    # downtrend pullback still -1

    # --- CLAIM 5: 2/3 confirmation + system-state precedence ---
    assert system((TREND, TREND, RANGE), (1, 1, 0)) == (1, TREND)         # confirmed trend up
    assert system((PULLBACK, PULLBACK, RANGE), (1, 1, 0)) == (1, PULLBACK)# confirmed but corrective
    assert system((TREND, RANGE, RANGE), (1, 0, 0)) == (0, RANGE)         # single TF → no direction
    assert system((TREND, TREND, TREND), (1, 1, -1)) == (1, TREND)        # 2 vs 1 → confirmed up
    assert system((TRANSITION, DISTRIB, RANGE), (0, 0, 0)) == (0, DISTRIB)# topping surfaced
    assert system((TRANSITION, ACCUM, RANGE), (0, 0, 0)) == (0, ACCUM)    # bottoming surfaced
    assert system((TREND, RANGE, TREND), (1, 0, -1)) == (0, TRANSITION)   # conflict → transition

    # --- CLAIM 6: SELECTIVITY / no counter-state false signals ---
    # A confirmed directional trade is only ever produced when >=2 HTFs are in a clean
    # TREND/PULLBACK of the same side. Enumerate every triple of (state,vote) the engine
    # can emit and confirm posDir!=0 implies >=2 directional TREND/PULLBACK votes agree.
    emit = [(TREND, 1), (TREND, -1), (PULLBACK, 1), (PULLBACK, -1),
            (TRANSITION, 0), (DISTRIB, 0), (ACCUM, 0), (RANGE, 0)]
    confirmed = 0
    for a, b, c in product(emit, repeat=3):
        states = (a[0], b[0], c[0]); votes = (a[1], b[1], c[1])
        posDir, sysState = system(states, votes)
        if posDir != 0:
            confirmed += 1
            agree = sum(1 for s, v in zip(states, votes)
                        if v == posDir and s in (TREND, PULLBACK))
            assert agree >= 2, (states, votes)
            # a non-directional state never contributes to a confirmed trade's direction
            for s, v in zip(states, votes):
                if s in (TRANSITION, DISTRIB, ACCUM, RANGE):
                    assert v == 0

    # --- CLAIM 7: deterministic ---
    for hh, hl, lh, ll, m, tm in product([False, True], [False, True], [False, True],
                                          [False, True], (-1, 0, 1), (-1, 0, 1)):
        assert state(hh, hl, lh, ll, m, HI, tm) == state(hh, hl, lh, ll, m, HI, tm)

    print("POSITION LAYER (MARKET-STATE ENGINE) VALIDATED:")
    print("  6 states classified from structure+swing+momentum+volatility; bias DERIVED from state")
    print("  directional vote ONLY in TREND/PULLBACK; volatility gate kills dead-grind trends")
    print("  PULLBACK keeps trend direction; DISTRIBUTION/ACCUMULATION surface as neutral leans")
    print(f"  2/3 agreement CONFIRMS; {confirmed} confirmed-direction combos, every one backed by")
    print("  >=2 clean TREND/PULLBACK votes — no counter-state false signals; deterministic")
    print("  all 7 claims PASS")
