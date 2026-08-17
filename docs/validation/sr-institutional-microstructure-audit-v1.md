# S/R Engine — Institutional Market-Microstructure Audit (v1 · 2026-07-12)

Benchmarks the S/R engine (`sr_engine.pine`, with the `setup_engine.pine`
liquidity map where relevant) against professional market-microstructure and
auction-theory principles — **not** retail "draw a line at the high" concepts, and
**not** any proprietary bank levels (unknowable). The question is only: *does the
engine reason the way the literature says price is actually formed?*

**Reference frame**
- **Harris, _Trading and Exchanges_** — order types, where limit/stop liquidity
  actually rests, tick structure, why clustering happens.
- **O'Hara, _Market Microstructure Theory_** — information asymmetry, price
  discovery, adverse selection; a level matters when information is revealed there.
- **Dalton, _Mind Over Markets_ / _Markets in Profile_** — auction market theory:
  value area, POC, TPO, initial balance, excess, responsive vs initiative,
  single prints. This is the framework the engine is **furthest** from.
- **Weis, _Trades About to Happen_** — Wyckoff / VSA: effort vs result, springs,
  upthrusts, volume at the turn.
- **Murphy, _Technical Analysis of the Financial Markets_** — classic S/R,
  role reversal, significance by number/recency of reactions, MTF.

---

## 1 · The Institutional Confidence Score (ICS 0–100) — rubric

A level's ICS is the weighted sum of ten criteria, weighted by how much each
drives *real* order flow in the literature. This is the score the engine **should**
compute per level (see §4); today's 0–100 score is a *different, narrower* blend
(§3) and should not be read as an ICS.

| # | Criterion | Pts | Anchored in | What earns the points |
|---|---|---:|---|---|
| 1 | Significant market structure | 12 | Murphy | Level is a confirmed swing / BOS-CHoCH pivot / range boundary, not noise |
| 2 | Institutional liquidity | 15 | Harris, O'Hara | Sits where stops/limits cluster: prior H/L, equal highs/lows, session extremes, round numbers |
| 3 | Auction market behavior | 15 | Dalton | Coincides with POC / value-area edge / single-print / excess tail / initial-balance extreme |
| 4 | Multiple historical reactions | 12 | Murphy | ≥2 independent touches with rejection; touch **mass**, not raw count |
| 5 | Rejection / effort-vs-result quality | 12 | Weis, O'Hara | Strong wick rejection **and** volume/effort disproportionate to price result (absorption) |
| 6 | Multi-timeframe confluence | 12 | Murphy | HTF agreement within an ATR-native band |
| 7 | ATR-appropriate zone sizing | 6 | Harris (tick/vol) | Zone width scales with the level's own-TF ATR; not fixed points |
| 8 | Continued validity (mitigation) | 8 | Wyckoff/SMC | Not fully mitigated/consumed; freshness decays; polarity flips on break |
| 9 | Explainable, deterministic logic | 4 | (engineering) | Same inputs → same level; reason codes emitted |
| 10 | Non-repainting | 4 | (engineering) | Confirmed-bar only; no look-ahead |

**Acceptance thresholds:** ≥ 75 institutional-grade (tradeable reference) · 60–74
watch · < 60 reject/decorative.

---

## 2 · Per-level-CLASS audit (the engine builds classes, not a fixed list)

Individual live levels can only be scored at runtime (see §4); here each **source
class** the engine emits is scored on how well the *class* satisfies the rubric.

| Level class | Source | ICS (class) | Verdict |
|---|---|---:|---|
| **Prior day/week H-L (PDH/PDL/PWH/PWL)** | prev-period extremes | **78** | ✅ Grade. Harris: stops cluster just beyond these; O'Hara: reference for overnight information. Deterministic, non-repaint. Loses points on auction (no volume context) and initial single reaction. |
| **Equal highs / lows (EQH/EQL)** | `f_hasEqual` | **74** | ⚠ Near-grade. Textbook engineered-liquidity pool (Harris stop-clustering). Strong liquidity + structure; docked for no auction context and tolerance sensitivity (`eqTol`). |
| **Swing pivots (per-TF book)** | `f_swing` + 8-factor score | **66** | ⚠ Watch. Good structure/confluence/reaction, but a swing high is only *sometimes* an auction reference; no volume-profile confirmation. Over-relies on price memory (Murphy) without Dalton's value context. |
| **Session highs/lows** | `f_sess` | **68** | ⚠ Watch. Real intraday liquidity (Harris). Docked: no volume, session-definition dependence, weaker on 24h crypto. |
| **Swing BSL/SSL (nearest unbroken external)** | swing liquidity | **70** | ⚠ Watch. Legitimate liquidity target; needs a sweep/displacement confirmation to grade up. |
| **FVG / Order Block footprints** | SMC bonus | **58** | ❌ Below. Most-recent-only, full-fill mitigation only, no breaker/mitigation state; adds a score *bonus* rather than standing as a validated level. |

