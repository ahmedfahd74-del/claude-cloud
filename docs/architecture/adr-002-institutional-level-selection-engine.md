# ADR-002 · Institutional Level Selection Engine (ILSE)

**Status:** Proposed (design) · **Date:** 2026-07-12 · Supersedes the ad-hoc
display path in `f_scoreAndRender` + the Chart-Clarity governor by consolidating
them into one explicit, evidence-first pipeline.

## Context

The engine draws too many marginal levels; quality/selection logic is spread
across scoring (`f_scoreAndRender` PASS 1), the Chart-Clarity governor (PASS 2 +
registry), and the Power Line (`f_powerPick`). The user wants a single, explainable
**selection engine**: score every candidate on real institutional merit, let
candidates compete, cluster + prune, and render only levels that earn their place —
with the single highest-confidence level as the Power Line. Determinism,
non-repaint, and full validation are hard constraints.

**On the referenced TradingView script:** we take **architecture only** — five
generic patterns below — and copy **no** code, formula, weight, or parameter. All
scoring and thresholds come from our own framework (ADR-001 + the microstructure
audit). We explicitly **discard** the retail/cosmetic ideas the user named:
harmonic grids, phase alignment, XYZ shading, resonance damping, adaptive-gain and
recursive-filter marketing, fake-AI inputs, and any decorative/unused parameters.
None of these will appear in ILSE.

### Borrowed patterns → our realization

| Generic pattern (architecture) | Our realization |
|---|---|
| Candidate-level competition | Every detected level is a candidate; it competes for a display slot by **ICS**, not by recency or draw-order |
| Intelligent clustering | ATR-**native** cluster distance (own-TF ATR, chart-independent) — already the merge/CONF/clarity basis |
| Minimum separation | A hard min-separation (× Daily-ATR) between *shown* levels; closer ones merge to the strongest |
| Dynamic pruning | Levels below an ICS floor, fully mitigated, or dominated by a stronger neighbour are pruned before render |
| Evidence-based ranking before rendering | Rank by ICS (with a proximity relevance term) *then* draw — never draw-then-hide |

## Decision — the ILSE pipeline

A single deterministic pass, all **display/selection** (never mutates the level
book, its frozen identities, or the STRUCT/DB hash — so the freeze/hash instrument
still proves determinism):

```
1 DETECT      existing candidate sources (swings, PDH/PDL/PWH/PWL, EQH/EQL, sessions)
2 SCORE (ICS) real Institutional Confidence Score per candidate (below)
3 COMPETE     all candidates ranked by ICS × proximity-relevance
4 CLUSTER     group candidates within min-separation (ATR-native), HTF-first
5 MERGE/PRUNE keep the highest-ICS representative per cluster; drop ICS<floor,
              fully-mitigated, or dominated levels
6 SELECT      take the top-K survivors (K = display budget)
7 POWER       the single highest-ICS survivor (chart-independent) = Power Line
8 RENDER      draw only survivors; each carries its ICS + reason codes
```

Stages 3–8 already exist in nascent form (Chart-Clarity governor + `f_powerPick`);
ILSE makes them **explicit, ICS-driven, and ordered**, and replaces the current
8-factor display score with the ICS in stage 2.

## The Institutional Confidence Score (ICS 0–100)

Per the microstructure audit rubric (Harris, O'Hara, Dalton, Weis, Murphy), each
factor **deterministic and chart-native where possible**:

| Factor | Pts | Source in engine | Status |
|---|--:|---|---|
| Structural significance | 12 | external/range-boundary swing, BOS/CHoCH origin | extend (expose structure rank) |
| Institutional liquidity | 15 | PDH/PDL/PWH/PWL, EQH/EQL, round numbers | mostly present |
| **Auction behavior** | 15 | POC / VAH-VAL / single-print / excess | **new (R1) — needs volume/TPO** |
| Multiple reactions | 12 | touch **mass** (prox×rejection×momentum) | present |
| Reaction / effort-vs-result | 12 | rejection wick **+** volume-vs-progress | extend (Weis effort/result) |
| MTF confluence | 12 | TF-native `f_nearCount` | present (deterministic) |
| Freshness | 6 | wall-clock-invariant decay | present |
| Mitigation state | 8 | broken/polarity-flip; partial-fill for FVG/OB | extend |
| Statistical evidence | 4 | hold-rate / calibration of the level class | extend (reuse self-review) |
| Deterministic + non-repaint | 4 | confirmed-bar, frozen identity, lookahead_off | met |

ICS is the number shown on each level and on the Power Line (answering the audit's
R3). The current touch/confluence score becomes the *statistical-evidence* and
*confluence* inputs, not the whole score.

## Determinism & non-repaint plan (hard constraints)

- ILSE is **selection/display only**: it reads the frozen level book and ICS; it
  never moves, creates, or deletes a stored identity. The **DB/STRUCT hash and the
  freeze test are therefore unchanged** — the existing instrument keeps proving
  determinism after each increment.
- **ICS must be as chart-independent as the inputs allow.** Confluence, liquidity,
  structural and mitigation factors are TF-native/security-derived (chart-
  independent). Touch/reaction factors accrue on chart bars and stay chart-
  *influenced* — documented honestly; the Power Line selection already excludes the
  chart-dependent parts (ADR-note: it ranks on Daily-close proximity + TF-weight).
- All state (mitigation, competition) updated on **confirmed bars only**;
  registries cleared per bar. No `request.security` beyond the existing budget.

## Validation (every increment)

Each increment ships behind: `pine_audit.py` (structural), `determinism_tests.py`
(property models — cluster min-separation, prune monotonicity, ICS ordering, Power
= argmax ICS, chart-independence), the on-chart **FREEZE/HASH** instrument
(unchanged ⇒ book untouched), and a repaint/leak scan. No increment merges if it
moves the hash or trips the freeze test.

## Staging (stability-first)

- **I1 — ICS core + reason codes.** Assemble the ICS from existing factors
  (structure, liquidity, confluence, touch, freshness, mitigation, evidence);
  show it on levels + Power Line. No auction yet. *Biggest explainability win, low
  risk — reuses present signals.*
- **I2 — Consolidate selection into the ILSE pipeline.** Fold Chart-Clarity +
  `f_powerPick` into the explicit compete→cluster→merge/prune→select→power order,
  driven by ICS.
- **I3 — Auction layer (R1).** Volume/TPO → POC/VAH-VAL/single-print/excess as the
  auction factor + first-class levels. Highest institutional lift; gated hardest.
- **I4 — Effort-vs-result (Weis) + mitigation depth (partial fills).**

## Trade-offs

- Shipping ICS + pipeline *before* the auction layer means the ICS is initially
  auction-blind (the audit's known gap). Accepted: I1/I2 are low-risk and deliver
  the cleaner, explainable chart now; I3 adds the missing dimension on a stable base.
- Consolidating three code paths into one is a larger diff than a point fix, so it
  is split I1→I2 and each is hash-verified, rather than one big rewrite.

## Non-goals / discarded (explicit)

Harmonic grids · phase alignment · XYZ shading · resonance damping · adaptive-gain
placeholders · recursive-filter marketing · fake-AI inputs · decorative/unused
parameters. ILSE adds **no** parameter that isn't consumed by a scored, explainable
decision.
