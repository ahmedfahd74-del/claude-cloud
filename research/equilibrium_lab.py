#!/usr/bin/env python3
"""EQUILIBRIUM LAB — research instrument for the "dynamic equilibrium" experiment.

Question under test (user's hypothesis):
  Is equilibrium DYNAMIC? When price breaks-and-retests, does the equilibrium line
  migrate to acknowledge the new auction position EARLIER than fixed confirmation —
  and do INDEPENDENT lines (different pivot lengths / TFs) migrate TOGETHER, which
  would make it a real property of the auction rather than a visual coincidence?

The equilibrium FAMILY:
  Weekly pivot lengths 2..14  +  Daily pivot lengths 2..14  = 26 independent lines.
  Each line's equilibrium = ( nearest CONFIRMED swing high >= price
                            + nearest CONFIRMED swing low  <= price ) / 2
  "Confirmed" = the pivot has completed its right-side L bars (non-repaint: a pivot
  at TF-bar i is only known at i+L). Nothing is smoothed.

What it records (exactly the user's schema) for every MIGRATION of every line:
  tf · pivotLen · t · prevPos · newPos · delta · direction · precedingEvent ·
  respected_TOUCH (price returned and rejected) · respected_HOLD (price stayed the
  new side). BOTH respect definitions are logged — successes AND failures.

Then across the family:
  COHERENCE  — how many independent lines migrate the SAME way within a window
  LEAD-LAG   — which pivot lengths move FIRST (leaders) vs LAST (laggers)
  RESPECT    — per (tf,L) hit-rate of migration -> price respected the new position

DATA:
  --csv PATH   run on real OHLC (date,open,high,low,close[,volume]); the day you
               export from TradingView, the SAME code answers the real question.
  (default)    a SEEDED synthetic NULL MODEL — realistic structure + noise, NO
               market intent. It is the control: anything real data does ABOVE this
               baseline is the actual discovery. Synthetic proves the METHOD and
               shows what pure estimator-mechanics look like — it proves nothing
               about real markets by itself.

  This is a LAB (offline, full history, honest forward-respect). It is deliberately
  NOT a live indicator — forward-respect needs future bars, which a non-repaint
  chart script must never peek at.
"""
import argparse, csv, math, random
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────────────────
def synth_daily(n=1500, seed=7):
    """Regime-switching geometric walk → realistic swings, breaks, retests, ranges.
    NULL MODEL: structure + noise, no 'intent'. Returns lists o,h,l,c."""
    rnd = random.Random(seed)
    px = 100.0
    drift = 0.0
    vol = 0.010
    o=[]; h=[]; l=[]; c=[]
    regime_left = 0
    for _ in range(n):
        if regime_left <= 0:                      # switch regime
            r = rnd.random()
            drift = (0.0025 if r < 0.33 else -0.0025 if r < 0.66 else 0.0)  # up/down/range
            vol = rnd.choice([0.008, 0.012, 0.018])
            regime_left = rnd.randint(20, 70)
        regime_left -= 1
        op = px
        ret = drift + rnd.gauss(0, vol)
        px = max(1e-6, px * (1.0 + ret))
        cl = px
        wick = abs(rnd.gauss(0, vol)) * op
        hi = max(op, cl) + wick
        lo = min(op, cl) - wick
        o.append(op); h.append(hi); l.append(lo); c.append(cl)
    return o,h,l,c

def load_csv(path):
    o=[]; h=[]; l=[]; c=[]
    with open(path) as f:
        for row in csv.DictReader(f):
            k = {kk.lower(): vv for kk, vv in row.items()}
            try:
                o.append(float(k['open'])); h.append(float(k['high']))
                l.append(float(k['low']));  c.append(float(k['close']))
            except (KeyError, ValueError):
                continue
    return o,h,l,c

def resample(o,h,l,c, k=7):
    """daily → weekly (k daily bars per bucket). Returns weekly o,h,l,c and the
    mapping day_index -> week_index (which week each day belongs to)."""
    wo=[]; wh=[]; wl=[]; wc=[]; day2wk=[]
    for i in range(0, len(c), k):
        j = min(i+k, len(c))
        wo.append(o[i]); wh.append(max(h[i:j])); wl.append(min(l[i:j])); wc.append(c[j-1])
        for _ in range(i, j):
            day2wk.append(len(wo)-1)
    return wo,wh,wl,wc, day2wk

