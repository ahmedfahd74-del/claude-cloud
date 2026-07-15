# Phase 2 — Power Line on fixed institutional anchors (2026-07-15)

## Why (evidence)

Phase 1 (chart-independent age + pure-recency eviction) made the book identical
where history is **deep** (BTC: Power = 65086.0 on 5m/1H/4H/1D). But on a **thin /
newer token** (MORPHO) the fingerprint showed the books still diverge across chart
TFs — e.g. Monthly live = 20 on the 4H chart vs 13 on the 1D chart, Daily hashes
40597203 / 41523579 / 45459371 on 30m / 4H / 1D — and the Power Line drifted
(2.0117 / 2.0135 / 2.0153).

Root cause, confirmed by evidence: on thin data the book **never overflows**
MAXBOOK, so eviction never runs and the chart-dependent **seed snapshot** (what
`request.security` had accumulated at the seed bar, which differs by chart TF)
persists. No eviction rule can fix that — the divergence is in what each chart
*detects*, not in what it keeps. A Power Line derived from that book inherits the
drift.

## The fix

The Power Line's candidate pool no longer comes from the pivot book. It is now a
**fixed set of institutional anchors**, each a single `request.security` value:

- Prev-period extremes: **PDH/PDL, PWH/PWL, PMH/PML** (`pHi*/pLo*`).
- Last-confirmed HTF swings: Daily / Weekly / Monthly (`ph*/pl*`).

Every one of these is **byte-identical on every chart TF** — they need only 1–2
prior HTF bars, which even a 1m chart loads. Selection is unchanged in spirit:
`rank = proximity(to dRef) × TF-importance² × trend-side`, all chart-independent.
The stability layer (dwell / decisive-margin) and the label are unchanged. The
label's ICS is looked up from the book near the chosen anchor (`f_bookScore`) —
**display only**; it is chart-influenced and never used to select. The **price is
guaranteed identical** across all chart TFs, thin token or not, by construction.

This decouples the Power decision from the depth-sensitive book entirely — exactly
the "fixed institutional anchors" option approved for the phased plan.

## What this does and does not fix

- **Power Line** — now cross-TF identical **by construction**, including on thin
  tokens. ✅
- **MTF book display** — the *detected* pivot book still differs on thin tokens
  (physical: each chart detects a different set). The anchors themselves render
  identically; the surrounding swing-pivot lines can still differ on thin symbols.
  A later step can promote the fixed anchors to the primary MTF reference lines if
  full book identity on thin tokens is required.

## Validation

| Check | Result |
|---|---|
| `pine_audit.py` (delimiters, decl-before-use incl. `f_bookScore`/`aPx`/`aW`/`aRs`) | ✅ all files |
| `determinism_tests.py` | ✅ all pass |
| fixed-anchor Power: pick is a pure function of (anchors, dRef) — book-independent | ✅ |
| fixed-anchor Power: order-independent across the anchor set | ✅ |
| anchors are single `request.security` values → identical on every chart TF | ✅ by construction |
| identity / DB hash / freeze inputs changed | ❌ none (selection + label only) |

## Next — user verification

Reload (BUILD now **`v2.6-ANCH`**). On MORPHO (and any thin token), the ⚡ Power
price must now be **identical on 1m / 15m / 30m / 1H / 4H / 1D**. The fingerprint
book rows may still differ on thin tokens (expected); the Power **price** must not.
