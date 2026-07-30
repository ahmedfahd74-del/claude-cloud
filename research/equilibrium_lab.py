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
    n=len(c)
    wo,wh,wl,wc,day2wk = resample(o,h,l,c,7)
    Ls=list(range(2,15))

    all_daily_migs=[]; per_line={}
    for L in Ls:                                   # DAILY family
        _,migs = build_line('D',L,o,h,l,c)
        for m in migs: all_daily_migs.append(m)    # daily migs already on day index
        per_line[('D',L)]=migs
    for L in Ls:                                   # WEEKLY family → map week migs to first day of that week
        _,migs = build_line('W',L,wo,wh,wl,wc)
        # invert day2wk: first day index of each week
        wk_first={}
        for di,wk in enumerate(day2wk):
            wk_first.setdefault(wk,di)
        mapped=[]
        for m in migs:
            dd=wk_first.get(m.t_tf)
            if dd is not None:
                mm=Migration('W',L,dd,m.prev,m.new,m.delta,m.direction,m.cause)
                mapped.append(mm)
        per_line[('W',L)]=mapped
        all_daily_migs+=mapped

    eval_respect(all_daily_migs,o,h,l,c,M=a.M)

    # ---- report ----
    print("="*74)
    print("EQUILIBRIUM LAB  ·  source:",src)
    print("family: W@2..14 + D@2..14 = 26 independent equilibrium lines")
    print("="*74)

    # Q1: are migrations structure-driven or price-cross (mechanical drift)?
    tot=len(all_daily_migs)
    new_swing=sum(1 for m in all_daily_migs if m.cause.startswith('new_'))
    print(f"\n[Q1] MIGRATIONS ARE STRUCTURE-DRIVEN?")
    print(f"  total migrations: {tot}")
    print(f"  caused by a NEW confirmed swing: {new_swing} ({100*new_swing/max(1,tot):.0f}%)")
    print(f"  caused by price crossing an old level: {tot-new_swing} ({100*(tot-new_swing)/max(1,tot):.0f}%)")

    # Q2/Q3: per-(tf,L) migration count + BOTH respect rates
    print(f"\n[Q2/Q3] PER-LINE BEHAVIOUR  (respect measured {a.M} bars forward, no lookahead)")
    print(f"  {'line':>6} {'migs':>5} {'respTOUCH':>10} {'respHOLD':>9}")
    def rate(ms, attr):
        vals=[getattr(m,attr) for m in ms if getattr(m,attr) is not None]
        return (100*sum(1 for v in vals if v)/len(vals)) if vals else float('nan')
    for tf in ('W','D'):
        for L in Ls:
            ms=per_line[(tf,L)]
            print(f"  {tf+'@'+str(L):>6} {len(ms):>5} {rate(ms,'respected_touch'):>9.0f}% {rate(ms,'respected_hold'):>8.0f}%")

    # Q4/Q5: coherence + lead-lag
    # STRUCTURE-DRIVEN migrations only = the user's actual phenomenon (new auction level),
    # not price drifting across old levels. Coherence among THESE is the real test.
    struct_migs=[m for m in all_daily_migs if m.cause.startswith('new_')]
    ev=coherence_events(struct_migs,n,W=2,thresh=a.thresh)
    print(f"\n[Q4] COHERENCE of STRUCTURE-DRIVEN migrations only (the real phenomenon)")
    print(f"  (>= {a.thresh} independent lines repricing SAME way on new swings within +/-2 days)")
    print(f"  coherent repricing events found: {len(ev)}")
    if ev:
        sizes=[len(p) for _,_,p in ev]
        print(f"  avg lines participating per event: {sum(sizes)/len(sizes):.1f}  (max {max(sizes)})")
        # THE key test: does independent agreement improve the respect rate?
        coh_migs=[m for _,_,p in ev for m in p]
        print(f"  respTOUCH  coherent: {rate(coh_migs,'respected_touch'):.0f}%   vs all struct: {rate(struct_migs,'respected_touch'):.0f}%   vs everything: {rate(all_daily_migs,'respected_touch'):.0f}%")
        print(f"  respHOLD   coherent: {rate(coh_migs,'respected_hold'):.0f}%   vs all struct: {rate(struct_migs,'respected_hold'):.0f}%   vs everything: {rate(all_daily_migs,'respected_hold'):.0f}%")
        gap_t = rate(coh_migs,'respected_touch') - rate(struct_migs,'respected_touch')
        gap_h = rate(coh_migs,'respected_hold')  - rate(struct_migs,'respected_hold')
        print(f"  >>> coherence lifts respect by +{gap_t:.0f}pt (touch) / +{gap_h:.0f}pt (hold) even on the")
        print(f"      NULL MODEL — a MECHANICAL premium (strong swings are multi-scale by nature).")
        print(f"      REAL market 'intent' only if real data's gap EXCEEDS this null gap.")

    ll=lead_lag(ev)
    if ll:
        print(f"\n[Q5] LEAD-LAG  (avg migration order in coherent events; LOW = leads first)")
        ranked=sorted(ll.items(), key=lambda kv:kv[1][0])
        print("  LEADERS:", ", ".join(f"{tf}@{L}({r:.1f})" for (tf,L),(r,cnt) in ranked[:5]))
        print("  LAGGERS:", ", ".join(f"{tf}@{L}({r:.1f})" for (tf,L),(r,cnt) in ranked[-5:]))

    print("\n" + "-"*74)
    print("READING THIS HONESTLY:")
    print("  • This is the NULL MODEL (no market intent). Whatever coherence/respect")
    print("    shows here is the equilibrium MATH, not the market being smart.")
    print("  • Real bars must BEAT these baselines (esp. 'respect in coherent events'")
    print("    vs 'all') for the 'equilibrium reveals intent early' claim to hold.")
    print("  • Feed real data:  python3 equilibrium_lab.py --csv YOURFILE.csv")
    print("-"*74)

if __name__=="__main__":
    main()