# ─────────────────────────────────────────────────────────────────────────────
# PIVOTS (fractal, non-repaint: pivot at bar i is CONFIRMED at bar i+L)
# ─────────────────────────────────────────────────────────────────────────────
def pivots(h, l, L):
    """returns two lists of (confirm_bar, price, kind) sorted by confirm_bar.
    kind: 'H' swing high, 'L' swing low. confirm_bar = i + L (real-time known)."""
    highs=[]; lows=[]
    n=len(h)
    for i in range(L, n-L):
        seg_h = h[i-L:i+L+1]; seg_l = l[i-L:i+L+1]
        if h[i] == max(seg_h) and h[i] > max(h[i-L:i]+h[i+1:i+L+1]):
            highs.append((i+L, h[i], 'H'))
        if l[i] == min(seg_l) and l[i] < min(l[i-L:i]+l[i+1:i+L+1]):
            lows.append((i+L, l[i], 'L'))
    return highs, lows

# ─────────────────────────────────────────────────────────────────────────────
# ONE EQUILIBRIUM LINE over its TF timeline (list of eq per TF-bar) + migrations
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Migration:
    tf: str; L: int; t_tf: int          # migration time in the line's own TF bars
    prev: float; new: float; delta: float; direction: int
    cause: str                          # 'new_HL','new_LH','new_LL','new_HH','price_cross'
    respected_touch: object = None      # resolved forward (True/False/None)
    respected_hold: object = None

def build_line(tf, L, o,h,l,c):
    """returns (eq_by_bar list, migrations list) on this TF's own bars."""
    highs, lows = pivots(h, l, L)
    n=len(c)
    hi_conf=[]; lo_conf=[]                 # (price) of confirmed pivots so far
    hi_ptr=0; lo_ptr=0
    prev_lo_price=None; prev_hi_price=None
    eq_series=[float('nan')]*n
    migs=[]
    prev_eq=float('nan')
    for t in range(n):
        cause_new=None
        # admit pivots confirmed by bar t
        while hi_ptr < len(highs) and highs[hi_ptr][0] <= t:
            p=highs[hi_ptr][1]
            cls = 'new_HH' if (prev_hi_price is None or p>prev_hi_price) else 'new_LH'
            prev_hi_price=p; hi_conf.append(p); cause_new=cls; hi_ptr+=1
        while lo_ptr < len(lows) and lows[lo_ptr][0] <= t:
            p=lows[lo_ptr][1]
            cls = 'new_LL' if (prev_lo_price is None or p<prev_lo_price) else 'new_HL'
            prev_lo_price=p; lo_conf.append(p); cause_new=cls; lo_ptr+=1
        px=c[t]
        ub=min((v for v in hi_conf if v>=px), default=None)
        lb=max((v for v in lo_conf if v<=px), default=None)
        eq = (ub+lb)/2.0 if (ub is not None and lb is not None) else float('nan')
        eq_series[t]=eq
        if not math.isnan(eq) and not math.isnan(prev_eq):
            if abs(eq-prev_eq) > 1e-9*max(1.0,abs(prev_eq)):
                cause = cause_new if cause_new else 'price_cross'
                migs.append(Migration(tf,L,t,prev_eq,eq,eq-prev_eq,
                                      1 if eq>prev_eq else -1, cause))
        prev_eq=eq
    return eq_series, migs

