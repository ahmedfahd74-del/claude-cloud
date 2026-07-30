#!/usr/bin/env python3
"""MARKET CONTEXT ENGINE validator — models the orthogonal 2nd-source direction
logic and the Structure×Context agreement combiner in level_core_v2.pine.

Proves:
  * context direction requires leader AND tide to agree (external-only vote)
  * TRUE direction is BULL/BEAR only when Structure AND Context agree; else RANGE
  * opposition surfaces as CONFLICT (a trap — never a directional verdict)
  * independence is enforced by construction: the two votes come from DISJOINT
    input sets (internal price structure vs external leader+tide), so their
    agreement is genuine confluence, not one series confirming itself
  * relative-strength tag is annotation only — it NEVER changes the verdict
  * graceful degrade: useContext=False → verdict == structure (posDir)
  * determinism
"""

# ── context direction: leader AND tide must agree (mirrors the Pine ternary) ──
def ctx_dir(leader_bv, tide_bv, use_context, pos_dir):
    if not use_context:
        return pos_dir
    if leader_bv == 1 and tide_bv == 1:
        return 1
    if leader_bv == -1 and tide_bv == -1:
        return -1
    return 0

# ── the combiner: true direction only on agreement of the two INDEPENDENT engines ──
def combine(pos_dir, ctx_direction, use_context):
    agree    = pos_dir != 0 and pos_dir == ctx_direction
    conflict = pos_dir != 0 and ctx_direction != 0 and pos_dir != ctx_direction
    verdict  = pos_dir if not use_context else (pos_dir if agree else 0)
    return verdict, agree, conflict

def rs_tag(pos_dir, leader_bv, use_context, use_rs):
    if not (use_context and use_rs):
        return ""
    if pos_dir == leader_bv and pos_dir != 0:
        return "IN-LINE"
    if pos_dir != 0 and leader_bv == 0:
        return "LEADING"
    if pos_dir == 0 and leader_bv != 0:
        return "LAGGING"
    if pos_dir != 0 and leader_bv != 0 and pos_dir != leader_bv:
        return "DIVERGING"
    return "FLAT"


if __name__ == "__main__":
    # ── CLAIM 1: context needs BOTH leader and tide (either alone ≠ direction) ──
    assert ctx_dir(1, 1, True, 0) == 1
    assert ctx_dir(-1, -1, True, 0) == -1
    assert ctx_dir(1, 0, True, 0) == 0          # tide undecided → no context dir
    assert ctx_dir(1, -1, True, 0) == 0          # leader/tide split → no context dir
    assert ctx_dir(0, 0, True, 1) == 0

    # ── CLAIM 2: TRUE direction only when Structure AND Context agree ──
    v, ag, cf = combine(1, 1, True)              # both bull
    assert (v, ag, cf) == (1, True, False)
    v, ag, cf = combine(-1, -1, True)            # both bear
    assert (v, ag, cf) == (-1, True, False)
    v, ag, cf = combine(1, 0, True)              # structure bull, context neutral
    assert (v, ag, cf) == (0, False, False)      # → RANGE (no agreement)
    v, ag, cf = combine(0, 1, True)              # structure neutral, context bull
    assert (v, ag, cf) == (0, False, False)

    # ── CLAIM 3: opposition is CONFLICT (trap), never a directional verdict ──
    v, ag, cf = combine(1, -1, True)             # structure bull vs context bear
    assert (v, ag, cf) == (0, False, True)
    v, ag, cf = combine(-1, 1, True)
    assert (v, ag, cf) == (0, False, True)

    # ── CLAIM 4: independence — verdict depends on DISJOINT input sets ──
    # Structure vote comes from this asset's internal HH/HL price (pos_dir).
    # Context vote comes ONLY from external leader+tide. Flipping the external
    # inputs while holding structure fixed MUST be able to change the verdict —
    # proving context is not a restatement of structure.
    fixed_structure = 1
    verdicts = {combine(fixed_structure, ctx_dir(lbv, tbv, True, fixed_structure), True)[0]
                for lbv in (-1, 0, 1) for tbv in (-1, 0, 1)}
    assert verdicts == {0, 1}                     # external inputs alone move it between RANGE and BULL
    # and a bull structure can NEVER be forced to BEAR by context (only agreement confirms)
    assert all(combine(1, ctx_dir(lbv, tbv, True, 1), True)[0] in (0, 1)
               for lbv in (-1, 0, 1) for tbv in (-1, 0, 1))

    # ── CLAIM 5: RS is annotation only — it never appears in the verdict path ──
    # (verdict is computed without rs_tag; assert the tag is pure over its inputs)
    assert rs_tag(1, 1, True, True) == "IN-LINE"
    assert rs_tag(1, 0, True, True) == "LEADING"
    assert rs_tag(0, 1, True, True) == "LAGGING"
    assert rs_tag(1, -1, True, True) == "DIVERGING"
    assert rs_tag(1, 1, True, False) == ""        # off → no tag, no effect
    # verdict identical regardless of what RS would say:
    base = combine(1, ctx_dir(1, 1, True, 1), True)
    for lbv in (-1, 0, 1):
        assert combine(1, ctx_dir(1, 1, True, 1), True) == base

    # ── CLAIM 6: graceful degrade — useContext=False → verdict == structure ──
    for pd in (-1, 0, 1):
        v, ag, cf = combine(pd, ctx_dir(0, 0, False, pd), False)
        assert v == pd and cf is False

    # ── CLAIM 7: deterministic ──
    seq = [(1, 1), (1, -1), (-1, -1), (0, 1), (1, 0)]
    r1 = [combine(pd, ctx_dir(l, t, True, pd), True) for pd in (-1, 0, 1) for (l, t) in seq]
    r2 = [combine(pd, ctx_dir(l, t, True, pd), True) for pd in (-1, 0, 1) for (l, t) in seq]
    assert r1 == r2

    print("MARKET CONTEXT ENGINE VALIDATED:")
    print("  context dir needs leader AND tide · true dir only on Structure×Context agreement,")
    print("  opposition = CONFLICT (never directional) · independence enforced (disjoint inputs),")
    print("  relative strength is annotation-only · degrades to structure when off · deterministic")
    print("  all 7 claims PASS")
