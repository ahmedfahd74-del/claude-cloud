#!/usr/bin/env python3
"""CROSS-TICKER HONESTY TEST — the right thing.

Two questions, measured per ticker against a shuffle-surrogate null (never opinion):
  A) CLAUDE-LINE (equilibrium) RESPECT — the line the user actually trades.
     When price APPROACHES the daily auction midpoint from one side and touches it,
     does it get respected (reject/hold the approach side) more than on shuffled data?
  B) MEMORY replication — does "a level that held before holds again" survive OFF BTC
     (the finding was fit on BTC; here it faces ETH/SOL/forex out-of-sample)?

No lookahead: level value frozen at the test bar; respect measured only on later bars.
"""
import statistics
from equilibrium_lab import load_csv, surrogate, build_line
from sr_lab import test2_history, levels_from

def line_respect(lvl, o,h,l,c, M=10, tol=0.004, approach=0.010, sep=3):
    """price approaches the (moving) level from >approach away, touches it; does it
    reject/hold the approach side over the next M bars? level frozen at the test bar."""
    n=len(c); tests=[]; last=-999
    for t in range(1,n):
        L=lvl[t]
        if L!=L: continue
        band=L*tol; prev=c[t-1]
        if abs(prev-L) < L*approach: continue            # wasn't away enough → not a real approach
        above = prev > L                                  # from above → support test (hold above)
        if not (l[t]-band <= L <= h[t]+band) or t-last<sep: continue
        last=t; holds=0; tot=0; rej=False
        for t2 in range(t+1, min(t+1+M, n)):
            tot+=1
            ok=(c[t2]>=L*(1-tol)) if above else (c[t2]<=L*(1+tol))
            if ok: holds+=1
            if ok and abs(c[t2]-L)>band: rej=True
        if tot: tests.append((rej, holds/tot>=0.7))
    rt=100*sum(a for a,_ in tests)/len(tests) if tests else float('nan')
    rh=100*sum(b for _,b in tests)/len(tests) if tests else float('nan')
    return rt, rh, len(tests)

def claude_respect(o,h,l,c, L=5, **k):
    eq,_=build_line('D',L,o,h,l,c)
    return line_respect(eq,o,h,l,c,**k)

def mem_lift(o,h,l,c, L=5, M=10):
    lv=levels_from(o,h,l,c,L)
    w,wo,_,_=test2_history(lv,o,h,l,c,M)
    return (w-wo) if (w==w and wo==wo) else float('nan')

TICKERS=[('BTC','BTC_daily_clean.csv','crypto'),
         ('SOL','SOL_daily.csv','crypto'),
         ('EURUSD','EURUSD_daily.csv','forex')]
NSH=25
print("="*78)
print("CROSS-TICKER HONESTY TEST  ·  Claude-Line respect + memory, vs shuffle null")
print("="*78)
print(f"\n{'ticker':>8} {'class':>7} | {'CLAUDE-LINE respect (HOLD)':^34} | {'MEMORY lift':^22}")
print(f"{'':>8} {'':>7} | {'real':>7} {'shuffled':>9} {'excess':>7} {'sig':>4} | {'real':>6} {'null':>7} {'sig':>4}")
print("-"*78)
for name,path,cls in TICKERS:
    o,h,l,c=load_csv(path)
    _,rh,nt=claude_respect(o,h,l,c)
    sh=[]; ml=[]
    for i in range(NSH):
        so,sH,sl,sc=surrogate(o,h,l,c,seed=100+i)
        _,srh,_=claude_respect(so,sH,sl,sc); sh.append(srh)
        ml.append(mem_lift(so,sH,sl,sc))
    shm=statistics.mean([x for x in sh if x==x]); shsd=statistics.pstdev([x for x in sh if x==x]) or 1e-9
    cl_pct=100*sum(1 for x in sh if x==x and x<rh)/len([x for x in sh if x==x])
    cl_sig="YES" if cl_pct>=95 else "no"
    real_ml=mem_lift(o,h,l,c)
    mlm=statistics.mean([x for x in ml if x==x]);
    ml_pct=100*sum(1 for x in ml if x==x and x<real_ml)/len([x for x in ml if x==x])
    ml_sig="YES" if ml_pct>=95 else "no"
    print(f"{name:>8} {cls:>7} | {rh:6.0f}% {shm:8.0f}% {rh-shm:+6.0f} {cl_sig:>4} | {real_ml:+5.0f} {mlm:+6.0f} {ml_sig:>4}")

print("-"*78)
print("CLAUDE-LINE excess>0 & sig = the equilibrium line beats chance on that ticker.")
print("MEMORY sig = the proven-holds edge replicates there. 'no' = doesn't beat the null.")
print("="*78)
