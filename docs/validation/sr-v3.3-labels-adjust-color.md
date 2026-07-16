# v3.3 — On-line labels, Level Adjustment, position colouring (display layer)

The reference-level + Power architecture is **frozen** (per request #2). Everything
here is display-only or an opt-in refinement of the *drawn* position — no change to
level identity, selection, merge, ICS, or the deterministic cross-TF behaviour.

## 1 · Labels on the line, far right

Reference labels now sit **on top of the line** (`style_label_down`) pushed to the
**far right** (`labelOffset` bars past the last candle, default 3). Vertically-close
labels still stagger left so a cluster never overlaps. Combined with the v3.2 Label
Detail modes (Full / Compact / Price only / Off).

## 2 · Freeze

No edits to the anchor engine, the native un-clamped sourcing, the Power argmax, the
touch weighting, or the determinism proof. The Power selection still runs on the raw
levels.

## 3 · Level Adjustment module (`levelAdjust`, default None)

Refines only **where a line is painted**. Options:

- **None** — raw level (default; nothing moves).
- **Nearest Round Number** — snap to the nearest `10^floor(log10 price)/10` step.
- **Nearest Psychological Level** — snap to the coarser `…/2` step (the .00/.50 grid).
- **Highest Touch Level** — within `adjATRWin` native-Daily-ATR of the raw level,
  snap to the price with the greatest historical **test density** (native period
  extremes, the same chart-independent source as the touch weighting).

**Determinism guarantee:** `f_adjust(rawPrice, nativeDailyATR)` is a pure function of
chart-independent inputs, so the snapped value is identical on every chart TF. The
engine still *selects/scores/merges on the raw price* — only the draw and the label's
displayed price use the snap. `None` (default) is exact v3.2 behaviour.

Applied to the reference lines and the Power line (Power selection stays raw).

## 4 · Colour by price position

`colorByPos` (default on): every line **above** current price is red, every line
**below** is green — regardless of its type — on the reference lines, the detected
book, and their labels. Off → colour by type (resistance red / support green).

## Validation

| Check | Result |
|---|---|
| `pine_audit.py` | ✅ all files |
| `determinism_tests.py` (incl. adjustment purity) | ✅ all pass |
| adjust is a pure function of raw price → same drawn level on every TF | ✅ |
| `None` mode returns the raw level unchanged (freeze default) | ✅ |
| identity / selection / DB hash / freeze inputs changed | ❌ none |

## User test plan (per request #3)

Try **Level Adjustment** on crypto, forex and indices across all timeframes. Keep it
only where the snapped levels visibly improve market respect **and** the Power price
stays identical across TFs (it will — the snap is deterministic). If a mode doesn't
help on a given market, leave it on `None`.
