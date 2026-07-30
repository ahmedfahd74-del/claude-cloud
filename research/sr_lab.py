#!/usr/bin/env python3
"""S/R LAB — does our support/resistance actually have an edge? Same rigor as the
equilibrium lab: real data, no lookahead, surrogate + permutation nulls.

Two decisive questions:
  TEST 1  Do PIVOT-derived levels get respected more than RANDOM price levels
          (matched count, drawn in the same local trading range)?  -> is a "level"
          worth anything over an arbitrary horizontal line?
  TEST 2  Does HISTORY predict the next touch — is a level that has HELD before
          respected more on its next touch than a level with no prior holds?  ->
          is the engine's memory/scoring real, or noise?

Respect (both, forward-only, no lookahead):
  TOUCH = within M bars price reaches the level (±tol) AND then closes back on the
          level's hold-side by a margin (a rejection).
  HOLD  = >= 70% of the next M closes stay on the level's hold-side.
  hold-side: support (pivot low) = above · resistance (pivot high) = below.

Levels are CONFIRMED pivots (known L bars late — non-repaint). Nulls: (a) random
levels in the same range; (b) shuffled-return surrogate. Permutation p-values.

  python3 sr_lab.py --csv BTC_daily_clean.csv --perm 40
"""
import argparse, random, statistics
from equilibrium_lab import load_csv, synth_daily, surrogate, pivots

def respect(price, kind, t, o,h,l,c, M=10, tol=0.004):
    n=len(c); band=price*tol; up=(kind=='L')
    touched=False; rej=False; holds=0; total=0
    for t2 in range(t+1, min(t+1+M, n)):
        total+=1
        if l[t2]-band <= price <= h[t2]+band: touched=True
        side = (c[t2] >= price*(1-tol)) if up else (c[t2] <= price*(1+tol))
        if side: holds+=1
        if touched and side and abs(c[t2]-price) > band: rej=True
    if total==0: return None, None
    return (touched and rej), (holds/total >= 0.7)

def levels_from(o,h,l,c, L):
    hi,lo=pivots(h,l,L)
    return [(cb,p,'H') for cb,p,_ in hi] + [(cb,p,'L') for cb,p,_ in lo]

def agg(levels, o,h,l,c, M):
    t=[]; hd=[]
    for cb,p,k in levels:
        rt,rh=respect(p,k,cb,o,h,l,c,M)
        if rt is not None: t.append(rt); hd.append(rh)
    return (100*sum(t)/len(t) if t else float('nan'),
            100*sum(hd)/len(hd) if hd else float('nan'))

def random_levels(levels, o,h,l,c, rnd, W=100):
    """same (confirm_bar, kind) but price drawn uniformly from the local trading
    range — a fair random horizontal line that could plausibly be touched."""
    out=[]
    for cb,p,k in levels:
        a=max(0,cb-W)
        lo=min(l[a:cb+1]); hi=max(h[a:cb+1])
        out.append((cb, rnd.uniform(lo,hi), k))
    return out

