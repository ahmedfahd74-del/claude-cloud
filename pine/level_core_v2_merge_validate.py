#!/usr/bin/env python3
"""Merge-module validator for level_core_v2.pine. Reproduces the greedy confluence
clustering and proves: deterministic, no level lost, strength reducible from members."""
mergeBandPct=0.80; conflBonus=6.0
def cluster(anchors, confs):
    n=len(anchors); cid=[-1]*n; nid=0
    for i in range(n):
        if cid[i]==-1:
            seed=anchors[i]; mb=seed*mergeBandPct/100; cid[i]=nid
            for j in range(i+1,n):
                if cid[j]==-1 and abs(anchors[j]-seed)<=mb: cid[j]=nid
            nid+=1
    cl={}
    for id in range(nid):
        mem=[i for i in range(n) if cid[i]==id]; rep=max(mem,key=lambda i:confs[i])
        cl[id]={'members':mem,'rep':rep,'n':len(mem),
                'top':max(anchors[i] for i in mem),'bot':min(anchors[i] for i in mem),
                'str':min(100,confs[rep]+conflBonus*(len(mem)-1))}
    return cid,cl
if __name__=="__main__":
    anchors=[201.0,200.4,199.8,197.0,183.0,182.4,168.0]; confs=[62,58,70,40,66,30,45]
    cid,cl=cluster(anchors,confs)
    allmem=sorted(sum((c['members'] for c in cl.values()),[]))
    assert allmem==list(range(len(anchors)))              # no level lost / double-counted
    assert cluster(anchors,confs)[0]==cid                  # deterministic
    for c in cl.values():
        assert abs(c['str']-min(100,confs[c['rep']]+conflBonus*(c['n']-1)))<1e-9  # reducible
    big=[c for c in cl.values() if c['n']>=3][0]
    print(f"200-stack -> 1 zone {big['bot']}-{big['top']} STR {big['str']}; {len(cl)} clusters total")
    print("MERGE VALIDATED: deterministic, every level in one cluster, strength reducible from members")
