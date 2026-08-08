#!/usr/bin/env python3
"""ALL-LEVELS SELECTION validator — models the new display-selection logic in
level_core_v2.pine's "if barstate.islast" block (the Pass-1/Pass-2 rewrite that
replaces "nearest maxLvls by distance" with "top maxLvls by confluence-adjusted
strength, post-merge, LIVE always included").

Mirrors, in order, exactly what the Pine code now does:
  Pass 1 — for every eligible (degree-on, min-conf/min-events) level, find its
           cluster representative (the strongest level within mergeBandPct;
           ties go to the LOWER book index) and its cluster strength
           (conf + conflBonus * (clCount-1), capped at 100).
  Pass 2 — rank representatives by cluster strength (f_rankTop: strict '>' so
           ties keep the earlier-encountered index) and keep the top N. Force
           the LIVE nearest-above and nearest-below into the shown set
           regardless of rank.

Claims checked:
  1. Selection is BY STRENGTH, not distance: a strong-but-far level survives
     into the top-N while a weak-but-near level (that a nearest-by-distance
     cap would have kept) is dropped.
  2. Duplicate-price levels from different degrees collapse to ONE slot (the
     stronger one), not two — merging happens before ranking, so a cluster
     never burns two of the N slots on itself.
  3. LIVE nearest above/below always shown, even when its own strength would
     rank it outside the top N.
  4. Graceful degrade: fewer eligible candidates than N just shows all of
     them — no crash, no padding with ineligible levels.
  5. Determinism / tie-break parity: equal cluster strength -> lower book
     index wins the representative slot and the rank slot (matches Pine's
     strict '>' comparisons in both the merge scan and f_rankTop).
"""

MERGE_BAND_PCT = 0.80
CONFL_BONUS = 6.0


def select(levels, min_conf, min_events, merge_on, top_n, live_idx=None,
           reach_pct=None, cur_price=None):
    """levels: list of dicts {anchor, deg_on(bool), conf, events}. live_idx:
    set of indices always force-shown. reach_pct: optional % of price radius —
    levels outside it are excluded from ranking (LIVE always bypasses).
    Returns (shown_idx_set, clCount, clStr)."""
    n = len(levels)
    cl_count = [1] * n
    cl_str = [0.0] * n
    rep_idx = []
    live_idx = live_idx or set()

    def eligible(i):
        L = levels[i]
        live = i in live_idx
        in_reach = (reach_pct is None or cur_price is None or
                    abs(L["anchor"] - cur_price) / cur_price * 100 <= reach_pct or live)
        return L["deg_on"] and (L["conf"] >= min_conf or live) and (L["events"] >= min_events or live) and in_reach

    for i in range(n):
        if not eligible(i):
            continue
        Li = levels[i]
        merged = False
        count = 1
        if merge_on:
            band = Li["anchor"] * MERGE_BAND_PCT / 100.0
            for k in range(n):
                if k == i:
                    continue
                Lk = levels[k]
                live_k = k in live_idx
                cand = Lk["deg_on"] and (Lk["conf"] >= min_conf or live_k) and (Lk["events"] >= min_events or live_k)
                if cand and abs(Lk["anchor"] - Li["anchor"]) <= band:
                    count += 1
                    if Lk["conf"] > Li["conf"] or (Lk["conf"] == Li["conf"] and k < i):
                        merged = True
        cl_count[i] = count
        cl_str[i] = min(100.0, Li["conf"] + CONFL_BONUS * (count - 1))
        if not merged:
            rep_idx.append(i)

    # f_rankTop: selection sort, strict '>' so ties keep the earlier-encountered index
    used = [False] * len(rep_idx)
    top_sel = []
    want = min(top_n, len(rep_idx))
    for _ in range(want):
        best_j, best_c = -1, -1.0
        for j, ri in enumerate(rep_idx):
            if not used[j] and cl_str[ri] > best_c:
                best_c = cl_str[ri]
                best_j = j
        if best_j >= 0:
            used[best_j] = True
            top_sel.append(rep_idx[best_j])

    shown = set(top_sel) | {i for i in live_idx if i is not None and 0 <= i < n}
    return shown, cl_count, cl_str


