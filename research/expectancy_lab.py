#!/usr/bin/env python3
"""EXPECTANCY LAB — the real 'can I trade this?' test for the S/R engine's levels.

Pre-registered, no cherry-picking. Population = EVERY confirmed daily pivot level
(support = pivot low, resistance = pivot high, size L). A trade fires each time price
TOUCHES a level (approach from the correct side), with a cooldown. Fixed-R management:
stop = 0.5·ATR beyond the level (=1R), target = 2R. Outcome = R-multiple NET of cost.

Judged three ways:
  * stratified by MEMORY (has the level held before, causally) — proven vs untested
  * NATURAL side (long@support/short@resistance) AND TREND-GATED (only with structure)
  * vs a RANDOM-ENTRY null (same count, same side mix, same geometry) — permutation
    percentile — and a shuffle SURROGATE (returns permuted → structure destroyed)

No lookahead: entry on the touch bar, outcome on later bars only. Barrier method
(stop-first if both in one bar). Metric = mean R per trade.
"""
import argparse, statistics
from random import Random
from equilibrium_lab import load_csv, surrogate, pivots

def atr_series(h,l,c,n):
    tr=[float('nan')]*len(c)
    for i in range(1,len(c)):
        tr[i]=max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    a=[float('nan')]*len(c); s=0.0; k=0
    for i in range(1,len(c)):
        s+=tr[i]; k+=1
        if k>n: s-=tr[i-n]; k=n
        if k==n: a[i]=s/n
    return a

def struct_trend(h,l,c,L):
    """causal HH/HL structure trend per bar (1 up / -1 down / 0), forward-filled."""
    hi,lo=pivots(h,l,L)
    ev=sorted([(cb,p,'H') for cb,p,_ in hi]+[(cb,p,'L') for cb,p,_ in lo])
    tr=[0]*len(c); t=0; ph=None; pl=None; hc=0; lc=0; i=0
    for bar in range(len(c)):
        while i<len(ev) and ev[i][0]<=bar:
            _,p,k=ev[i]; i+=1
            if k=='H': hc=1 if (ph is None or p>ph) else -1; ph=p
            else:      lc=1 if (pl is None or p>pl) else -1; pl=p
            t = 1 if (hc==1 and lc==1) else -1 if (hc==-1 and lc==-1) else t
        tr[bar]=t
    return tr

def simulate(o,h,l,c, L=5, stopATR=0.5, targetR=2.0, cool=5, maxHold=60,
             costPct=0.0005, gate=False):
    atr=atr_series(h,l,c,14); trend=struct_trend(h,l,c,L) if gate else None
    hi,lo=pivots(h,l,c) if False else pivots(h,l,L)
    levels=sorted([(cb,p,'R') for cb,p,_ in hi]+[(cb,p,'S') for cb,p,_ in lo])
    n=len(c); trades=[]                                  # (netR, proven, side, dirn)
    for cb,p,side in levels:
        prior=0; last=-10**9; t=cb+1
        while t<n:
            appr = (side=='S' and c[t-1]>p and l[t]<=p) or (side=='R' and c[t-1]<p and h[t]>=p)
            if appr and t-last>=cool and atr[t]==atr[t] and atr[t]>0:
                last=t; dirn=1 if side=='S' else -1
                risk=atr[t]*stopATR; entry=p
                stop=entry-dirn*risk; tgt=entry+dirn*risk*targetR
                out=None
                for u in range(t+1, min(t+1+maxHold,n)):
                    if dirn==1:
                        if l[u]<=stop: out=-1.0; break
                        if h[u]>=tgt:  out=targetR; break
                    else:
                        if h[u]>=stop: out=-1.0; break
                        if l[u]<=tgt:  out=targetR; break
                if out is None:
                    u=min(t+maxHold,n-1); out=dirn*(c[u]-entry)/risk
                netR=out-2*(costPct*entry)/risk
                take = (not gate) or (trend[t]==dirn)     # trend-gate: only with structure
                if take:
                    trades.append((netR, prior>=1, side, dirn))
                if out>0: prior+=1                        # memory: a bounce (win) = a hold
            t+=1
    return trades