**Weighted engine posture ≈ 68/100** — a **strong price-structure + liquidity**
engine that is **materially incomplete on auction market behavior (Dalton)** and
**shallow on effort-vs-result (Weis)**. It is above retail, below a desk that
reasons in value/volume.

---

## 3 · How today's 0–100 score maps to the rubric (and where it misleads)

Current factor weights and their ICS mapping:

| Engine factor | Wt | ICS criterion | Assessment |
|---|---:|---|---|
| Confluence (`W_CONF`) | .24 | #6 MTF | ✅ Strong, now TF-native/deterministic |
| Touch gravity (`W_TOUCH`) | .16 | #4 reactions | ✅ Better than raw count (prox×rejection×momentum) |
| Reaction (`W_REACT`) | .16 | #5 rejection | ⚠ Wick-based; **no effort-vs-result** (Weis) |
| Freshness (`W_FRESH`) | .10 | #8 validity | ✅ Wall-clock-invariant decay |
| Sweep (`W_SWEEP`) | .10 | #2 liquidity | ✅ Sweep+reject; good smart-money proxy |
| SMC (`W_SMC`) | .10 | #2 liquidity | ⚠ EQH/EQL good; OB/FVG minimal |
| Trend (`W_TREND`) | .08 | #1 structure | ⚠ Alignment only, not structural rank |
| Volume (`W_VOL`) | .06 | #5/#2 | ⚠ Raw rel-volume; unreliable on FX |

**The misleading part:** the current score has **0 weight on auction behavior
(#3)** and treats a swing pivot as fully institutional on confluence alone. Two
levels can score 80% here yet one sits on the day's POC (institutionally decisive)
and the other in a low-volume single-print void (a liquidity vacuum, not support).
The score cannot tell them apart — the single biggest quality gap.

---

## 4 · Recommendations (ranked; stability-gated per ADR-001)

**R1 — Add an auction layer (largest ICS gap, Dalton).** Build a volume/TPO
profile over a rolling window (session + visible range): derive **POC, VAH/VAL,
single prints, excess tails, initial balance**. Emit these as first-class levels
and add criterion #3 to scoring. This is what separates "a line at a high" from a
value-based reference. *Feasible on TV via `ta`/arrays without extra security.*

**R2 — Effort-vs-result at the level (Weis).** At each touch, compare volume
(effort) to price progress (result): high effort + small result beyond the level =
absorption → grade up; low effort rejection = weaker. Replace/augment `W_REACT`.

**R3 — Compute and display the real ICS.** Add the §1 rubric as the engine's
per-level score (label it ICS), keeping the current blend available for
continuity. Levels < 60 draw faint/decorative; ≥ 75 solid. This directly answers
"produce an Institutional Confidence Score, explain why, recommend improvements" —
per level, at runtime, with reason codes.

**R4 — Liquidity classification (Harris).** Tag each level's liquidity *type*
(resting stops vs limit, engineered EQH/EQL vs natural, round-number) and weight
#2 by type, rather than a single sweep flag.

**R5 — Mitigation state (#8).** Track partial vs full mitigation for FVG/OB and
"consumed" liquidity after a sweep, so continued-validity is graded, not binary.

**R6 — Structural rank (#1).** Distinguish internal vs external swings and
range-boundary extremes (the engine already protects extremes in eviction — expose
that as a structure score, not just trend alignment).

**Sequencing:** R1 and R3 give the biggest institutional-quality lift and are the
natural next increment now that determinism is solid (Max-Levels leak fixed,
freeze/hash in place). Each ships behind the FREEZE/HASH instrument and the
`determinism_tests` harness; any that destabilizes levels or repaints is paused
(ADR-001). R2/R4/R5/R6 follow.

---

## 5 · Scorecard summary

| Institutional criterion | Engine today | Target |
|---|---:|---:|
| Market structure | 8/12 | 11 |
| Institutional liquidity | 11/15 | 13 |
| **Auction behavior** | **2/15** | **12** |
| Multiple reactions | 10/12 | 11 |
| Rejection / effort-result | 7/12 | 11 |
| MTF confluence | 11/12 | 11 |
| ATR zone sizing | 5/6 | 6 |
| Continued validity | 5/8 | 7 |
| Deterministic logic | 4/4 | 4 |
| Non-repainting | 4/4 | 4 |
| **Total (ICS posture)** | **≈ 67/100** | **≈ 90** |

The determinism and non-repaint criteria are now genuinely met (this session's
fixes). The path from 67 → 90 is almost entirely **auction behavior + effort/result
+ real per-level ICS** — R1–R3. Nothing here requires matching hidden bank levels;
it requires reasoning in **value and liquidity**, which the references define and
the engine can compute deterministically.
