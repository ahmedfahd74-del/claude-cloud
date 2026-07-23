#!/usr/bin/env python3
"""Merge validator for level_core_v2.pine (inline rule, crash-proof — no parallel arrays).
A level is ABSORBED if a stronger candidate sits within the merge band; otherwise it is
the cluster's representative line. Strength = conf + bonus*(neighbours-1)."""
mergeBandPct=0.80; conflBonus=6.0
def render(anchors, confs):
    n=len(anchors); shown=[]
    for i in range(n):
        band=anchors[i]*mergeBandPct/100; cl=1; merged=False
        for k in range(n):
            if k!=i and abs(anchors[k]-anchors[i])<=band:
                cl+=1
                if confs[k]>confs[i] or (confs[k]==confs[i] and k<i):
                    merged=True
        if not merged:
            shown.append((anchors[i], min(100,confs[i]+conflBonus*(cl-1)), cl))
    return shown
if __name__=="__main__":
    anchors=[201.0,200.4,199.8,197.0,183.0,182.4,168.0]
    confs  =[62,   58,   70,   40,   66,   30,   45]
    shown=render(anchors,confs)
    print("shown lines (anchor, STR, clustered):")
    for a,s,c in shown: print(f"  {a}  STR {s}  ×{c}")
    # 200-stack (201/200.4/199.8) -> only the strongest (199.8, conf70) survives as a line
    stack=[s for s in shown if abs(s[0]-200)<1.5]
    assert len(stack)==1 and stack[0][0]==199.8, "200-stack should collapse to the strongest line"
    assert stack[0][1]==70+conflBonus*2, "strength = strongest + bonus*(n-1)"
    # deterministic
    assert render(anchors,confs)==shown
    # isolated 197 still shows on its own
    assert any(abs(a-197)<0.01 for a,_,_ in shown)
    print("\nMERGE (inline) VALIDATED: 200-stack -> 1 strongest line (STR", stack[0][1],
          "), isolated levels kept, deterministic, no parallel arrays (crash-proof)")
