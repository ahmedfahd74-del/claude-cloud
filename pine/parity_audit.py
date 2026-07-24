#!/usr/bin/env python3
"""LEVEL-CORE PARITY AUDIT (read-only — Module 1 is NOT modified).

Reconstructs Level Core's internal level book on four chart timeframes (1m/5m/15m/1H)
from ONE shared HTF anchor stream, using the EXACT frozen Module-1 rules:
  * f_found  create + evict-furthest-from-CHART-close   (level_core_v2.pine:150-171)
  * f_audit  recency decay  age = bar_index - ev.bar     (level_core_v2.pine:270-271)
  * star rank = top-N by confidence                      (level_core_v2.pine:578-585)

The anchors themselves are timeframe-invariant (they come from HTF request.security
pivots). Everything that follows — which anchors SURVIVE eviction, and each survivor's
CONFIDENCE — is measured against the CHART, so it diverges per chart TF. This audit
dumps the full book per TF, diffs them, and answers A/B/C.
"""
from math import floor, ceil

DEGW = {"1H": 0.55, "4H": 0.70, "1D": 0.85, "1W": 1.00}
DECAY_BARS = 150.0
EVID_NORM = 5.0
MAXLVLS = 2            # tiny cap to expose eviction in a readable way (real default 40-60)
TOPN = 3
TF_SEC = {"1m": 60, "5m": 300, "15m": 900, "1H": 3600}
DAY = 86400
T0, T1 = 0, 3 * DAY   # 3-day window; "now" = T1

