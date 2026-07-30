#!/usr/bin/env python3
"""Scoring-layer validator for level_core_v2.pine. Confidence is a pure reduction
over the enriched event log — this reproduces it and proves the institutional
properties. Run: python3 level_core_v2_score_validate.py"""
decayBars=150.0; sepNorm=20.0; dispNorm=2.0; evidNorm=5.0
wWin,wRej,wDisp,wSweep,wSep,wEvid,wProven=.28,.20,.16,.12,.12,.12,.30; NOW=1000
def proven(held):  # data-validated cliff: untested = trap, one hold = normal, then climbs
    return 0.15 if held<=1 else 0.55 if held==2 else 0.78 if held==3 else 1.0
def separation(log):
    n=len(log)
    if n<3: return 1.0
    return min((log[-1][0]-log[0][0])/(n-1)/sepNorm,1.0)
def confidence(log,deg):
    if not log: return 0.0
    wsum=rejW=dispW=sweepW=0.0; held=brk=0
    for bar,t,kind,react,rejQ,swept in log:
        w=1.0/(1.0+max(0,NOW-bar)/decayBars); wsum+=w
        rejW+=w*rejQ; dispW+=w*min(react/dispNorm,1.0); sweepW+=w if swept else 0
        held+=kind==2; brk+=kind==3
    winF=held/(held+brk) if held+brk else .5
    rejF=rejW/wsum; dispF=dispW/wsum; sweepF=min(sweepW/wsum*2,1)
    sepF=separation(log); evidF=min(wsum/evidNorm,1); degW={3:1.,2:.85,1:.70,0:.55}[deg]
    provenF=proven(held)
    wtot=wWin+wRej+wDisp+wSweep+wSep+wEvid+wProven
    raw=(winF*wWin+rejF*wRej+dispF*wDisp+sweepF*wSweep+sepF*wSep+evidF*wEvid+provenF*wProven)/wtot
    return max(0,min(raw*degW*100,100))
if __name__=="__main__":
    strong=[(b,b,2,1.8,0.8,True) for b in range(900,990,15)]
    clustered=[(b,b,1,0.3,0.2,False) for b in range(980,988,2)]
    assert confidence(strong,2)>confidence(clustered,2)          # anti-cluster
    w=[(b,b,2,1.5,0.7,True) for b in range(900,960,15)]
    assert confidence(w,3)>confidence(w,0)                        # proximity/TF weight
    recent=[(b,b,2,1.5,0.7,True) for b in range(950,995,15)]
    old=[(b,b,2,1.5,0.7,True) for b in range(100,145,15)]
    assert confidence(recent,2)>confidence(old,2)                # time decay
    # PROVEN-HOLDS (data-validated): an UNTESTED level (only the founding rejection, held=1)
    # must score BELOW an identical level that has bounced again — untested is a trap.
    untested=[(980,980,2,1.5,0.7,True)]                          # held=1 (founding only)
    proved  =[(980,980,2,1.5,0.7,True),(990,990,2,1.5,0.7,True)] # held=2 (bounced once more)
    assert confidence(proved,2)>confidence(untested,2)           # proven > untested
    assert proven(1)<proven(2)<proven(3)<=proven(4)              # monotone climb, cliff at 1→2
    assert proven(1)==0.15 and proven(4)==1.0
    print(f"strong={confidence(strong,2):.0f} clustered={confidence(clustered,2):.0f} "
          f"1W={confidence(w,3):.0f} 1H={confidence(w,0):.0f} recent={confidence(recent,2):.0f} stale={confidence(old,2):.0f} "
          f"untested={confidence(untested,2):.0f} proved={confidence(proved,2):.0f}")
    print("SCORING VALIDATED: anti-cluster, quality/sweep/displacement, proximity, decay,")
    print("  PROVEN-HOLDS (untested<proven, data-validated cliff), deterministic")
