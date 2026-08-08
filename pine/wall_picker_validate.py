#!/usr/bin/env python3
"""WALL-PICKER validator — models f_pickWall / f_wallOK in level_core_v2.pine and
proves the Item-4 fix: a floor/ceiling no longer DISAPPEARS when nothing on that
side clears zoneMinConf. The old picker had two passes (strict, then relaxed) but
BOTH kept the `c >= zoneMinConf` gate, so if every candidate scored below it the
picker returned None and the wall (and the Claude Line, which needs both) vanished
— exactly when a fresh directional move has only new, still-unproven structure.

The fix adds a THIRD, last-resort pass that drops the confidence gate entirely and
takes the nearest level on that side regardless of score, tagged WEAK so it reads
as a low-confidence placeholder, not a real wall. A side now only goes blank if the
book has literally nothing on it.

Claims:
  1. Normal case unchanged: a level clearing zoneMinConf is picked, weak=False.
  2. OLD picker DISAPPEARS when nothing clears the gate (control), NEW picker
     returns the nearest level tagged weak=True.
  3. Last-resort still picks the NEAREST level on that side, not just any.
  4. Proven gate still wins when a proven level is in reach (fix doesn't weaken
     authority — the last-resort pass only runs when passes 0 and 1 both fail).
  5. Determinism.
"""

ZONE_MIN_CONF = 35.0


def wall_ok(L, mode, zmc=ZONE_MIN_CONF, wall_proven="Proven only", wall_deg_pref=True):
    c, held = L["conf"], L["held"]
    degOK = (not wall_deg_pref) or L["deg"] >= 1
    if wall_proven == "Strongest only":
        pOK = True
    elif wall_proven == "Prefer proven":
        pOK = held >= 2 or c >= zmc + 15.0
    else:                                   # "Proven only"
        pOK = held >= 2
    confOK = c >= zmc
    if mode == 2:                           # last-resort: no gate at all
        return True
    if mode == 1:                           # relaxed: conf only
        return confOK
    return confOK and degOK and pOK         # strict: conf + degree + proven


def pick_wall(book, px, direction, passes=3, **kw):
    """direction: +1 = ceiling (above px), -1 = floor (below px). Returns
    (price, is_proven, is_weak). passes=2 models the OLD picker."""
    best, best_pr, found_pass = None, False, -1
    for p in range(passes):
        if best is None:
            for L in book:
                side = L["anchor"] > px if direction == 1 else L["anchor"] < px
                nearer = best is None or (L["anchor"] < best if direction == 1 else L["anchor"] > best)
                if side and nearer and wall_ok(L, p, **kw):
                    best = L["anchor"]
                    best_pr = L["held"] >= 2
                    found_pass = p
    return best, best_pr, (found_pass == 2)


if __name__ == "__main__":
    px = 100.0

    # ── CLAIM 1: normal case — a qualifying proven 4H level above price ──
    book1 = [
        {"anchor": 110.0, "deg": 1, "conf": 60.0, "held": 3},   # clears conf, proven, 4H
        {"anchor": 130.0, "deg": 2, "conf": 70.0, "held": 4},
    ]
    p, pr, wk = pick_wall(book1, px, 1)
    assert p == 110.0 and pr and not wk, f"normal pick broke: {(p, pr, wk)}"

    # ── CLAIM 2: nothing clears zoneMinConf (all fresh, conf < 35) ──
    #   OLD (2-pass) disappears; NEW (3-pass) returns nearest, tagged weak.
    book2 = [
        {"anchor": 108.0, "deg": 0, "conf": 20.0, "held": 1},   # 1H, fresh, weak
        {"anchor": 115.0, "deg": 1, "conf": 28.0, "held": 1},   # 4H, fresh, weak
    ]
    old_p, _, _ = pick_wall(book2, px, 1, passes=2)             # the OLD behaviour
    assert old_p is None, f"control: old 2-pass picker should DISAPPEAR, got {old_p}"
    new_p, new_pr, new_wk = pick_wall(book2, px, 1, passes=3)   # the FIX
    assert new_p == 108.0, f"last-resort should pick the nearest, got {new_p}"
    assert new_wk and not new_pr, f"last-resort wall must be tagged weak/unproven, got {(new_pr, new_wk)}"

    # ── CLAIM 3: last-resort picks the NEAREST on that side, not the strongest ──
    book3 = [
        {"anchor": 140.0, "deg": 2, "conf": 30.0, "held": 1},   # stronger but far
        {"anchor": 105.0, "deg": 0, "conf": 10.0, "held": 0},   # weaker but nearest
    ]
    p3, _, wk3 = pick_wall(book3, px, 1, passes=3)
    assert p3 == 105.0 and wk3, f"last-resort should be nearest (105), got {p3}"

    # ── CLAIM 4: proven authority still wins — last-resort only fires as fallback ─
    book4 = [
        {"anchor": 107.0, "deg": 0, "conf": 12.0, "held": 0},   # near junk (would win last-resort)
        {"anchor": 120.0, "deg": 2, "conf": 55.0, "held": 3},   # farther, proven 1D — the real wall
    ]
    p4, pr4, wk4 = pick_wall(book4, px, 1, passes=3)
    assert p4 == 120.0 and pr4 and not wk4, f"proven wall must win over near junk, got {(p4, pr4, wk4)}"

    # ── CLAIM 5: determinism ──
    a = pick_wall(book2, px, 1, passes=3)
    b = pick_wall(book2, px, 1, passes=3)
    assert a == b, "non-deterministic"

    # floor side sanity (direction = -1)
    bookF = [{"anchor": 92.0, "deg": 0, "conf": 15.0, "held": 0},
             {"anchor": 85.0, "deg": 1, "conf": 18.0, "held": 1}]
    pf, _, wkf = pick_wall(bookF, px, -1, passes=3)
    assert pf == 92.0 and wkf, f"floor last-resort should pick nearest below (92), got {pf}"

    print("WALL-PICKER VALIDATED:")
    print("  1 normal pick unchanged · 2 old picker DISAPPEARS / new returns nearest (weak)")
    print("  3 last-resort = nearest on side · 4 proven authority still wins first")
    print("  5 determinism · floor side sanity")
    print("  all 5 claims PASS")