def stat(trades):
    if not trades: return (float('nan'),0,float('nan'))
    rs=[x[0] for x in trades]
    return (statistics.mean(rs), len(rs), 100*sum(1 for r in rs if r>0)/len(rs))

def random_null(o,h,l,c, n_tr, side_mix, stopATR, targetR, maxHold, costPct, seed):
    rnd=Random(seed); atr=atr_series(h,l,c,14); n=len(c)
    bars=[t for t in range(15,n-maxHold-1) if atr[t]==atr[t] and atr[t]>0]
    if not bars or n_tr==0: return float('nan')
    outs=[]
    for _ in range(n_tr):
        t=rnd.choice(bars); dirn=rnd.choice(side_mix)
        risk=atr[t]*stopATR; entry=c[t]; stop=entry-dirn*risk; tgt=entry+dirn*risk*targetR
        out=None
        for u in range(t+1,min(t+1+maxHold,n)):
            if dirn==1:
                if l[u]<=stop: out=-1.0; break
                if h[u]>=tgt:  out=targetR; break
            else:
                if h[u]>=stop: out=-1.0; break
                if l[u]<=tgt:  out=targetR; break
        if out is None: u=min(t+maxHold,n-1); out=dirn*(c[u]-entry)/risk
        outs.append(out-2*(costPct*entry)/risk)
    return statistics.mean(outs)

def run(name, path, L, targetR, nperm=60):
    o,h,l,c=load_csv(path)
    print(f"\n{'='*76}\n{name}  ·  {len(c)} daily bars  ·  pivot L={L}  ·  stop 0.5ATR  ·  target {targetR}R  ·  net of cost\n{'='*76}")
    for gate,label in [(False,'NATURAL (long@support / short@resistance)'),(True,'TREND-GATED (only with structure)')]:
        tr=simulate(o,h,l,c,L=L,targetR=targetR,gate=gate)
        allm,alln,allw=stat(tr)
        prov=[x for x in tr if x[1]]; unpr=[x for x in tr if not x[1]]
        pm,pn,pw=stat(prov); um,un,uw=stat(unpr)
        side_mix=[x[3] for x in tr] or [1,-1]
        nulls=[random_null(o,h,l,c,alln,side_mix,0.5,targetR,60,0.0005,1000+i) for i in range(nperm)]
        nulls=[x for x in nulls if x==x]; nm=statistics.mean(nulls) if nulls else float('nan')
        pct=100*sum(1 for x in nulls if x<allm)/len(nulls) if nulls else float('nan')
        so,sh,sl,sc=surrogate(o,h,l,c,seed=7); sm,_,_=stat(simulate(so,sh,sl,sc,L=L,targetR=targetR,gate=gate))
        print(f"\n  {label}")
        print(f"    ALL       trades {alln:5d}   mean {allm:+.3f}R   win {allw:.0f}%")
        print(f"    PROVEN    trades {pn:5d}   mean {pm:+.3f}R   win {pw:.0f}%")
        print(f"    UNTESTED  trades {un:5d}   mean {um:+.3f}R   win {uw:.0f}%")
        print(f"    random null mean {nm:+.3f}R   ·  real > {pct:.0f}% of {len(nulls)} shuffles   ·  surrogate {sm:+.3f}R")
        edge = "*** beats random (p<0.05)" if pct>=95 else "within noise" if pct>=50 else "BELOW random"
        print(f"    VERDICT (ALL vs random): {edge}   |   break-even needs mean > 0")

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument('--target',type=float,default=2.0); ap.add_argument('--L',type=int,default=5)
    a=ap.parse_args()
    for name,path in [('BTC','BTC_daily_clean.csv'),('SOL','SOL_daily.csv'),('EURUSD','EURUSD_daily.csv')]:
        run(name,path,a.L,a.target)
    print("\nNET-R > 0 AND beats random = a tradeable entry. PROVEN>UNTESTED = the score sorts money.")
