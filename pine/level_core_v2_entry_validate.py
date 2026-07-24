#!/usr/bin/env python3
"""M4 validator — liquidity-first entry state machine (models level_core_v2.pine).
Proves: arm only on bias-aligned sweep of the LIVE level; confirm = close through
sweep bar's opposite extreme within window; expiry, invalidation, bias-flip reset,
cooldown, MIXED = no signals, no-repaint gate, determinism."""
CONFIRM=3; COOL=10

def run(bars):
    # bars: (bar_index, hi, lo, close, nUp, nDn, dir, confirmed)
    st=0; dirL=0; swHi=swLo=anchor=None; swBar=0; cool=0; sigs=[]
    for b,hi,lo,cl,nUp,nDn,d,conf in bars:
        if not conf: continue                        # no-repaint gate
        sigS=sigL=False
        if st==1:
            if b-swBar>CONFIRM or d!=dirL: st=0
            elif dirL==-1:
                if cl<swLo: sigS=True
                elif cl>swHi: st=0
            else:
                if cl>swHi: sigL=True
                elif cl<swLo: st=0
        if sigS or sigL:
            sigs.append((b,'SHORT' if sigS else 'LONG',anchor)); cool=b+COOL; st=0
        if st==0 and not(sigS or sigL) and b>=cool and d!=0:
            if d==-1 and nUp is not None and hi>nUp and cl<=nUp:
                st=1; dirL=-1; anchor=nUp; swHi=hi; swLo=lo; swBar=b
            elif d==1 and nDn is not None and lo<nDn and cl>=nDn:
                st=1; dirL=1; anchor=nDn; swHi=hi; swLo=lo; swBar=b
    return sigs

if __name__=="__main__":
    U,D=76.0,75.0   # LIVE ceiling / floor
    # 1) bear: sweep ceiling then confirm -> SHORT
    s=run([(1,75.5,75.2,75.4,U,D,-1,1),(2,76.3,75.4,75.9,U,D,-1,1),(3,75.8,75.1,75.2,U,D,-1,1)])
    assert [x[1] for x in s]==['SHORT'] and s[0][2]==U, s
    # 2) no confirm in window -> expire, no signal
    s=run([(1,76.3,75.4,75.9,U,D,-1,1)]+[(b,75.9,75.5,75.7,U,D,-1,1) for b in range(2,8)])
    assert s==[], s
    # 3) close above sweep high while armed -> invalidated
    s=run([(1,76.3,75.4,75.9,U,D,-1,1),(2,76.6,75.8,76.5,U,D,-1,1),(3,75.8,75.1,75.2,U,D,-1,1)])
    assert s==[], s
    # 4) MIXED bias -> never arms
    s=run([(1,76.3,75.4,75.9,U,D,0,1),(2,75.8,75.1,75.2,U,D,0,1)])
    assert s==[], s
    # 5) bias flips while armed -> reset
    s=run([(1,76.3,75.4,75.9,U,D,-1,1),(2,75.8,75.1,75.2,U,D,1,1)])
    assert s==[], s
    # 6) cooldown blocks immediate re-arm
    seq=[(1,76.3,75.4,75.9,U,D,-1,1),(2,75.8,75.1,75.2,U,D,-1,1),   # signal @2
         (3,76.4,75.5,75.9,U,D,-1,1),(4,75.8,75.0,75.1,U,D,-1,1)]   # sweep in cooldown ignored
    s=run(seq); assert len(s)==1, s
    # 7) long mirror: bull bias, sweep floor, confirm above sweep high -> LONG
    s=run([(1,75.6,74.8,75.2,U,D,1,1),(2,75.9,75.3,75.7,U,D,1,1)])
    assert [x[1] for x in s]==['LONG'] and s[0][2]==D, s
    # 8) unconfirmed bars change nothing
    s=run([(1,76.3,75.4,75.9,U,D,-1,0),(2,75.8,75.1,75.2,U,D,-1,0)])
    assert s==[], s
    # 9) deterministic
    seq=[(1,75.5,75.2,75.4,U,D,-1,1),(2,76.3,75.4,75.9,U,D,-1,1),(3,75.8,75.1,75.2,U,D,-1,1)]
    assert run(seq)==run(seq)
    print("M4 ENTRY VALIDATED: sweep-arm, confirm, expiry, invalidation, bias-flip reset,")
    print("cooldown, MIXED=no-signal, no-repaint gate, deterministic — all 9 scenarios PASS")