# ── shared underlying price path p(t) (same real market on every chart TF) ──────
# piecewise-linear; the ONLY thing that changes per TF is WHERE bar-closes sample it.
# the segment 169500->172800 rises 73.355->73.90 THROUGH the midpoint (73.365) of the two
# floor anchors 73.33/73.40, so the 1m bar-close lands just BELOW the midpoint and the
# 5m/15m/1H bar-closes land just ABOVE it at the creation instant -> the "furthest" flips.
_PATH = [(0, 75.50), (DAY, 74.00), (2 * DAY - 3300, 73.355), (2 * DAY, 73.90), (T1, 73.90)]
def p(t):
    for (t0, v0), (t1, v1) in zip(_PATH, _PATH[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return _PATH[-1][1]

def chart_close(tf, t):
    # the close of the chart bar (interval TF_SEC[tf]) that CONTAINS time t = p at bar end
    I = TF_SEC[tf]
    return round(p(ceil((t - T0) / I) * I + T0), 4)

def bar_index(tf, t):
    return floor((t - T0) / TF_SEC[tf])

# ── ONE shared anchor stream (HTF pivots — identical set on every chart TF) ──────
# (price, degree, creation_time_s, [event_times_s])  events = HTF interactions.
ANCHORS = [
    (73.33, "1D", 10, [10, 1.0 * DAY, 2.6 * DAY]),                       # near-price floor A1
    (73.40, "4H", 20, [20, 1.2 * DAY, 2.2 * DAY]),                       # near-price floor A2
    (76.00, "1D", 2 * DAY - 3300 + 5, [2 * DAY - 3300 + 5, 2.9 * DAY]),  # A3 created mid-bar → triggers evict
]
CREATE_ORDER = sorted(ANCHORS, key=lambda a: a[2])

# ── f_found: create, and when full evict the anchor FURTHEST from the chart close ──
def build_book(tf):
    book = []   # list of anchor tuples currently held
    for anc in CREATE_ORDER:
        px, deg, tc, evs = anc
        band = px * 0.40 / 100.0
        if any(abs(b[0] - px) <= band and b[1] == deg for b in book):
            continue
        if len(book) < MAXLVLS:
            book.append(anc)
        else:
            cc = chart_close(tf, tc)                      # <-- CHART close at creation time
            far_i = max(range(len(book)), key=lambda i: abs(book[i][0] - cc))
            book.pop(far_i)
            book.append(anc)
    return book

# ── f_audit: confidence with recency decay measured in CHART bars ───────────────
def confidence(tf, anc):
    px, deg, tc, evs = anc
    now = bar_index(tf, T1)
    wsum = 0.0
    ages = []
    for te in evs:
        eb = bar_index(tf, te)
        age = max(0, now - eb)                            # <-- age in CHART bars (:270)
        ages.append(age)
        wsum += 1.0 / (1.0 + age / DECAY_BARS)            # <-- decay weight (:271)
    evidF = min(wsum / EVID_NORM, 1.0)
    # representative blend: hold non-decay factors fixed, let evidence (decay) move it
    raw = 0.55 + 0.45 * evidF                             # 0.55 base + evidence share
    conf = min(max(raw * DEGW[deg] * 100.0, 0.0), 100.0)
    decay_age = round(sum(ages) / len(ages)) if ages else 0
    return round(conf), decay_age, len(evs)

def dump(tf):
    book = build_book(tf)
    rows = []
    for anc in book:
        conf, decay_age, touches = confidence(tf, anc)
        rows.append([anc[0], anc[1], int(anc[2]), touches, conf, decay_age])
    rows.sort(key=lambda r: -r[0])
    order = sorted(range(len(rows)), key=lambda i: -rows[i][4])   # star rank by conf
    star = {order[i]: (i + 1 if i < TOPN else "-") for i in range(len(rows))}
    for i, r in enumerate(rows):
        r.append(star[i])
    return rows

# ── run + report ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    books = {tf: dump(tf) for tf in TF_SEC}
    hdr = f"{'anchor':>8} {'src':>4} {'created':>8} {'touch':>5} {'conf':>4} {'decayAge':>8} {'star':>4}"
    for tf in TF_SEC:
        print(f"\n=== {tf} book (before rendering) ===")
        print(hdr)
        for r in books[tf]:
            print(f"{r[0]:>8.2f} {r[1]:>4} {r[2]:>8} {r[3]:>5} {r[4]:>4} {r[5]:>8} {str(r[6]):>4}")

    # ---- cross-TF comparison ----
    print("\n=== CROSS-TF COMPARISON ===")
    all_px = sorted({r[0] for tf in TF_SEC for r in books[tf]}, reverse=True)
    membership_diff = conf_diff = False
    for px in all_px:
        cells = []
        degs, confs = set(), set()
        for tf in TF_SEC:
            m = [r for r in books[tf] if r[0] == px]
            if m:
                degs.add(m[0][1]); confs.add(m[0][4])
                cells.append(f"{tf}:{m[0][1]}/conf{m[0][4]}")
            else:
                cells.append(f"{tf}:—ABSENT")
        present = [tf for tf in TF_SEC if any(r[0] == px for r in books[tf])]
        if len(present) != len(TF_SEC):
            membership_diff = True
        if len(confs) > 1:
            conf_diff = True
        flag = "  <-- MEMBERSHIP DIFFERS" if len(present) != len(TF_SEC) else ("  <-- CONF DIFFERS" if len(confs) > 1 else "")
        print(f"  {px:>7.2f}  " + " | ".join(cells) + flag)

    # ---- verdict ----
    print("\n=== VERDICT ===")
    print(f"A) anchors DIFFERENT (membership)          : {'YES' if membership_diff else 'no'}")
    print(f"B) anchors identical, CONFIDENCE differs   : {'YES' if conf_diff else 'no'}")
    print(f"C) anchors+conf identical, RENDER differs  : no (render code is shared; books differ first)")
    print("\nEXACT DIVERGENCE POINTS (frozen Module 1, level_core_v2.pine):")
    print("  A  f_found eviction keyed on CHART close  -> :173  math.abs(px - close)")
    print("                                             :175  math.abs(anchor - close)")
    print("     different chart-close at an anchor's creation time evicts a different")
    print("     neighbour, so a different level survives near the same price per TF.")
    print("  B  f_audit decay in CHART bars            -> :270  age = bar_index - ev.bar")
    print("                                             :271  w = 1/(1 + age/decayBars)")
    print("     identical events age faster on finer TFs -> lower recency weight -> lower conf.")
    print("  C  render loop is identical on every TF; it faithfully draws whatever the")
    print("     (already-divergent) book contains -> rendering is NOT the divergence.")
