# v2.7 — Institutional Reference Lines + stable Power (cross-TF identity by design)

## Why

After Phase 1 (eviction) and Phase 2 (anchor Power pool), MORPHO still showed two
real problems: the Power Line **jumped over time** on one chart, and the **MTF
lines still differed** across timeframes. Root causes, confirmed by the fingerprint:

1. **Jumping:** the Power pick ranked anchors by distance to `dRef`, the *developing*
   daily close — which moves every tick, so the nearest anchor flipped intrabar.
2. **MTF differs:** the displayed lines came from the *detected pivot book*, which is
   inherently history-depth-dependent (each chart TF detects a different set). No
   eviction/anchoring trick removes this — it is what each chart *sees*.

The conclusion is structural: a level engine built on **per-chart pivot detection**
cannot be byte-identical across timeframes on TradingView. The fix is to stop
detecting the displayed levels per chart and **define** them.

## What changed

**1. Institutional Reference Lines (new default MTF display).** Every displayed level
is now a **fixed institutional reference** drawn at its current single-`request.security`
value — identical on every chart TF and every token by construction:

`PMH/PML, PWH/PWL, PDH/PDL` (prev-period extremes) + the last confirmed `Monthly /
Weekly / Daily` swings. Near-duplicates merge (a swing sitting on a prev-period
extreme → one clean line). Monthly drawn boldest.

**2. Detected swing book → off by default.** The per-chart auto-detected pivots
(the source of the cross-TF drift) now render only when "Also show detected swing
book" is enabled. The book still populates and scores internally (it feeds the
Power label's ICS and the fingerprint/freeze proof) — it is just not drawn by
default. Result: the chart shows only levels that are identical on every timeframe.

**3. Stable Power ranking.** The Power pick now ranks anchors by distance to
`pRefS` = the **prior confirmed Daily close** (`close[1]` on the Daily), which is
**fixed for the whole session**. The pick can no longer flip intrabar as price
wiggles — the jumping stops — while remaining identical on every chart TF (still a
single security value). The dwell/decisive-margin stability layer is unchanged.

## Determinism / safety

- Reference lines and the Power pick are **display/selection only**. No level
  identity, no DB/STRUCT hash input, no freeze-test input changes — the determinism
  proof is intact by construction.
- The detected book is unchanged internally (only its rendering is gated), so
  `f_bookScore`, the fingerprint, DB HASH and the freeze test still operate on it.

## Validation

| Check | Result |
|---|---|
| `pine_audit.py` (delimiters, decl-before-use of all new ids, arg-parity) | ✅ all files |
| `determinism_tests.py` | ✅ all pass |
| Reference lines are single-`security` values → identical on every chart TF | ✅ by construction |
| Power ranks against a session-fixed reference → no intraday flip | ✅ by construction |
| `f_scoreAndRender` still scores in PASS 1 when `drawOK=false` (book hidden) | ✅ verified |

## User verification (BUILD `v2.7-IRL`)

On MORPHO (and any token), across 1m / 15m / 1H / 4H / 1D:
- The **reference lines** (PMH/PWL/PDH/…) must sit at the **same prices** on every
  chart, and there should be **no jitter** between them.
- The **⚡ Power price** must be identical on every TF and **must not jump** as price
  moves within the session.
- Toggle "Also show detected swing book" only if you want the extra per-chart detail
  (expected to differ across TFs — that is the physical limit, now opt-in).
