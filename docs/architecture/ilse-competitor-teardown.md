# Architectural Teardown — "Horizontal Red Line" TV indicator (2026-07-12)

Read for **architecture only**. No code, formula, weight, parameter, or threshold
is copied. This documents *why its (enabled) S/R core would render cleanly*, what is
**deceptive/decorative and discarded**, and which **generic patterns** we adopt into
ILSE (ADR-002), redesigned in our own framework.

## 0 · Headline: it is an obfuscated decoy

The script is engineered to *look* sophisticated while hiding/disabling its real
engine:

- **The S/R engine never renders by default.** `showZones = (not xyzShading) and
  (vn_window == 3755)`. `xyzShading` defaults **true**, so `showZones` is **false** —
  and even with it off, it demands `vn_window == 3755` exactly. The entire
  zone-drawing block is gated behind this. What actually draws is a single red line
  at `close * 0.99` (the "Horizontal Red Line").
- **Three whole input groups are fake.** "Signal Processing" (Adaptive/Classic/
  Hybrid/Recursive filter, adaptive gain, recursion depth), "Harmonic Confluence"
  (0.618 grid, bands, XYZ shading, phase alignment, resonance damping), and
  "Volatility Normalization" (Sigma/Range/Kalman/MAD, Kalman gain, recalibration)
  feed **nothing** — they are summed into `_decoy` and `plot(_decoy, display=none)`
  purely so Pine doesn't flag them unused. Zero effect on output.

**Lesson, not a feature:** these are exactly the concepts you told me to discard.
Confirmed — none enter ILSE. The "cleaner look" is not from DSP/harmonics/AI; it is
from the plain selection architecture underneath.

## 1 · Why the REAL core (if enabled) renders cleanly

Stripping the decoys, the genuine engine is ~5 ideas — all things we already
planned in ADR-002, which is a good cross-check:

| Real mechanism | Effect on clarity |
|---|---|
| **Detection-time consolidation** — a new pivot within a cluster distance of an existing level folds INTO it (and bumps a pivot-count) instead of spawning a new level | Fewer candidates from the start |
| **Score-ranked greedy selection** — score every candidate, then repeatedly take the highest-scoring unused one | Strongest-first competition, not draw-order |
| **Hard minimum separation** — a candidate closer than a separation distance to an already-selected level is rejected | No overlapping/stacked zones |
| **Evidence pruning** — min-retests gate, "strong only" gate, stale-lookback removal, idle score decay | Weak/dead levels never drawn |
| **Global cap + uniform ATR height** — at most N zones, all one ATR-scaled height | Bounded, tidy output |

That is the whole reason it looks clean: **aggressive consolidation → strict
competition with min-separation → evidence pruning → bounded top-K.** No magic.

## 2 · Two genuinely useful ideas we adopt (redesigned)

Most of the above we already have (clarity governor cluster/prune, relevance
select, freshness decay). Two are worth folding into the **ICS**, redesigned:

1. **Outcome-based reaction quality (bounce vs break).** The core classifies each
   interaction: did price *enter and exit the same side* (a **bounce** — level
   respected) or *enter one side and exit the other* (a **break** — level failed)?
   A running **respect-rate** = bounces / (bounces + breaks). This is a real,
   deterministic, non-repainting reaction-quality signal, stronger than our
   current wick-only reaction. **We adopt the concept** (outcome win-rate as an ICS
   *reaction/statistical-evidence* factor), computed on confirmed bars only, with
   our own detection — not their `close[2]` heuristic or weights.

2. **Pivot-count as confluence evidence.** Repeated pivots at the same level are
   counted as accumulating evidence. **We adopt the count**, but **NOT** their
   running-average that *moves* the level toward each new pivot — moving a level's
   price repaints its identity and breaks our frozen-identity / freeze-hash
   invariant. Ours: identity stays frozen (the wick extreme); repeats add evidence
   only. This is a determinism *upgrade* over their approach.

Plus one selection refinement for ILSE: a **global top-K + min-separation** select
(they cap total zones; our current cap is per-timeframe). ILSE stage 6 gets a
global budget with min-separation, so total on-chart lines are bounded regardless
of how many timeframes are on.

## 3 · Where our engine is already stronger (keep ours)

| Dimension | Their core | Ours |
|---|---|---|
| Level identity | running-average → **moves/repaints** | **frozen** wick extreme (deterministic) |
| Timeframe | single (chart only) | true MTF (security), TF-native ATR |
| Cross-TF consistency | none | TF-native confluence, Daily-close Power anchor |
| Determinism proof | none | append-only hash + A=B=C freeze test |
| Freshness | bar-count decay (chart-TF dependent) | wall-clock-invariant decay |
| Liquidity model | retests only | PDH/PDL/PWH/PWL, EQH/EQL, sweeps (pierce+reclaim) |
| Auction behavior | none | planned (ILSE I3: POC/VAH-VAL) |

## 4 · Net effect on ADR-002

The teardown **validates the ILSE pipeline** (compete → cluster → min-sep →
prune → top-K → power → render) and adds two concrete ICS inputs and one selection
refinement, all redesigned in our framework:

- ICS **reaction quality** ← bounce/break **respect-rate** (new factor input).
- ICS **statistical evidence** ← frozen-identity **pivot/touch count** (no averaging).
- ILSE **stage 6** ← **global** top-K with min-separation (was per-timeframe).

No parameter, weight, threshold, or decorative concept from the source is carried
over. These fold into I1 (ICS core) and I2 (pipeline consolidation) of ADR-002.
