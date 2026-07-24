#!/usr/bin/env python3
"""M4 v2 validator — liquidity-first pipeline (models level_core_v2.pine):
HTF bias -> sweep of STRONG level -> rejection quality -> LH/HL micro-pivot ->
LL/HH break -> signal. Gates log every rejected setup with a reason."""
MINCNF=40.0; REJMIN=0.5; N=1; WIN=20; COOL=10

def run(bars, strength=80.0, execOK=True):
    # bars: (hi, lo, close, dir, confirmed); nUp/nDn fixed per call
    U,D=76.0,74.5
    st=0; dirL=0; swHi=swLo=anchor=None; swBar=0
    seqLo=seqHi=None; ref=None; cool=0
    sigs=[]; rej=[]
    H=[b[0] for b in bars]
    for b,(hi,lo,cl,d,conf) in enumerate(bars):
        if not conf or not execOK: continue
        sigS=sigL=False
        # pivots (n=1) confirmed this bar at b-1
        ph = H[b-1] if b>=2 and H[b-1]>H[b-2] and H[b-1]>H[b] else None
        L=[x[1] for x in bars]
        pl = L[b-1] if b>=2 and L[b-1]<L[b-2] and L[b-1]<L[b] else None
        if st>0:
            seqLo=min(seqLo,lo); seqHi=max(seqHi,hi)
        if st>0:
            if d!=dirL: rej.append("bias flipped"); st=0
            elif b-swBar>WIN: rej.append("window expired"); st=0
            elif dirL==-1 and cl>swHi: rej.append("invalidated above sweep"); st=0
            elif dirL==1 and cl<swLo: rej.append("invalidated below sweep"); st=0
        if st==1:
            if dirL==-1 and ph is not None and (b-N)>swBar:
                if ph<swHi: ref=seqLo; st=2
                else: rej.append("structure failed HH"); st=0
            elif dirL==1 and pl is not None and (b-N)>swBar:
                if pl>swLo: ref=seqHi; st=2
                else: rej.append("structure failed LL"); st=0
        if st==2:
            if dirL==-1 and cl<ref: sigS=True
            elif dirL==1 and cl>ref: sigL=True
        if sigS or sigL:
            sigs.append((b,'SHORT' if sigS else 'LONG')); cool=b+COOL; st=0
        if st==0 and not(sigS or sigL) and b>=cool and d!=0:
            rng=hi-lo
            if d==-1 and hi>U and cl<=U:
                rq=0 if rng<=0 else (hi-cl)/rng
                if strength<MINCNF: rej.append("weak level")
                elif rq<REJMIN: rej.append("weak rejection")
                else: st=1;dirL=-1;anchor=U;swHi=hi;swLo=lo;swBar=b;seqLo=lo;seqHi=hi
            elif d==1 and lo<D and cl>=D:
                rq=0 if rng<=0 else (cl-lo)/rng
                if strength<MINCNF: rej.append("weak level")
                elif rq<REJMIN: rej.append("weak rejection")
                else: st=1;dirL=1;anchor=D;swHi=hi;swLo=lo;swBar=b;seqLo=lo;seqHi=hi
    return sigs,rej

if __name__=="__main__":
    BEAR=-1;BULL=1
    # 1) full SHORT: sweep -> down -> LH pivot -> break intervening low
    seq=[(75.5,75.3,75.4,BEAR,1),(76.3,75.4,75.7,BEAR,1),(75.7,75.2,75.3,BEAR,1),
         (75.9,75.3,75.8,BEAR,1),(75.7,75.4,75.5,BEAR,1),(75.4,74.9,75.0,BEAR,1)]
    s,r=run(seq); assert [x[1] for x in s]==['SHORT'] and r==[], (s,r)
    # 2) weak level -> logged, no signal
    s,r=run(seq,strength=20.0); assert s==[] and 'weak level' in r, (s,r)
    # 3) weak rejection (close back under level but near the high -> low wick quality) -> logged
    seq2=[x for x in seq]; seq2[1]=(76.3,75.4,75.95,BEAR,1)
    s,r=run(seq2); assert s==[] and 'weak rejection' in r, (s,r)
    # 4) no LH within window -> expired logged
    seq3=[(76.3,75.4,75.7,BEAR,1)]+[(75.6,75.5,75.55,BEAR,1)]*23
    s,r=run(seq3); assert s==[] and 'window expired' in r, (s,r)
    # 5) invalidation: close back above sweep high
    seq4=[(76.3,75.4,75.7,BEAR,1),(76.5,75.8,76.4,BEAR,1)]
    s,r=run(seq4); assert s==[] and 'invalidated above sweep' in r, (s,r)
    # 6) bias flip while live -> logged reset
    seq5=[(76.3,75.4,75.7,BEAR,1),(75.7,75.2,75.3,BULL,1)]
    s,r=run(seq5); assert s==[] and 'bias flipped' in r, (s,r)
    # 7) MIXED never arms
    s,r=run([(76.3,75.4,75.7,0,1),(75.4,74.9,75.0,0,1)]); assert s==[] and r==[], (s,r)
    # 8) LONG mirror: sweep low -> up -> HL pivot -> break intervening high
    seqL=[(75.0,74.8,74.9,BULL,1),(74.9,74.2,74.8,BULL,1),(75.3,74.9,75.2,BULL,1),
          (75.2,74.7,74.8,BULL,1),(75.1,74.9,75.0,BULL,1),(75.6,75.0,75.5,BULL,1)]
    s,r=run(seqL); assert [x[1] for x in s]==['LONG'] and r==[], (s,r)
    # 9) exec TF gate off -> nothing
    s,r=run(seq,execOK=False); assert s==[] and r==[], (s,r)
    # 10) unconfirmed bars -> nothing
    s,r=run([(76.3,75.4,75.7,BEAR,0),(75.4,74.9,75.0,BEAR,0)]); assert s==[] and r==[]
    # 11) deterministic
    assert run(seq)==run(seq)
    print("M4 v2 ENTRY VALIDATED: sweep->LH->LL short, sweep->HL->HH long, strength gate,")
    print("rejection-quality gate, expiry/invalidation/bias-flip all LOGGED, MIXED=no-trade,")
    print("exec-TF guard, no-repaint gate, deterministic — all 11 scenarios PASS")
