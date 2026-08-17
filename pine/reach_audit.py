#!/usr/bin/env python3
"""REACH AUDIT — why levels are MISSING on low timeframes, and the fix.

Root cause (distinct from the earlier eviction/decay divergence): the book is
ACCUMULATED by walking CHART bars, so a chart only ever creates the HTF pivots that
fall inside its own bar-history window (max_bars_back * chart_interval). Low TFs reach
back only days, so older 4H/1D levels are never created there.

  chart reach = 5000 bars * interval:
    1m ~3.5d | 5m ~17d | 15m ~52d | 1h ~208d | 1D ~13y

FIX: source each degree's book INSIDE HTF context (request.security), driven by the
DEGREE's own bar history (5000 of ITS bars), independent of the chart. Then every
chart TF receives the identical, complete set. This models both to prove it.
"""
MAXBARS = 5000
MAXLVLS = 60
DAY = 1.0
NOW = 200.0                      # 200 days of history in this scenario
CHART = {"1m": 1 / 1440, "5m": 5 / 1440, "15m": 15 / 1440, "1h": 1 / 24, "1D": 1.0}   # days/bar
DEG_DAYS = {"1H": 1 / 24, "4H": 4 / 24, "1D": 1.0, "1W": 7.0}                          # days/bar
REFPX = 74.0                     # TF-invariant centering reference (fastest HTF close)

def chart_reach(tf):  # days a chart TF can look back
    return MAXBARS * CHART[tf]

def deg_reach(deg):   # days a degree's OWN context looks back (chart-independent)
    return MAXBARS * DEG_DAYS[deg]

# ── shared anchor stream: (price, degree, creation_day) spread across 200 days ──
# the exact SOL-like set you see: recent ones near price, older ones further back.
ANCHORS = [
    (78.20, "4H", 195.0), (77.08, "4H", 190.0), (76.55, "1D", 120.0), (76.04, "1D", 150.0),
    (75.60, "1D", 118.0), (74.97, "1D", 175.0), (74.08, "4H", 199.0), (73.89, "4H", 188.0),
    (73.33, "1D", 185.0), (73.14, "1H", 199.5), (72.28, "4H", 180.0), (67.23, "1W", 60.0),
    (64.02, "1D", 55.0), (97.63, "1W", 20.0), (94.03, "1D", 25.0), (92.10, "1D", 26.0),
    (87.03, "1D", 40.0), (83.29, "1D", 92.0), (81.35, "1D", 100.0),
]

def build_old(tf):
    # chart-walk: only anchors whose creation falls inside THIS chart's reach window
    horizon = NOW - chart_reach(tf)
    got = [a for a in ANCHORS if a[2] >= horizon]
    got.sort(key=lambda a: abs(a[0] - REFPX))
    return sorted(got[:MAXLVLS], key=lambda a: -a[0])

def build_new(tf):
    # HTF-context: each anchor created if within its DEGREE's reach (chart-independent)
    got = [a for a in ANCHORS if (NOW - a[2]) <= deg_reach(a[1])]
    got.sort(key=lambda a: abs(a[0] - REFPX))
    return sorted(got[:MAXLVLS], key=lambda a: -a[0])

def show(title, fn):
    print(f"\n############ {title} ############")
    books = {}
    for tf in CHART:
        b = fn(tf)
        books[tf] = b
        near = [f"{a[0]:.2f}" for a in b if 73.0 <= a[0] <= 79.0]
        print(f"  {tf:>3}: {len(b):>2} levels   near-price(73-79): {', '.join(near) if near else '— NONE'}")
    return books

if __name__ == "__main__":
    old = show("OLD  (chart-walk accumulation — reach-limited)", build_old)
    new = show("NEW  (HTF-context sourcing — chart-independent)", build_new)

    old_counts = {tf: len(old[tf]) for tf in CHART}
    new_ref = new["1D"]
    new_identical = all(new[tf] == new_ref for tf in CHART)

    print("\n================ VERDICT ================")
    print(f"OLD level counts per TF : {old_counts}   <-- 1m/5m starved, the reported failure")
    print(f"NEW identical + complete on every TF: {new_identical}  ({len(new_ref)} levels each)")
    assert old_counts["1m"] < old_counts["1h"], "old model should show reach starvation"
    assert new_identical and len(new_ref) == len(ANCHORS), "HTF-context sourcing must give the full set on every TF"
    print("\nHTF-context sourcing gives ALL levels on 1m/5m/15m/1h/1D identically.")
    print("Blueprint locked: per-degree book built inside request.security(degree_tf, ...),")
    print("returned as arrays, merged + capped by refPx on the chart. PASS")
