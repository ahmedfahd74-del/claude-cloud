# ILSE I1 — Institutional Confidence Score (ICS) core (2026-07-12)

First increment of ADR-002. The per-level display score **is now the ICS** — a
0–100 institutional confidence built from real factors, shown on every level and
the Power Line. It lives in `s.score`, which is **not** part of the STRUCT/DB hash,
so replacing the old flat blend changes **no identity** and leaves the freeze/hash
determinism proof intact.

## The ICS (our framework — no source weights copied)

`ICS = 100 · Σ wᵢ·fᵢ · (0.7 + 0.3·TF-weight)`, factors each in 0..1, weights sum to 1:

| Factor | w | Signal (deterministic, from existing stats) | Reference |
|---|--:|---|---|
| Structural significance | .14 | range boundary (store's highest/lowest unbroken = external extreme) → 1.0, interior → 0.5 | Murphy |
| Institutional liquidity | .16 | `0.6·sweep + 0.7·SMC/EQ` footprint | Harris/O'Hara |
| Reaction quality | .16 | **respect-rate** `t/(t+1.5·breakMass)` (bounce-vs-break, our frozen-identity take on the teardown idea) + wick rejection + volume | Weis |
| Multiple reactions | .12 | touch **mass** (prox×rejection×momentum) | Murphy |
| MTF confluence | .18 | TF-native `f_nearCount` (chart-independent) | Murphy |
| Freshness | .08 | wall-clock-invariant decay | — |
| Mitigation integrity | .08 | `1 − 0.2·breakMass` (partially broken = less intact) | Wyckoff/SMC |
| Trend alignment | .08 | HTF-aligned side | — |
| **Auction behavior** | **.00** | held at 0 — **I3** adds volume/TPO (POC/VAH-VAL) | Dalton |

The label now reads `A  R  2.053  ICS 78` (grade · side · price · ICS); the Power
Line reads `⚡ POWER 2.053 · S · ICS 57 · 0.4 ATR · BEAR · RESPECT`.

## Two teardown ideas, redesigned (not copied)

- **Respect-rate (bounce vs break)** → the reaction-quality factor, from the level's
  own touch mass vs break-quality mass. Deterministic, confirmed-bar.
- **Repeat evidence** → carried by touch mass with the identity **frozen** — we do
  **not** average-move the level toward new pivots (that would repaint identity and
  break the freeze hash). This is a determinism upgrade over the source.

## Validation (`determinism_tests.py` — 49/49 PASS)

- weights sum to 1.0 (auction held at 0);
- ICS bounded 0..100 (20k random);
- **monotonic non-decreasing in every factor** (5k random) — more evidence never
  lowers the score;
- respect-rate strictly falls as break mass rises; a never-broken level = 1.0;
- a range-boundary extreme outscores an interior level, all else equal;
- higher-timeframe level outranks a lower-TF one at equal evidence;
- deterministic. `pine_audit.py` PASS (no dangling `W_*`, delimiters, decl-before-use).

## Determinism / non-repaint (unchanged, by construction)

ICS is computed in PASS 1 from existing per-level stats and stored in `s.score`; it
touches no identity, no line position, no hash input. Confluence is TF-native;
touch/reaction remain chart-*influenced* (documented). The **Power Line selection
is unchanged** — still chart-independent (Daily-close proximity + TF-weight); the
ICS is shown on its label as evidence, not used to reselect (that stays consistent
across timeframes). Making Power = argmax(chart-independent ICS subset) is I2.

## Next (ADR-002)

- **I2** — consolidate Chart-Clarity + `f_powerPick` into the explicit ILSE
  pipeline (compete → cluster → merge/prune → **global** top-K + min-sep → power →
  render), Power = argmax of the chart-independent ICS subset, per-factor reason
  codes in the dashboard.
- **I3** — auction layer (volume/TPO → POC/VAH-VAL) fills the held-0 factor.
- **I4** — effort-vs-result depth + partial mitigation state.
