# v3.1 — Touch / test weighting for the Power Line (chart-independent)

## Goal

A level that price has tested many times — repeatedly making it a high or low —
deserves more Power. Add that "more touches = more strength" weighting **without
breaking** the cross-TF determinism achieved in v3.0.

## The determinism trap (and how it's avoided)

Naive touch-counting is chart-timeframe-dependent: a 1m chart sees ~100× more
candle touches than a 1D chart, so counting touches on chart bars would instantly
re-introduce cross-TF divergence. Instead, touches are counted from a **native,
un-clamped source**: the last N period extremes per timeframe
(`high[k]`/`low[k]` for D×8, W×6, M×4), fetched via lightweight **indexed history
refs** — no array accumulation over full history, no ATR/EMA/swing — so a sub-chart
request cannot trigger RE10110, and the extreme set is **identical on every chart
TF**. The test count is therefore a pure function of `(level, native extreme set,
band)`, none of which depend on the chart timeframe.

## Definition

`f_touchCount(level, band)` = weighted count of recent D/W/M highs & lows within
`band` (native Daily ATR × `touchBandK`, default 0.25) of the level — Weekly ×1.3,
Monthly ×1.6 (a bigger-timeframe test is a stronger test). A level that has been a
period extreme many times scores high; a fresh, once-touched level scores ~1.

The Power rank gains a multiplier: `rank = prox × tfw² × sideW × (1 + infl ·
min(touches/4, 1.5))` — `powerTouchInfl` default 0.6 (a well-tested level earns up
to ~1.9×). Because `touches` is chart-independent, the boosted rank — and thus the
winner — stays identical on every chart TF.

## Safety / reversibility

- **Toggle `powerTouchOn` (default on).** Off → `tchMul = 1` → **exact v3.0
  selection**. `powerTouchInfl = 0` does the same. So the feature can never
  permanently "wreck" the Power Line — it is one click from the proven state.
- Selection + display only: no level identity, DB/STRUCT hash, or freeze input
  changes. The book, reference lines and cross-TF anchor set are untouched.
- The `tch` column in the Power Decision Trace shows each candidate's test count;
  the ⚡ label shows the winner's `TCH n`.

## Validation

| Check | Result |
|---|---|
| `pine_audit.py` | ✅ all files |
| `determinism_tests.py` | ✅ all pass |
| touch count is chart-independent (same level+extremes → same count) | ✅ |
| a repeatedly-tested level outscores a lightly-tested one | ✅ |
| touch boost monotonic non-decreasing in count | ✅ |
| identity / DB hash / freeze inputs changed | ❌ none |

## User verification (BUILD `v3.1-TCH`)

The ⚡ Power price must **still be identical on 1m / 15m / 1H / 4H / 1D / 1W**
(determinism preserved), now with a `TCH n` count on the label and a `tch` column
in the trace. A heavily-tested level should now win over a merely-close one. Toggle
"Weight Power by touches / tests" off to confirm it returns to exact v3.0 behaviour.
