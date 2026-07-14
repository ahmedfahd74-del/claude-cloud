# ILSE I2 — Power Decision Engine + reason codes (2026-07-12)

Second ADR-002 increment. Reframes the Power Line as the **output of a Power
Decision**, makes that decision **stable** (resistant to unnecessary switching),
and adds **per-level reason codes** so every drawn level justifies itself. All
display/decision only — the level book, identities and STRUCT/DB hash are
untouched, so the freeze/hash instrument keeps proving determinism.

## Power Decision Engine

The engine continuously re-evaluates every Daily+ candidate each bar
(`f_powerDecision`); the drawn ⚡ line is only the **committed output**. The old
per-bar re-pick (with a rank-bonus hysteresis) is replaced by an explicit
**stability decision**:

> A challenger replaces the current Power Decision **only** if — it is the first
> pick, OR the committed level has disappeared (broken/removed), OR the challenger
> **decisively out-ranks** the incumbent now (`rawRank > incumbentRank ×
> POWER_MARGIN`, 1.5), OR the **same challenger has led for `powerDwell` confirmed
> bars** (default 5, user input). Otherwise it **holds**.

This is exactly the user's rule: *don't switch just because a new candidate scores
one point higher.* A one-bar blip cannot move the line; a genuine, sustained or
decisive shift does. The incumbent's live rank is measured in the same scan
(`heldRank`) so the margin test is real, not approximate. Selection stays
chart-independent (Daily-close proximity × TF-weight), so the line remains the same
across timeframes; the stability layer only governs *when* it switches.

**Validated** (`determinism_tests.py`): a 1-bar marginal challenger never switches
(no flicker); a challenger leading `dwell` bars switches exactly at the dwell bar
(not before); a decisive challenger switches immediately; a vanished committed
level is replaced at once; deterministic.

## Per-level reason codes

Every displayed level now carries a compact justification built from its own ICS
factors (each shown only when it clears a meaningful threshold), stored in a new
frozen-identity `Store.why` field (display only, not hashed):

`EXT` range-boundary extreme · `MTF` multi-timeframe confluence · `LIQ`
institutional liquidity · `RESP` respect-rate (bounce>break) · `TCH` repeated
touches · `BRK` partially broken (warning).

Label now reads: `A  R  2.053  ICS 78  · EXT MTF LIQ`. A level with **no** qualifying
evidence yields an empty code — a signal it does not deserve the chart (pruned by
the clarity/ICS budget). **Validated:** strong extreme+MTF+liquidity → the full
code; a broken level carries `BRK`; a no-evidence level → empty.

## Pipeline status (ADR-002)

`detect → ICS (I1) → compete/relevance → cluster/min-sep (Chart Clarity) →
prune → select top-K → **Power Decision (I2)** → render (+reason codes, I2)`.

The pieces now exist and are ICS-driven; a later pass can fold the Chart-Clarity
governor and the Power Decision behind a single named `f_ilse()` entry point, but
functionally the pipeline is complete and stable.

## Determinism / non-repaint

- `f_powerDecision` and all stability state update on **confirmed bars only**;
  `Store.why` is set in PASS 1 from existing factors and read in PASS 2 — no
  identity, line position, or hash input changes.
- The new `Store.why` array is kept in lockstep with every other per-level array
  (unshift on add, remove on evict), preserving the frozen-identity invariant.

## Verification summary

| Check | Result |
|---|---|
| `pine_audit.py` (delimiters, decl-before-use of 5 new ids, no dangling `pwrHold`/`f_powerPick`/`POWER_HOLD`, Store arg-parity) | ✅ all files |
| `determinism_tests.py` | ✅ 58/58 |
| Power Decision: no-flicker / dwell-switch / decisive / held-gone / deterministic | ✅ |
| Reason codes: full / BRK / empty | ✅ |
| No repaint / future leak (confirmed-bar state, lookahead_off) | ✅ |
| Book / STRUCT+DB hash unchanged | ✅ by construction |

On-chart gate: the ⚡ line stops flickering between near-equal levels (tune with
"Power Decision: dwell bars"); each level label shows its reason codes; DB HASH /
Freeze read unchanged. **Next: I3 — auction layer (volume/TPO → POC/VAH-VAL)** fills
the held-at-0 ICS factor, now on a stable, explainable selection framework.