def test2_history(levels, o,h,l,c, M=10, tol=0.004, sep=3):
    """per level, scan its touches in time; does a PRIOR hold predict THIS hold?
    causal: prior count uses only earlier touches. Returns (rate_with_prior,
    rate_without_prior, n_with, n_without)."""
    n=len(c)
    with_p=[]; without_p=[]
    for cb,p,k in levels:
        band=p*tol; up=(k=='L'); prior_holds=0; last_touch=-999
        t=cb+1
        while t < n:
            if l[t]-band <= p <= h[t]+band and t-last_touch>=sep:
                last_touch=t
                holds=0; tot=0
                for t2 in range(t+1, min(t+1+M,n)):
                    tot+=1
                    side=(c[t2]>=p*(1-tol)) if up else (c[t2]<=p*(1+tol))
                    if side: holds+=1
                this_hold = (holds/tot>=0.7) if tot else None
                if this_hold is not None:
                    (with_p if prior_holds>=1 else without_p).append(this_hold)
                    if this_hold: prior_holds+=1
            t+=1
    r=lambda a: (100*sum(a)/len(a)) if a else float('nan')
    return r(with_p), r(without_p), len(with_p), len(without_p)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--csv'); ap.add_argument('--L',type=int,default=5)
    ap.add_argument('--M',type=int,default=10); ap.add_argument('--perm',type=int,default=0)
    ap.add_argument('--seed',type=int,default=7); ap.add_argument('--n',type=int,default=1500)
    a=ap.parse_args()
    if a.csv: o,h,l,c=load_csv(a.csv); src=f"REAL CSV {a.csv}"
    else: o,h,l,c=synth_daily(a.n,a.seed); src=f"SYNTHETIC NULL ({a.n} bars)"

    lv=levels_from(o,h,l,c,a.L)
    rt,rh=agg(lv,o,h,l,c,a.M)
    print("="*72); print("S/R LAB  ·  source:",src,f" · pivot L={a.L} · {len(lv)} levels"); print("="*72)
    print(f"\n[TEST 1] PIVOT LEVELS vs RANDOM LEVELS (respected {a.M} bars fwd)")
    print(f"  pivot levels:  respTOUCH {rt:.0f}%   respHOLD {rh:.0f}%")

    rnd=random.Random(a.seed)
    R=max(a.perm,30)
    nt=[]; nh=[]
    for i in range(R):
        rl=random_levels(lv,o,h,l,c,random.Random(1000+i))
        xt,xh=agg(rl,o,h,l,c,a.M); nt.append(xt); nh.append(xh)
    def rep(nm, real, null):
        m=statistics.mean(null); sd=statistics.pstdev(null) or 1e-9
        pct=100*sum(1 for x in null if x<real)/len(null)
        v="*** SIGNIFICANT (p<0.05)" if pct>=95 else "within noise" if pct>=50 else "BELOW null"
        print(f"  {nm:12} real {real:5.1f}%   random {m:5.1f}% ± {sd:.1f}   >null {pct:3.0f}%   {v}")
    print(f"  random-level null ({R} draws):")
    rep("TOUCH", rt, nt); rep("HOLD", rh, nh)

    # surrogate: does level-respect survive destroying time-order?
    so,sh,sl,sc=surrogate(o,h,l,c,seed=a.seed+101)
    slv=levels_from(so,sh,sl,sc,a.L); st,shd=agg(slv,so,sh,sl,sc,a.M)
    print(f"\n[TEST 1b] SHUFFLED-RETURN SURROGATE (time-order destroyed)")
    print(f"  surrogate pivot levels: respTOUCH {st:.0f}%  respHOLD {shd:.0f}%")
    print(f"  EXCESS (real - surrogate): {rt-st:+.0f}pt touch / {rh-shd:+.0f}pt hold")

    w,wo,nw,nwo=test2_history(lv,o,h,l,c,a.M)
    print(f"\n[TEST 2] DOES HISTORY PREDICT? (level's next touch: has held before vs not)")
    print(f"  touch WITH prior hold:    respHOLD {w:.0f}%   (n={nw})")
    print(f"  touch WITHOUT prior hold: respHOLD {wo:.0f}%   (n={nwo})")
    print(f"  lift from memory: {w-wo:+.0f}pt")

    if a.perm:
        # permutation for TEST 2 lift: shuffle labels? simplest honest null = surrogate data
        lifts=[]
        for i in range(a.perm):
            po,ph,pl,pc=surrogate(o,h,l,c,seed=2000+i)
            plv=levels_from(po,ph,pl,pc,a.L)
            ww, wwo,_,_=test2_history(plv,po,ph,pl,pc,a.M)
            if ww==ww and wwo==wwo: lifts.append(ww-wwo)
        if lifts:
            m=statistics.mean(lifts); sd=statistics.pstdev(lifts) or 1e-9
            pct=100*sum(1 for x in lifts if x<(w-wo))/len(lifts)
            print(f"\n[TEST 2 permutation] memory-lift real {w-wo:+.0f}pt  vs surrogate {m:+.0f}±{sd:.0f}  >null {pct:.0f}%  "
                  + ("*** SIGNIFICANT" if pct>=95 else "within noise" if pct>=50 else "BELOW null"))

    print("\n"+"-"*72)
    print("READING: TEST 1 = is a level better than a random line · TEST 2 = does the")
    print("engine's MEMORY/scoring add signal. Real must beat random AND surrogate.")
    print("-"*72)

if __name__=="__main__": main()
