#!/usr/bin/env python3
"""LEVEL-CORE CROSS-TF PARITY AUDIT — before/after the root-cause fix.

Reconstructs Level Core's internal level book on 1m/5m/15m/1H from ONE shared HTF
anchor stream, two ways:

  OLD (pre-fix, the reported bug): membership evicts by CHART close; confidence
       decays in CHART bars  -> books DIVERGE per timeframe (answers A + B YES).

  FIXED (root cause removed): membership evicts by a TF-INVARIANT HTF close (refPx);
       every time-based measure (decay / separation / qualified spacing) is counted
       in the level's OWN degree-bars via event timestamps -> books are BYTE-IDENTICAL
       on every chart timeframe. Asserted below.

This mirrors the frozen edits in level_core_v2.pine:
  f_found  eviction  close -> refPx           (:173/:175)
  f_audit  decay     bar_index-ev.bar -> (nowRef-ev.t)/f_degMs(deg)   (:270)
  f_separation / f_qualified  .bar -> .t / f_degMs(deg)
"""
from math import floor, ceil

DEGSEC = {"1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800}
DEGW = {"1H": 0.55, "4H": 0.70, "1D": 0.85, "1W": 1.00}
DECAY_BARS = 150.0
EVID_NORM = 5.0
MAXLVLS = 2
TOPN = 3
TF_SEC = {"1m": 60, "5m": 300, "15m": 900, "1H": 3600}
DAY = 86400
T0, T1 = 0, 3 * DAY

_PATH = [(0, 75.50), (DAY, 74.00), (2 * DAY - 3300, 73.355), (2 * DAY, 73.90), (T1, 73.90)]
def p(t):
    for (t0, v0), (t1, v1) in zip(_PATH, _PATH[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return _PATH[-1][1]

def bar_close(tf, t):
    I = TF_SEC[tf]
    return round(p(ceil((t - T0) / I) * I + T0), 4)

def bar_index(tf, t):
    return floor((t - T0) / TF_SEC[tf])

# shared anchor stream (price, degree, creation_time_s, [event_times_s]) — TF-invariant
ANCHORS = [
    (73.33, "1D", 10, [10, 1.0 * DAY, 2.6 * DAY]),
    (73.40, "4H", 20, [20, 1.2 * DAY, 2.2 * DAY]),
    (76.00, "1D", 2 * DAY - 3300 + 5, [2 * DAY - 3300 + 5, 2.9 * DAY]),
]
CREATE = sorted(ANCHORS, key=lambda a: a[2])
NOWREF = (T1 // 3600) * 3600           # TF-invariant "now", 1H-aligned

def build_book(tf, fixed):
    book = []
    for anc in CREATE:
        px, deg, tc, evs = anc
        band = px * 0.40 / 100.0
        if any(abs(b[0] - px) <= band and b[1] == deg for b in book):
            continue
        if len(book) < MAXLVLS:
            book.append(anc)
        else:
            ref = bar_close("1H", tc) if fixed else bar_close(tf, tc)   # <-- the eviction fix
            far = max(range(len(book)), key=lambda i: abs(book[i][0] - ref))
            book.pop(far)
            book.append(anc)
    return book

def confidence(tf, anc, fixed):
    px, deg, tc, evs = anc
    wsum, ages = 0.0, []
    for te in evs:
        if fixed:
            age = max(0.0, (NOWREF - te) / DEGSEC[deg])        # degree-bars (fix)
        else:
            age = max(0, bar_index(tf, T1) - bar_index(tf, te))  # chart bars (bug)
        ages.append(age)
        wsum += 1.0 / (1.0 + age / DECAY_BARS)
    evidF = min(wsum / EVID_NORM, 1.0)
    conf = min(max((0.55 + 0.45 * evidF) * DEGW[deg] * 100.0, 0.0), 100.0)
    return round(conf), round(sum(ages) / len(ages), 1) if ages else 0

def dump(tf, fixed):
    rows = []
    for anc in build_book(tf, fixed):
        conf, decay_age = confidence(tf, anc, fixed)
        rows.append([anc[0], anc[1], int(anc[2]), len(anc[3]), conf, decay_age])
    rows.sort(key=lambda r: -r[0])
    order = sorted(range(len(rows)), key=lambda i: -rows[i][4])
    for rank, i in enumerate(order):
        rows[i].append(rank + 1 if rank < TOPN else "-")
    return rows

def show(mode, fixed):
    print(f"\n############ {mode} ############")
    books = {tf: dump(tf, fixed) for tf in TF_SEC}
    hdr = f"{'anchor':>8} {'src':>4} {'created':>8} {'touch':>5} {'conf':>4} {'decayAge':>8} {'star':>4}"
    for tf in TF_SEC:
        print(f"\n=== {tf} book (before rendering) ===\n{hdr}")
        for r in books[tf]:
            print(f"{r[0]:>8.2f} {r[1]:>4} {r[2]:>8} {r[3]:>5} {r[4]:>4} {r[5]:>8} {str(r[6]):>4}")
    return books

def diff(books):
    all_px = sorted({r[0] for tf in TF_SEC for r in books[tf]}, reverse=True)
    membership = conf = False
    print("\n--- cross-TF comparison ---")
    for px in all_px:
        cells, confs = [], set()
        for tf in TF_SEC:
            m = [r for r in books[tf] if r[0] == px]
            if m:
                confs.add(m[0][4]); cells.append(f"{tf}:{m[0][1]}/c{m[0][4]}")
            else:
                cells.append(f"{tf}:—")
        present = sum(1 for tf in TF_SEC if any(r[0] == px for r in books[tf]))
        if present != len(TF_SEC): membership = True
        if len(confs) > 1: conf = True
        flag = "  <-- MEMBERSHIP" if present != len(TF_SEC) else ("  <-- CONF" if len(confs) > 1 else "")
        print(f"  {px:>7.2f}  " + " | ".join(cells) + flag)
    return membership, conf


if __name__ == "__main__":
    old = show("OLD  (chart-close eviction + chart-bar decay)", fixed=False)
    mo, co = diff(old)
    fix = show("FIXED (refPx eviction + degree-bar decay)", fixed=True)
    mf, cf = diff(fix)

    # the proof: after the fix every timeframe's book is byte-identical
    ref = fix["1m"]
    identical = all(fix[tf] == ref for tf in TF_SEC)

    print("\n================ VERDICT ================")
    print(f"OLD  : A membership differs = {'YES' if mo else 'no'} | B confidence differs = {'YES' if co else 'no'}")
    print(f"FIXED: A membership differs = {'YES' if mf else 'no'} | B confidence differs = {'YES' if cf else 'no'}")
    assert mo and co, "old model should reproduce the bug"
    assert not mf and not cf and identical, "FIX FAILED — books still differ across timeframes"
    print("\nFIXED books are BYTE-IDENTICAL on 1m/5m/15m/1H (membership + confidence + star).")
    print("Root causes removed at source (eviction ref + degree-bar time): the cross-TF")
    print("instability class is eliminated, not masked. PASS")