if __name__ == "__main__":
    # ── CLAIM 1: strength beats distance ──────────────────────────────────
    # A far, strong 1W level (conf 80) vs a near, weak 1H level (conf 10) that
    # a nearest-by-distance cap of N=1 would have kept instead.
    levels = [
        {"anchor": 100.0, "deg_on": True, "conf": 10.0, "events": 3},   # near price (100), weak
        {"anchor": 500.0, "deg_on": True, "conf": 80.0, "events": 10},  # far from price, strong
    ]
    shown, cc, cs = select(levels, min_conf=0.0, min_events=1, merge_on=True, top_n=1)
    assert shown == {1}, f"strength-based selection failed: kept {shown}, expected the strong far level"

    # ── CLAIM 2: cross-degree duplicates collapse to ONE slot ────────────
    # Same price found independently on 1H (conf 40) and 4H (conf 55) -> one
    # book entry each (mirrors f_found's per-degree dedup), but they sit within
    # the merge band of each other -> must yield exactly ONE representative.
    levels2 = [
        {"anchor": 200.00, "deg_on": True, "conf": 40.0, "events": 5},  # 1H copy
        {"anchor": 200.05, "deg_on": True, "conf": 55.0, "events": 8},  # 4H copy, same price band
        {"anchor": 900.00, "deg_on": True, "conf": 20.0, "events": 2},  # unrelated distant level
    ]
    shown2, cc2, cs2 = select(levels2, min_conf=0.0, min_events=1, merge_on=True, top_n=2)
    assert 0 not in shown2, "the weaker duplicate should have been merged away, not shown"
    assert 1 in shown2, "the stronger duplicate should represent the cluster"
    assert cc2[1] == 2, f"cluster count should be 2 (both duplicates counted), got {cc2[1]}"
    assert cs2[1] == 55.0 + CONFL_BONUS * 1, "cluster strength should include the confluence bonus"
    # with top_n=2 both the cluster-rep and the distant level should show (2 slots, 2 candidates)
    assert shown2 == {1, 2}, f"expected the 2 real slots filled, got {shown2}"

    # ── CLAIM 3: LIVE always shown even if it would rank outside top-N ───
    levels3 = [{"anchor": 100.0 + i, "deg_on": True, "conf": 90.0 - i, "events": 5} for i in range(10)]
    # index 9 is the weakest (conf=81) -- still well above 0, but outside a top_n=3 cut.
    # Make a genuinely weak LIVE candidate at the very back of the ranking.
    levels3.append({"anchor": 500.0, "deg_on": True, "conf": 1.0, "events": 1})  # index 10, weakest by far
    live = {10}
    shown3, _, _ = select(levels3, min_conf=0.0, min_events=1, merge_on=True, top_n=3, live_idx=live)
    assert 10 in shown3, "LIVE level must show even when it ranks outside the top N"
    assert len(shown3) == 4, f"expected top-3 + 1 forced LIVE = 4 shown, got {len(shown3)}"

    # ── CLAIM 4: graceful degrade — fewer eligible candidates than N ─────
    thin = [
        {"anchor": 100.0, "deg_on": True, "conf": 50.0, "events": 3},
        {"anchor": 300.0, "deg_on": True, "conf": 20.0, "events": 1},
        {"anchor": 700.0, "deg_on": False, "conf": 99.0, "events": 9},  # wrong degree -> ineligible
    ]
    shown4, _, _ = select(thin, min_conf=0.0, min_events=1, merge_on=True, top_n=20)
    assert shown4 == {0, 1}, f"expected exactly the 2 eligible levels, got {shown4} (no crash, no padding)"

    # ── CLAIM 5: determinism / tie-break — equal strength -> lower index wins ─
    tied = [
        {"anchor": 100.00, "deg_on": True, "conf": 50.0, "events": 5},  # idx 0
        {"anchor": 100.02, "deg_on": True, "conf": 50.0, "events": 5},  # idx 1, same conf, in-band
    ]
    shown5, cc5, _ = select(tied, min_conf=0.0, min_events=1, merge_on=True, top_n=2)
    assert shown5 == {0}, f"equal-strength duplicate should merge into the LOWER index, got {shown5}"
    assert cc5[0] == 2, "the surviving representative should carry the full cluster count"
    # run twice -> identical result (no ordering nondeterminism)
    shown5b, _, _ = select(tied, min_conf=0.0, min_events=1, merge_on=True, top_n=2)
    assert shown5 == shown5b, "non-deterministic selection"

    # ── CLAIM 6: reach filter excludes archaeology; near-price structure wins ─
    # Simulate a meme coin: current price 0.0012, 20 near-price levels within 30%,
    # plus 5 ancient ATH levels at 0.006-0.009 (3x-7x above current — well outside 30%).
    # Without reach limit, ancient ATH levels (high CONF from many old touches) would rank
    # into the top-N ahead of current-market levels. With reach limit they don't compete.
    cur_px = 0.0012
    near_lvls = [{"anchor": cur_px * (1.0 + (i - 10) * 0.015), "deg_on": True, "conf": 30.0 + i * 2, "events": 3 + i}
                 for i in range(20)]
    ath_lvls = [{"anchor": cur_px * (4.0 + i), "deg_on": True, "conf": 90.0 - i, "events": 20 + i}
                for i in range(5)]
    all_lvls = near_lvls + ath_lvls  # indices 0-19 near, 20-24 ATH

    # without reach limit: ATH levels (highest CONF) occupy the top slots
    shown_no_reach, _, _ = select(all_lvls, min_conf=0.0, min_events=1, merge_on=False,
                                  top_n=5, reach_pct=None, cur_price=cur_px)
    ath_in_no_reach = [i for i in shown_no_reach if i >= 20]
    assert len(ath_in_no_reach) > 0, "without reach limit ATH levels should dominate top-5 by CONF"

    # with 30% reach limit: only near-price levels compete
    shown_reach, _, _ = select(all_lvls, min_conf=0.0, min_events=1, merge_on=False,
                               top_n=5, reach_pct=30.0, cur_price=cur_px)
    ath_in_reach = [i for i in shown_reach if i >= 20]
    assert len(ath_in_reach) == 0, f"reach filter must exclude ATH archaeology, got ATH indices {ath_in_reach}"
    assert all(i < 20 for i in shown_reach), "all shown levels must be near-price"
    assert len(shown_reach) == 5, "should still fill all N slots from near-price pool"

    # ── CLAIM 7: reach bypass for LIVE — LIVE shown even if outside reach range ─
    # LIVE nearest above happens to be a distant recovery level outside 30% reach.
    ath_live_levels = [
        {"anchor": cur_px * 0.95, "deg_on": True, "conf": 40.0, "events": 3},   # idx 0, near, strong-ish
        {"anchor": cur_px * 1.05, "deg_on": True, "conf": 35.0, "events": 2},   # idx 1, near
        {"anchor": cur_px * 5.0,  "deg_on": True, "conf": 20.0, "events": 1},   # idx 2, FAR, but LIVE
    ]
    live_far = {2}
    shown7, _, _ = select(ath_live_levels, min_conf=0.0, min_events=1, merge_on=False,
                          top_n=2, reach_pct=30.0, cur_price=cur_px, live_idx=live_far)
    assert 2 in shown7, "LIVE level must show even when it is outside the reach range"
    assert len(shown7) == 3, f"expected top-2 near + 1 forced LIVE = 3 total, got {len(shown7)}"

    print("ALL-LEVELS SELECTION VALIDATED:")
    print("  1 strength beats distance · 2 cross-degree duplicates collapse to 1 slot")
    print("  3 LIVE always forced in · 4 graceful degrade (no crash/padding)")
    print("  5 tie-break determinism (lower index wins)")
    print("  6 reach filter excludes ancient archaeology before ranking")
    print("  7 LIVE bypass overrides reach filter")
    print("  all 7 claims PASS")