# ─────────────────────────────────────────────────────────────────────────────
# FORWARD RESPECT (both definitions) — measured ONLY on bars AFTER confirmation
# ─────────────────────────────────────────────────────────────────────────────
def eval_respect(migs_daily, o,h,l,c, M=10, tol=0.004):
    """migs_daily: migrations already mapped to the DAILY timeline (t = day index).
    touch = within M days price trades to newPos AND then closes back the expected
            side by tol (a rejection).  hold = >=70% of next M closes on expected side."""
    n=len(c)
    for m in migs_daily:
        t=m.t_tf                                   # here t_tf carries the day index
        lvl=m.new; band=lvl*tol
        exp_up = m.direction>0                     # up-migration → expect support (price above)
        touched=False; rej=False; holds=0; total=0
        for t2 in range(t+1, min(t+1+M, n)):
            total+=1
            if l[t2]-band <= lvl <= h[t2]+band:
                touched=True
            side_ok = (c[t2] >= lvl*(1-tol)) if exp_up else (c[t2] <= lvl*(1+tol))
            if side_ok: holds+=1
            if touched and side_ok and abs(c[t2]-lvl) > band:
                rej=True
        m.respected_touch = (touched and rej) if total>0 else None
        m.respected_hold  = (holds/total >= 0.7) if total>0 else None

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
def coherence_events(all_daily_migs, n_days, W=2, thresh=6):
    """A coherence event = a day where >= thresh lines migrated the SAME direction
    within +/-W days. Returns list of (day, direction, participants[list of migs])."""
    by_day={}
    for m in all_daily_migs:
        by_day.setdefault(m.t_tf,[]).append(m)
    events=[]
    used=set()
    for d in range(n_days):
        for dirn in (1,-1):
            parts=[]
            for dd in range(d-W, d+W+1):
                for m in by_day.get(dd,[]):
                    if m.direction==dirn:
                        parts.append(m)
            if len(parts)>=thresh:
                key=(d,dirn)
                # dedupe overlapping windows: only take local maxima not already used
                sig=frozenset((p.tf,p.L,p.t_tf) for p in parts)
                if sig not in used:
                    used.add(sig)
                    events.append((d,dirn,parts))
    # collapse events that share most participants (keep the biggest)
    events.sort(key=lambda e:-len(e[2]))
    kept=[]; claimed=set()
    for d,dirn,parts in events:
        ids=set((p.tf,p.L,p.t_tf) for p in parts)
        if len(ids & claimed) > 0.5*len(ids):
            continue
        claimed|=ids; kept.append((d,dirn,parts))
    return kept

def lead_lag(events):
    """average migration-order rank per (tf,L) within coherence events.
    low rank = leader (moves first). Returns dict (tf,L)->(avg_rank, count)."""
    acc={}
    for d,dirn,parts in events:
        ps=sorted(parts, key=lambda m:m.t_tf)
        for rank,m in enumerate(ps):
            k=(m.tf,m.L); a=acc.setdefault(k,[0,0]); a[0]+=rank; a[1]+=1
    return {k:(v[0]/v[1], v[1]) for k,v in acc.items() if v[1]>0}

# ─────────────────────────────────────────────────────────────────────────────
# REUSABLE ANALYSIS (so ORDERED and SURROGATE run through the identical pipeline)
# ─────────────────────────────────────────────────────────────────────────────
def rate(ms, attr):
    vals=[getattr(m,attr) for m in ms if getattr(m,attr) is not None]
    return (100*sum(1 for v in vals if v)/len(vals)) if vals else float('nan')

def build_all(o,h,l,c,Ls):
    """the whole 26-line family, migrations mapped onto the DAILY timeline."""
    wo,wh,wl,wc,day2wk = resample(o,h,l,c,7)
    wk_first={}
    for di,wk in enumerate(day2wk):
        wk_first.setdefault(wk,di)
    all_migs=[]; per_line={}
    for L in Ls:
        _,migs = build_line('D',L,o,h,l,c)
        per_line[('D',L)]=migs; all_migs+=migs
    for L in Ls:
        _,migs = build_line('W',L,wo,wh,wl,wc)
        mapped=[Migration('W',L,wk_first[m.t_tf],m.prev,m.new,m.delta,m.direction,m.cause)
                for m in migs if m.t_tf in wk_first]
        per_line[('W',L)]=mapped; all_migs+=mapped
    return all_migs, per_line

def analyze(o,h,l,c,Ls,M,thresh):
    n=len(c)
    all_migs, per_line = build_all(o,h,l,c,Ls)
    eval_respect(all_migs,o,h,l,c,M=M)          # mutates the shared objects in per_line too
    struct=[m for m in all_migs if m.cause.startswith('new_')]
    ev=coherence_events(struct,n,W=2,thresh=thresh)
    coh=[m for _,_,p in ev for m in p]
    gap_t=rate(coh,'respected_touch')-rate(struct,'respected_touch')
    gap_h=rate(coh,'respected_hold') -rate(struct,'respected_hold')
    return dict(n=n, all=all_migs, per_line=per_line, struct=struct, ev=ev, coh=coh,
                gap_t=gap_t, gap_h=gap_h)

