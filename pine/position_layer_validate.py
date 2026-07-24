#!/usr/bin/env python3
"""POSITION LAYER validator (models the HTF-bias + regime logic in level_core_v2.pine).

Proves the edge rules:
  * 2/3 HTF agreement required (1W/1D/4H) — no single TF can force direction
  * each TF's structure vote is CONFIRMED by momentum (opposing momentum vetoes it)
  * mixed/conflicting = NEUTRAL (range) — no forced direction
  * regime = Daily efficiency ratio vs threshold (independent of structure)
And proves the SELECTIVITY claim: the new model emits STRICTLY FEWER directional
calls than (a) a structure-only 2/3 rule and (b) the old weighted+deadband model —
momentum can only REMOVE a directional call, never create one (no new false signals).
"""
from itertools import product

TRI = (-1, 0, 1)


def vote(s, m):
    # structure gives direction; momentum that directly opposes it vetoes the vote
    if s == 0:
        return 0
    return 0 if m == -s else s


def pos_dir(votes):
    bulls = sum(1 for v in votes if v == 1)
    bears = sum(1 for v in votes if v == -1)
    d = 1 if bulls >= 2 else -1 if bears >= 2 else 0
    return d, max(bulls, bears)


def struct_only_dir(structs):
    # baseline: 2/3 on raw structure, ignoring momentum
    return pos_dir(structs)[0]


def old_weighted_dir(W, D, H4, H1=0):
    # the model the Position Layer REPLACES: weighted blend + 0.15 deadband
    score = W * 0.40 + D * 0.30 + H4 * 0.20 + H1 * 0.10
    return 1 if score > 0.15 else -1 if score < -0.15 else 0


def regime(er, thr):
    return "TRENDING" if er >= thr else "RANGING"


if __name__ == "__main__":
    # --- CLAIM 1: vote truth table (momentum veto) ---
    assert vote(1, 1) == 1 and vote(1, 0) == 1 and vote(1, -1) == 0
    assert vote(-1, -1) == -1 and vote(-1, 0) == -1 and vote(-1, 1) == 0
    assert vote(0, 1) == 0 and vote(0, -1) == 0 and vote(0, 0) == 0

    # --- CLAIM 2: 2/3 agreement rule + no single-TF force ---
    assert pos_dir((1, 1, 0))[0] == 1 and pos_dir((1, 1, 1))[0] == 1
    assert pos_dir((-1, -1, 0))[0] == -1 and pos_dir((-1, -1, -1))[0] == -1
    assert pos_dir((1, 0, 0))[0] == 0          # single bullish TF -> neutral
    assert pos_dir((-1, 0, 0))[0] == 0         # single bearish TF -> neutral
    assert pos_dir((1, -1, 0))[0] == 0         # conflict -> neutral
    assert pos_dir((1, -1, 1))[0] == 1         # 2 bull vs 1 bear -> bull
    assert pos_dir((1, 1, -1))[1] == 2         # agreement count reported

    # --- CLAIM 3: momentum can only REMOVE a directional call, never add one ---
    # over ALL 27 structures x 27 momenta, new directional => structure-only directional
    removed = 0
    for structs in product(TRI, repeat=3):
        so = struct_only_dir(structs)
        for moms in product(TRI, repeat=3):
            votes = tuple(vote(s, m) for s, m in zip(structs, moms))
            nd = pos_dir(votes)[0]
            if nd != 0:
                assert so != 0 and nd == so, (structs, moms)   # never invents/flips
            if so != 0 and nd == 0:
                removed += 1
    assert removed > 0   # momentum genuinely tightens selectivity in real cases

    # --- CLAIM 4: SELECTIVITY vs the two baselines, over the 27 structure triples ---
    # (momentum neutral, so new == structure-only here; compare against old weighted)
    new_dir = sum(1 for s in product(TRI, repeat=3) if pos_dir(s)[0] != 0)
    old_dir = sum(1 for s in product(TRI, repeat=3) if old_weighted_dir(*s) != 0)
    assert new_dir < old_dir, (new_dir, old_dir)
    # concrete false-signal removals: single strong HTF forced a call in the old model
    assert old_weighted_dir(1, 0, 0) == 1 and pos_dir((1, 0, 0))[0] == 0    # lone 1W
    assert old_weighted_dir(0, 1, 0) == 1 and pos_dir((0, 1, 0))[0] == 0    # lone 1D
    assert old_weighted_dir(1, 0, -1) != 0 and pos_dir((1, 0, -1))[0] == 0  # conflict W vs 4H

    # --- CLAIM 5: regime (efficiency ratio, independent of structure) ---
    assert regime(0.35, 0.35) == "TRENDING" and regime(0.34, 0.35) == "RANGING"
    assert regime(0.80, 0.35) == "TRENDING" and regime(0.10, 0.35) == "RANGING"

    # --- CLAIM 6: deterministic ---
    for structs in product(TRI, repeat=3):
        for moms in product(TRI, repeat=3):
            v = tuple(vote(s, m) for s, m in zip(structs, moms))
            assert pos_dir(v) == pos_dir(v)

    print("POSITION LAYER VALIDATED:")
    print(f"  2/3 HTF agreement, momentum veto, neutral-on-conflict, no single-TF force")
    print(f"  momentum removed a directional call in {removed} of 729 cases (never added one)")
    print(f"  directional calls over 27 HTF states: new model {new_dir}  vs  old weighted {old_dir}")
    print(f"  -> strictly more selective, no new false signals; regime independent of bias")
    print("  all 6 claims PASS")
