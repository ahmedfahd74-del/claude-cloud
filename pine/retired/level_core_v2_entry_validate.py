#!/usr/bin/env python3
"""M4 v3 validator — liquidity-first pipeline (models level_core_v2.pine).

Flow per confirmed execution bar (same ordering as the Pine block):
  1. update internal structure (pivots of size INTPIV) → one-shot BOS/CHoCH flags
  2. if SWEPT: resets (bias flip · window expiry · sweep-extreme reclaim)
  3. if SWEPT and bar>sweepBar: CONFIRM on internal break in bias direction → signal
  4. on signal: target = opposing liquidity (nearest strong opposing level, else
     range extreme), cooldown
  5. if IDLE: arm on a QUALIFIED sweep — gates, each logged on failure:
       ATR sweep depth · premium/discount location · level strength · rejection quality
"""
U, D = 76.0, 74.5          # resistance / support LIVE levels
ATR = 0.5
MINSWEEPATR = 0.25         # depth threshold = 0.125
MINCNF = 40.0
REJMIN = 0.5
INTPIV = 1
WIN = 20
COOL = 10
USELOC = True
LEVELS = {76.0: 80.0, 74.5: 80.0}   # price -> strength, for opposing-liquidity target


def opp_liq(dir, from_px, rng_lo, rng_hi):
    best = None
    for a, strg in LEVELS.items():
        if dir == -1 and a < from_px and strg >= MINCNF and (best is None or a > best):
            best = a
        if dir == 1 and a > from_px and strg >= MINCNF and (best is None or a < best):
            best = a
    if best is None:
        return rng_lo if dir == -1 else rng_hi
    return best


def run(bars, strength=80.0, execOK=True, useloc=USELOC):
    # bars: (hi, lo, close, dir, confirmed)
    st = 0; dirL = 0; anchor = swHi = swLo = None; swBar = 0
    cool = 0; sigs = []; rej = []
    H = [b[0] for b in bars]; L = [b[1] for b in bars]
    # internal structure state (one-shot break flags)
    iSwHi = iSwLo = None; iHiUsed = iLoUsed = True; iTrend = 0
    for b, (hi, lo, cl, d, conf) in enumerate(bars):
        if not conf or not execOK:
            continue
        # --- internal pivots of size INTPIV (confirm INTPIV bars late) ---
        iPH = iPL = None
        j = b - INTPIV
        if j - INTPIV >= 0 and j + INTPIV < len(bars):
            if all(H[j] > H[j - k] and H[j] > H[j + k] for k in range(1, INTPIV + 1)):
                iPH = H[j]
            if all(L[j] < L[j - k] and L[j] < L[j + k] for k in range(1, INTPIV + 1)):
                iPL = L[j]
        # only consider pivots confirmable by data up to current bar b
        if iPH is not None:
            iSwHi = iPH; iHiUsed = False
        if iPL is not None:
            iSwLo = iPL; iLoUsed = False
        brokeHi = iSwHi is not None and not iHiUsed and cl > iSwHi
        brokeLo = iSwLo is not None and not iLoUsed and cl < iSwLo
        chochUp = chochDn = False
        if brokeHi:
            chochUp = iTrend <= 0; iTrend = 1; iHiUsed = True
        if brokeLo:
            chochDn = iTrend >= 0; iTrend = -1; iLoUsed = True
        # running range for location + fallback targets
        rngHi = max(H[:b + 1]); rngLo = min(L[:b + 1]); eq = (rngHi + rngLo) / 2.0

        sigS = sigL = False
        # --- resets while SWEPT ---
        if st == 1:
            if d != dirL:
                rej.append("bias flipped"); st = 0
            elif b - swBar > WIN:
                rej.append("no internal break in window"); st = 0
            elif dirL == -1 and cl > swHi:
                rej.append("invalidated above sweep"); st = 0
            elif dirL == 1 and cl < swLo:
                rej.append("invalidated below sweep"); st = 0
        # --- CONFIRM: internal BOS/CHoCH after the sweep bar ---
        if st == 1 and b > swBar:
            if dirL == -1 and brokeLo:
                sigS = True
            elif dirL == 1 and brokeHi:
                sigL = True
        # --- SIGNAL ---
        if sigS or sigL:
            tgt = opp_liq(dirL, cl, rngLo, rngHi)
            sigs.append((b, 'SHORT' if sigS else 'LONG', tgt))
            cool = b + COOL; st = 0
        # --- IDLE: arm on a qualified sweep ---
        if st == 0 and not (sigS or sigL) and b >= cool and d != 0:
            rng = hi - lo
            if d == -1 and hi > U and cl <= U:
                depth = hi - U
                rq = 0 if rng <= 0 else (hi - cl) / rng
                if depth < MINSWEEPATR * ATR:
                    rej.append("shallow")
                elif useloc and U < eq:
                    rej.append("not in premium")
                elif strength < MINCNF:
                    rej.append("weak level")
                elif rq < REJMIN:
                    rej.append("weak rejection")
                else:
                    st = 1; dirL = -1; anchor = U; swHi = hi; swLo = lo; swBar = b
            elif d == 1 and lo < D and cl >= D:
                depth = D - lo
                rq = 0 if rng <= 0 else (cl - lo) / rng
                if depth < MINSWEEPATR * ATR:
                    rej.append("shallow")
                elif useloc and D > eq:
                    rej.append("not in discount")
                elif strength < MINCNF:
                    rej.append("weak level")
                elif rq < REJMIN:
                    rej.append("weak rejection")
                else:
                    st = 1; dirL = 1; anchor = D; swHi = hi; swLo = lo; swBar = b
    return sigs, rej


