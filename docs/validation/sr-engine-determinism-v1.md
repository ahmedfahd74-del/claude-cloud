# Production Engine Determinism — Increment 1 Validation (2026-07-12)

Implements ADR-001: the determinism **hash + freeze/replay** instrument now lives
**inside `sr_engine.pine`** (the single source of truth), as a read-only layer.
No existing institutional feature was modified. Institutional roadmap features
(MSS, multi-OB, breaker/mitigation, inducement, premium/discount, session/killzone)
are intentionally **not** in this increment — stability-first, per the directive.

## What shipped

1. **Append-only identity log** (`detKey/detSide/detTfC/detBirth`, ints only,
   rolling-capped at 4000) fed from `f_addLevel`'s creation branch — captures the
   engine's real level identities with **no `request.security` replay**.
2. **Section 17** — three instruments over the log:
   - **DB HASH** (all identities), **HTF HASH** (≥4H, cross-TF-comparable),
     both commutative → order-independent.
   - **FREEZE A/B/C** sampled at three **confirmed** bars (`last−1/−501/−1001`),
     with a **retention guard** so a rolling-cap roll-off reports "raise cap /
     lower window" instead of a misleading FAIL. A FAIL now means only a genuine
     repaint.
   - HUD in the unused `middle_left` corner (`showDetHUD`, default on).

## Verification matrix (as required)

| Requirement | How verified | Result |
|---|---|---|
| **Deterministic outputs** | Commutative hash order-independence (200× shuffles); freeze A==B==C at realistic rate | ✅ model PASS |
| **Stable level identity** | Log is append-only, prices frozen on creation; genuine-repaint test flips FREEZE to FAIL | ✅ PASS (repaint caught) |
| **Stable scoring** | No scoring code touched this increment; score path unchanged | ✅ unchanged |
| **Stable confluence** | TF-native `CONF_BAND_K` (prior increment) invariant across 5000 chart contexts | ✅ PASS |
| **No repainting** | 17 `barstate.isconfirmed/islast` gates; freeze sampled on confirmed bars; append-only log never rewrites history | ✅ verified |
| **No future data leakage** | 7× `lookahead_off`, 0× `lookahead_on`; no negative/forward offsets in new code | ✅ verified |
| **Runtime performance** | O(log) hash scans gated to the 4 bars where read (last + 3 anchors); logger is O(1) push | ✅ negligible added cost |
| **Memory usage** | Log is 4 int arrays ≤ 4000 each (~tiny); no lines/labels/boxes; no in-security book | ✅ bounded |
| **TradingView execution limits** | No `request.security` replay added (the POC's RE10139/RE10110 source); read-only draw of one 2×6 table | ✅ avoided by design |

Harnesses: `scratchpad/pine_audit.py` (structural — delimiters, decl-before-use of
all 14 new identifiers, no dangling refs) and `scratchpad/determinism_tests.py`
(**15/15 PASS**), including the three-way discrimination:
- realistic rate → **PASS** (retained & A==B==C);
- log roll-off → **retention guard fires** (honest "raise cap", not a false FAIL);
- injected repaint of an old frozen identity → **FAIL** correctly flagged.

## Key design decisions (full rationale in ADR-001)

- **Hash the append-only log, not the evicted display book** → the DB/HTF hash is
  immune to the chart-dependent `MAXBOOK` eviction, closing a cross-TF identity
  leak *without changing eviction*.
- **Confirmed-bar freeze sampling** → fixes the POC's 1h realtime-freeze artifact.
- **Retention guard** → a rolling cap can't silently invalidate the freeze test;
  the instrument now distinguishes "capacity limit" from "repaint."
- **Read-only / additive** → cannot destabilise any existing feature (stability
  priority honoured).

## Honest scope boundary

This delivers **identity determinism + non-repaint + a live proof on the real
engine**. Scores remain chart-influenced (touch mass accrues on chart bars); full
cross-TF score parity would need the in-`request.security` architecture we are
deliberately leaving. The HTF HASH is the cross-TF-comparable metric; the FREEZE
test is a same-chart non-repaint proof.

## On-chart gate (user)

Load `sr_engine.pine`. Expect: DETERMINISM HUD (middle-left) shows a stable **DB
HASH**; **HTF HASH matches** across 5m/15m/1h/4h on the same symbol; **FREEZE test
PASS** on charts with ≥ `detWindow`+ bars (or "raise cap / lower window" if the log
is too small on a very busy LTF — raise `DET_LOGCAP` or lower the freeze window);
and **every existing panel/plan/alert is unchanged**. Report the HUD values if
anything reads FAIL and I'll diagnose.

## Next increments (staged, stability-gated)

Per ADR-001, institutional features resume only after the core is confirmed green
on-chart, each regression-checked against this FREEZE/HASH instrument, in roughly
this order: improved market structure (per-TF HH/HL/LH/LL) → MSS → multi-OB +
breaker/mitigation → inducement → premium/discount → session/killzone → liquidity
classification. Any feature that trips FREEZE/HASH or adds repaint/runtime is
paused.
