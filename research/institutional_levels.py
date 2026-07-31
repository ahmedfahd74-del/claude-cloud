#!/usr/bin/env python3
"""INSTITUTIONAL LEVELS test — do Volume-Profile (POC / Value Area) levels — the
documented institutional standard — trade better than plain price pivots?

Same pre-registered expectancy sim (touch → stop 0.5ATR / target 2R, net of cost,
proven-vs-untested, trend-gate, random-entry + shuffle-surrogate nulls). Only the
LEVEL SOURCE changes: pivots vs volume-profile. Honest, no fit-to-pass.
"""
import csv, statistics
from random import Random
from collections import defaultdict
from equilibrium_lab import pivots, surrogate
from expectancy_lab import atr_series, struct_trend

def load_vol(path):
    o=[];h=[];l=[];c=[];v=[]
    for r in csv.DictReader(open(path)):
        try:
            o.append(float(r['open']));h.append(float(r['high']));l.append(float(r['low']))
            c.append(float(r['close']));v.append(float(r.get('volume',0) or 0))
        except (ValueError,KeyError): continue
    return o,h,l,c,v

def gen_pivots(o,h,l,c,v,L=5):
    hi,lo=pivots(h,l,L)
    return sorted([(cb,p) for cb,p,_ in hi]+[(cb,p) for cb,p,_ in lo])

def gen_vprofile(o,h,l,c,v, W=60, step=5, bins=50, va=0.70, dedup=0.004):
    n=len(c); raw=[]
    for t in range(W,n,step):
        lo=min(l[t-W:t]); hi=max(h[t-W:t])
        if hi<=lo: continue
        w=(hi-lo)/bins; hist=[0.0]*bins
        for d in range(t-W,t):
            b0=max(0,min(bins-1,int((l[d]-lo)/w))); b1=max(0,min(bins-1,int((h[d]-lo)/w)))
            share=v[d]/(b1-b0+1) if v[d]>0 else 0
            for b in range(b0,b1+1): hist[b]+=share
        tot=sum(hist)
        if tot<=0: continue
        poc=max(range(bins),key=lambda b:hist[b]); lob=hib=poc; acc=hist[poc]
        while acc<va*tot and (lob>0 or hib<bins-1):
            up=hist[hib+1] if hib<bins-1 else -1; dn=hist[lob-1] if lob>0 else -1
            if up>=dn and hib<bins-1: hib+=1; acc+=hist[hib]
            elif lob>0: lob-=1; acc+=hist[lob]
            else: break
        for p in (lo+(poc+0.5)*w, lo+(hib+1)*w, lo+lob*w): raw.append((t,p))
    # dedup near-equal prices (keep earliest)
    raw.sort(); out=[]
    for cb,p in raw:
        if all(abs(p-q)/q>dedup for _,q in out[-40:]): out.append((cb,p))
    return sorted(out)

def sim(levels,o,h,l,c, stopATR=0.5,targetR=2.0,cool=5,maxHold=60,costPct=0.0005,gate=False,L=5):
    atr=atr_series(h,l,c,14); trend=struct_trend(h,l,c,L) if gate else None
    n=len(c); trades=[]; prior=defaultdict(int)
    for cb,p in sorted(levels):
        last=-10**9; t=cb+1; key=round(p,6)
        while t<n:
            sup=c[t-1]>p and l[t]<=p; res=c[t-1]<p and h[t]>=p
            if (sup or res) and t-last>=cool and atr[t]==atr[t] and atr[t]>0:
                last=t; dirn=1 if sup else -1; risk=atr[t]*stopATR; e=p; stp=e-dirn*risk; tg=e+dirn*risk*targetR
                out=None
                for u in range(t+1,min(t+1+maxHold,n)):
                    if dirn==1:
                        if l[u]<=stp: out=-1.0;break
                        if h[u]>=tg: out=targetR;break
                    else:
                        if h[u]>=stp: out=-1.0;break
                        if l[u]<=tg: out=targetR;break
                if out is None: u=min(t+maxHold,n-1); out=dirn*(c[u]-e)/risk
                if (not gate) or trend[t]==dirn: trades.append((out-2*(costPct*e)/risk, prior[key]>=1, dirn))
                if out>0: prior[key]+=1
            t+=1
    return trades

def meanR(tr): return statistics.mean([x[0] for x in tr]) if tr else float('nan')
def split(tr):
    pr=[x for x in tr if x[1]]; return meanR([x for x in tr]),meanR(pr),len(tr)

def rnd_null(o,h,l,c,ntr,mix,targetR,seed,stopATR=0.5,maxHold=60,cost=0.0005):
    rnd=Random(seed); atr=atr_series(h,l,c,14); n=len(c)
    bars=[t for t in range(15,n-maxHold-1) if atr[t]==atr[t] and atr[t]>0]
    if not bars or not ntr: return float('nan')
    out=[]
    for _ in range(ntr):
        t=rnd.choice(bars); d=rnd.choice(mix); risk=atr[t]*stopATR; e=c[t]; stp=e-d*risk; tg=e+d*risk*targetR; o2=None
        for u in range(t+1,min(t+1+maxHold,n)):
            if d==1:
                if l[u]<=stp:o2=-1.0;break
                if h[u]>=tg:o2=targetR;break
            else:
                if h[u]>=stp:o2=-1.0;break
                if l[u]<=tg:o2=targetR;break
        if o2 is None: u=min(t+maxHold,n-1); o2=d*(c[u]-e)/risk
        out.append(o2-2*(cost*e)/risk)
    return statistics.mean(out)

if __name__=="__main__":
    for name,path in [('BTC','btc_vol.csv'),('ETH','eth_vol.csv'),('SOL','sol_vol.csv')]:
        o,h,l,c,v=load_vol(path)
        print(f"\n{'='*70}\n{name}  ·  {len(c)} daily bars w/ volume\n{'='*70}")
        for src,gen in [('PIVOT',gen_pivots),('VPROFILE (POC/VA)',gen_vprofile)]:
            lv=gen(o,h,l,c,v)
            trN=sim(lv,o,h,l,c,gate=False); trG=sim(lv,o,h,l,c,gate=True)
            aN,pN,nN=split(trN); aG,pG,nG=split(trG)
            mix=[x[2] for x in trN] or [1,-1]
            nulls=[rnd_null(o,h,l,c,nN,mix,2.0,1000+i) for i in range(40)]; nulls=[x for x in nulls if x==x]
            pct=100*sum(1 for x in nulls if x<aN)/len(nulls) if nulls else float('nan')
            so,sh,sl,sc=surrogate(o,h,l,c,seed=7); sv=v[:]; Random(7).shuffle(sv)
            sm=meanR(sim(gen(so,sh,sl,sc,sv),so,sh,sl,sc,gate=False))
            print(f"  {src:18} levels {len(lv):4d} | natural ALL {aN:+.3f}R (proven {pN:+.3f}) | trend+proven {pG:+.3f}R | vs rand {pct:.0f}% | surrogate {sm:+.3f}R")
    print("\nPASS = real mean R > 0 AND not below surrogate. VPROFILE>PIVOT = institutional levels help.")