def surrogate(o,h,l,c, seed=101):
    """SHUFFLE control: permute close-to-close returns AND intrabar offsets. Same
    return distribution / volatility / fat tails, but time-ordering DESTROYED — so
    any structure that survives ordering but dies here was genuinely temporal."""
    rnd=random.Random(seed); n=len(c)
    rets=[math.log(c[t]/c[t-1]) for t in range(1,n)]
    up =[(h[t]-c[t])/c[t] for t in range(n)]
    dn =[(c[t]-l[t])/c[t] for t in range(n)]
    opf=[(o[t]-c[t])/c[t] for t in range(n)]
    rnd.shuffle(rets); rnd.shuffle(up); rnd.shuffle(dn); rnd.shuffle(opf)
    cc=[c[0]]
    for r in rets: cc.append(cc[-1]*math.exp(r))
    o2=[];h2=[];l2=[];c2=[]
    for t in range(n):
        cl=cc[t]
        oo=cl*(1+opf[t]); hh=cl*(1+abs(up[t])); ll=cl*(1-abs(dn[t]))
        o2.append(oo); h2.append(max(hh,oo,cl)); l2.append(min(ll,oo,cl)); c2.append(cl)
    return o2,h2,l2,c2

def sequencing(per_line):
    """HIGHER-LOW / LOWER-HIGH SEQUENCING: per line, find RUNS of consecutive
    same-direction structural migrations (equilibrium stair-stepping). Split into
    SEQUENCED (run length >= 2) vs ISOLATED (single). The user's phenomenon is the
    sequenced up-chain (HL after HL). Returns (sequenced, isolated) migration lists."""
    seq=[]; iso=[]
    for ms in per_line.values():
        s=sorted([m for m in ms if m.cause.startswith('new_')], key=lambda m:m.t_tf)
        i=0
        while i<len(s):
            j=i
            while j+1<len(s) and s[j+1].direction==s[i].direction:
                j+=1
            run=s[i:j+1]
            (seq if len(run)>=2 else iso).extend(run)
            i=j+1
    return seq, iso

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--csv'); ap.add_argument('--n',type=int,default=1500)
    ap.add_argument('--seed',type=int,default=7); ap.add_argument('--M',type=int,default=10)
    ap.add_argument('--thresh',type=int,default=6)
    a=ap.parse_args()

    if a.csv:
        o,h,l,c=load_csv(a.csv); src=f"REAL CSV {a.csv}"
    else:
        o,h,l,c=synth_daily(a.n,a.seed); src=f"SYNTHETIC NULL MODEL (seed {a.seed}, {a.n} daily bars)"
    Ls=list(range(2,15))

    R=analyze(o,h,l,c,Ls,a.M,a.thresh)          # ORDERED
    print("="*74)
    print("EQUILIBRIUM LAB  ·  source:",src)
    print("family: W@2..14 + D@2..14 = 26 independent equilibrium lines")
    print("="*74)

    tot=len(R['all']); new_swing=len(R['struct'])
    print(f"\n[Q1] STRUCTURE-DRIVEN vs price-drift")
    print(f"  total migrations {tot} · NEW swing {new_swing} ({100*new_swing/max(1,tot):.0f}%) · price-cross {tot-new_swing} ({100*(tot-new_swing)/max(1,tot):.0f}%)")

    print(f"\n[Q2/Q3] PER-LINE  (respect {a.M} bars fwd, no lookahead)")
    print(f"  {'line':>6} {'migs':>5} {'respTOUCH':>10} {'respHOLD':>9}")
    for tf in ('W','D'):
        for L in Ls:
            ms=R['per_line'][(tf,L)]
            print(f"  {tf+'@'+str(L):>6} {len(ms):>5} {rate(ms,'respected_touch'):>9.0f}% {rate(ms,'respected_hold'):>8.0f}%")

    print(f"\n[Q4] COHERENCE of STRUCTURE-DRIVEN migrations (>= {a.thresh} lines same-way, +/-2d)")
    print(f"  events {len(R['ev'])} · respTOUCH coherent {rate(R['coh'],'respected_touch'):.0f}% vs struct {rate(R['struct'],'respected_touch'):.0f}%  |  respHOLD coherent {rate(R['coh'],'respected_hold'):.0f}% vs struct {rate(R['struct'],'respected_hold'):.0f}%")

    ll=lead_lag(R['ev'])
    if ll:
        ranked=sorted(ll.items(), key=lambda kv:kv[1][0])
        print(f"\n[Q5] LEAD-LAG (order in coherent events; LOW leads)")
        print("  LEADERS:", ", ".join(f"{tf}@{L}({r:.1f})" for (tf,L),(r,_) in ranked[:5]))
        print("  LAGGERS:", ", ".join(f"{tf}@{L}({r:.1f})" for (tf,L),(r,_) in ranked[-5:]))

    # ── SHUFFLE SURROGATE CONTROL — does temporal ORDER matter? ──
    so,sh,sl,sc=surrogate(o,h,l,c, seed=a.seed+101)
    S=analyze(so,sh,sl,sc,Ls,a.M,a.thresh)
    print(f"\n[CONTROL] SHUFFLED-RETURN SURROGATE (same distribution, time-order destroyed)")
    print(f"  coherence gap  ORDERED:  +{R['gap_t']:.0f}pt touch / +{R['gap_h']:.0f}pt hold")
    print(f"  coherence gap  SURROGATE:+{S['gap_t']:.0f}pt touch / +{S['gap_h']:.0f}pt hold")
    print(f"  EXCESS (ordered - surrogate): {R['gap_t']-S['gap_t']:+.0f}pt touch / {R['gap_h']-S['gap_h']:+.0f}pt hold")
    print(f"  >>> EXCESS > 0 = coherence relies on real time-ORDER (auction memory), not")
    print(f"      just the return distribution. EXCESS ~ 0 = it's a distributional artifact.")

    # ── HIGHER-LOW / LOWER-HIGH SEQUENCING EXPERIMENT (surrogate-controlled) ──
    seq,iso=sequencing(R['per_line'])
    sqS,isS=sequencing(S['per_line'])
    seq_gap_t=rate(seq,'respected_touch')-rate(iso,'respected_touch')
    seq_gap_h=rate(seq,'respected_hold') -rate(iso,'respected_hold')
    sur_gap_t=rate(sqS,'respected_touch')-rate(isS,'respected_touch')
    sur_gap_h=rate(sqS,'respected_hold') -rate(isS,'respected_hold')
    print(f"\n[EXPERIMENT] STRUCTURAL SEQUENCING (equilibrium stair-stepping: run>=2 vs single)")
    print(f"  ORDERED   sequenced {len(seq)}/isolated {len(iso)} · respTOUCH {rate(seq,'respected_touch'):.0f}% vs {rate(iso,'respected_touch'):.0f}% (+{seq_gap_t:.0f}) · respHOLD {rate(seq,'respected_hold'):.0f}% vs {rate(iso,'respected_hold'):.0f}% (+{seq_gap_h:.0f})")
    print(f"  SURROGATE sequenced {len(sqS)}/isolated {len(isS)} · gap +{sur_gap_t:.0f} touch / +{sur_gap_h:.0f} hold")
    print(f"  EXCESS (ordered - surrogate): {seq_gap_t-sur_gap_t:+.0f}pt touch / {seq_gap_h-sur_gap_h:+.0f}pt hold")
    print(f"  >>> EXCESS > 0 = a CHAIN of higher-lows repricing equilibrium up is respected")
    print(f"      more BECAUSE of real time-order — your phenomenon, beyond distribution.")

    print("\n" + "-"*74)
    print("READING HONESTLY:")
    print("  • Default run = synthetic NULL. The two NEW tests (surrogate EXCESS,")
    print("    sequencing) are what real data must light up. Synthetic shows the method.")
    print("  • Feed real data:  python3 equilibrium_lab.py --csv YOURFILE.csv")
    print("-"*74)

if __name__=="__main__":
    main()