if __name__ == "__main__":
    BEAR, BULL = -1, 1
    # 1) full SHORT: pivot low (protected) -> sweep U (deep, premium, good rej) ->
    #    close through the internal low = bearish break -> SHORT, target opposing liq
    seq = [(75.6, 75.4, 75.5, BEAR, 1), (75.5, 75.2, 75.3, BEAR, 1),
           (75.9, 75.5, 75.8, BEAR, 1), (76.3, 75.7, 75.9, BEAR, 1),
           (75.8, 74.9, 75.0, BEAR, 1)]
    s, r = run(seq)
    assert [x[1] for x in s] == ['SHORT'] and s[0][2] == 74.5 and r == [], (s, r)
    # 2) weak level -> logged, no signal
    s, r = run(seq, strength=20.0); assert s == [] and 'weak level' in r, (s, r)
    # 3) weak rejection: deep enough sweep but closes near its high -> low wick quality
    seq3 = [x for x in seq]; seq3[3] = (76.2, 75.5, 76.0, BEAR, 1)
    s, r = run(seq3); assert s == [] and 'weak rejection' in r, (s, r)
    # 4) shallow sweep: pierces U by < 0.125 -> logged, never arms
    seq4 = [x for x in seq]; seq4[3] = (76.05, 75.7, 75.9, BEAR, 1)
    s, r = run(seq4); assert s == [] and 'shallow' in r, (s, r)
    # 5) location fail (LONG in premium): deep early low makes eq < D, so D is NOT
    #    a discount -> long at the range top is blocked and logged
    seqLoc = [(74.0, 72.5, 73.0, BULL, 1), (74.6, 74.3, 74.55, BULL, 1),
              (74.7, 74.1, 74.6, BULL, 1)]   # low 74.1 < D=74.5, closes back above
    s, r = run(seqLoc); assert s == [] and 'not in discount' in r, (s, r)
    # 6) no internal break within window -> expired logged
    seq6 = [(75.6, 75.4, 75.5, BEAR, 1), (75.5, 75.2, 75.3, BEAR, 1),
            (75.9, 75.5, 75.8, BEAR, 1), (76.3, 75.7, 75.9, BEAR, 1)] + \
           [(75.7, 75.3, 75.55, BEAR, 1)] * 24     # never closes < 75.2
    s, r = run(seq6); assert s == [] and 'no internal break in window' in r, (s, r)
    # 7) invalidation: close back above the sweep high
    seq7 = [(75.6, 75.4, 75.5, BEAR, 1), (75.5, 75.2, 75.3, BEAR, 1),
            (75.9, 75.5, 75.8, BEAR, 1), (76.3, 75.7, 75.9, BEAR, 1),
            (76.5, 75.9, 76.4, BEAR, 1)]
    s, r = run(seq7); assert s == [] and 'invalidated above sweep' in r, (s, r)
    # 8) bias flip while SWEPT -> logged reset
    seq8 = [(75.6, 75.4, 75.5, BEAR, 1), (75.5, 75.2, 75.3, BEAR, 1),
            (75.9, 75.5, 75.8, BEAR, 1), (76.3, 75.7, 75.9, BEAR, 1),
            (75.8, 75.4, 75.6, BULL, 1)]
    s, r = run(seq8); assert s == [] and 'bias flipped' in r, (s, r)
    # 9) MIXED never arms
    s, r = run([(76.3, 75.4, 75.9, 0, 1), (75.4, 74.9, 75.0, 0, 1)])
    assert s == [] and r == [], (s, r)
    # 10) LONG mirror: pivot high (protected) -> sweep D (deep, discount, good rej) ->
    #     close through the internal high = bullish break -> LONG
    seqL = [(74.9, 74.7, 74.8, BULL, 1), (75.0, 74.8, 74.95, BULL, 1),
            (74.9, 74.6, 74.7, BULL, 1), (74.7, 74.3, 74.6, BULL, 1),
            (75.2, 74.6, 75.1, BULL, 1)]
    s, r = run(seqL)
    assert [x[1] for x in s] == ['LONG'] and s[0][2] == 76.0 and r == [], (s, r)
    # 11) exec-TF gate off -> nothing
    s, r = run(seq, execOK=False); assert s == [] and r == [], (s, r)
    # 12) unconfirmed bars -> nothing
    s, r = run([(76.3, 75.4, 75.9, BEAR, 0), (75.4, 74.9, 75.0, BEAR, 0)])
    assert s == [] and r == []
    # 13) deterministic
    assert run(seq) == run(seq)
    print("M4 v3 ENTRY VALIDATED: sweep -> internal BOS/CHoCH break (short & long),")
    print("ATR sweep-depth gate, premium/discount location gate, strength gate,")
    print("rejection-quality gate, expiry/invalidation/bias-flip LOGGED, MIXED=no-trade,")
    print("exec-TF guard, no-repaint gate, opposing-liquidity target, deterministic —")
    print("all 13 scenarios PASS")
