#!/usr/bin/env python3
"""STATE-ENGINE CONSISTENCY CHECK.

Proves the market-state CLASSIFICATION TREE in ms_core.pine's f_state is byte-identical
(comment- and blank-stripped, indentation preserved) to the one in level_core_v2.pine's
f_state — so with matching inputs the MS-Core panel and the Level Core Position Layer can
never disagree. Guards against silent drift when either file is edited.

The compared region is from the first `_hh = not na(_h1)` line (structure classification,
which is identical across both) through the final `_st := 0` (end of the decision tree).
The pivot-source lines above it differ only by the swing-size input name (mtfSwing vs
entryBiasSw) and are intentionally excluded.
"""
import re
import sys

START = "_hh = not na(_h1)"
END = "_st := 0"


def strip_comment(line):
    # no string literals occur in the compared region, so a plain // split is safe
    return line.split("//", 1)[0].rstrip()


def extract_tree(path):
    lines = open(path).read().split("\n")
    start = next(i for i, l in enumerate(lines) if START in l)
    end = max(i for i, l in enumerate(lines) if END in l)
    out = []
    for l in lines[start:end + 1]:
        s = strip_comment(l)
        if s.strip():
            out.append(s)          # keep leading indentation, drop trailing/comment/blank
    return out


if __name__ == "__main__":
    a = extract_tree("level_core_v2.pine")
    b = extract_tree("ms_core.pine")
    if a != b:
        print("STATE-ENGINE DRIFT DETECTED — the two f_state trees differ:")
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print(f"  line {i}: level_core: {x!r}")
                print(f"           ms_core:    {y!r}")
        if len(a) != len(b):
            print(f"  length differs: level_core {len(a)} vs ms_core {len(b)}")
        sys.exit(1)
    print("STATE-ENGINE CONSISTENCY VERIFIED:")
    print(f"  ms_core.pine f_state tree == level_core_v2.pine f_state tree "
          f"({len(a)} lines, identical)")
    print("  the MS-Core panel and the Position Layer share one classification engine —")
    print("  with matching Bias Swing / momentum / efficiency inputs they cannot disagree")
