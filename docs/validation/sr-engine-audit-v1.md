# Institutional Support & Resistance Engine — Complete Audit (v1 · 2026-07-12)

**Scope.** The S/R engine as shipped in `pine/sr_engine.pine` (v2.1.1, 1971 lines
— the full institutional build), with the determinism proof-of-concept
`pine/sr_poc.pine` ("IA-SR · MTF Determinism POC") audited as the stability
substrate. Legacy/superseded variants (`sr_fusion.pine`, `sr_db_engine.pine`)
are noted only where they differ; they are not the maintained engine.

**Method.** Static inspection of every section, concept-presence grep sweeps,
`request.security`/`lookahead` scans, and structural review of the scoring,
determinism and trade-validation math. **Nothing is assumed correct.** Runtime
TradingView behaviour (hash equality across TFs, RE-code limits) is the user's to
confirm on-chart; where I could only reason statically I say so. **Per the
governing instruction, this is a report only — the S/R engine is NOT rewritten.**

Every claim below cites `file:line`.

---

## 1 · Market Logic Validation

| Element | Status | Evidence / verdict |
|---|---|---|
| **Swing detection** | ✅ Solid | `f_swing` (`sr_engine.pine:332-345`): custom series-length fractal — bar `leg` back is a swing if it is the extreme of the `[0..2·leg]` window; confirmed `leg` bars after it prints (no future data). Fixed loop bound `2·MAXLEG=28` ⇒ constant cost. **Identity is always the wick extreme** and the anchor toggle never enters detection (`:331`). Non-repaint. |
| **Market structure (HH/HL/LH/LL)** | ⚠ Coarse | No maintained swing *sequence* per timeframe. There is no HH/HL/LH/LL state machine; structure is inferred indirectly from the level book. |
| **BOS** | ⚠ 1H-only | `bosUp/bosDn` (`:1215-1216`) are computed from a **single held 1H swing** (`lastPhH1`/`lastPlH1`) — not per-timeframe, and only the most-recent swing. A real BOS needs the prior *structural* swing of each TF; here it is one 1H high/low. |
| **CHoCH** | ⚠ Derived | `chochUp/chochDn` (`:1217-1218`) = a 1H BOS *against* the HTF trend. Reasonable heuristic, but inherits the 1H-only limitation and has no distinct MSS concept. |
| **MSS (market-structure shift)** | ❌ Absent | Not modelled separately from BOS/CHoCH. |
| **Liquidity sweeps** | ✅ / ⚠ | Two detectors. Per-level (`f_touchUpdate:753-755`): wick pierces level **and close rejects** — correct sweep semantics, debounced 3 bars. Decision-engine (`:1176-1178`): wick `> mWick` ATR near S/R — **no displacement requirement**, so a large indecision wick near a level can flag as a sweep. Sweep *lines* anchor at the wick extreme and clear on a confirmed close-through (mitigation) (`:1186-1212`). |
| **Inducement** | ❌ Absent | Grep: 0. No inducement/liquidity-trap modelling (sweep of a minor pool before the real move). A named institutional gap. |
| **Order blocks** | ⚠ Minimal | `:814-830`: only the **most-recent OB per side** is held (`obBullTop/Bot`, `obBearTop/Bot`), gated by displacement `body1 > atrSafe·1.2`. No set of unmitigated OBs, no refresh/mitigation state, no FVG-refined OB. Feeds `f_smcBonus` (0.7) and the probability engine. |
| **Breaker blocks** | ❌ Absent | Grep: 0. Broken *levels* flip polarity (`:689-692`), but there is no breaker-block concept on order blocks. |
| **Mitigation blocks** | ❌ Absent | Grep: 0. |
| **Fair Value Gaps** | ✅ Solid | `:765-812`: 3-bar imbalance on confirmed bars, tracked until filled, capped at 30, bull/bear typed, optional draw. Feeds `f_smcBonus` (0.6). Limitation: fill is **full-fill only** (`low≤bot` / `high≥top`, `:803`) — no 50%/CE partial-mitigation state. |
| **Volume analysis** | ⚠ Light | `volRatio` vs SMA20 (`:254-255`), used in touch gravity (`:749`) and scoring (`W_VOL=0.06`, `:868`). Raw volume with no range-proxy fallback here (the setup engine had one) — unreliable on spot-FX symbols. Deliberately low weight. |
| **MTF confluence** | ✅ Strongest factor | `f_nearCount` across the six other TF books, weighted by TF importance, `W_CONF=0.24` (heaviest) (`:904`, `:866`). Design is correct — HTF agreement dominates. **Caveat (see §4-Stability):** the confluence band mixes chart-bar `atrSafe` and the per-bar `adMergeMult` (`:893-894`), so the *confluence contribution to score* is chart-TF-dependent even though level *identity* is not. |

**Verdict.** The primitives it does implement (swings, FVG, sweeps-with-rejection,
polarity flip, MTF confluence) are correctly, non-repaintingly built. The named
absences — **inducement, breaker blocks, mitigation blocks, MSS, multi-OB
tracking, per-TF structure sequence** — are what separate this from a full ICT/SMC
liquidity engine. It is an institutional *level* engine, not yet a full *orderflow*
engine.

## 2 · Level Quality

- **Touch gravity** (`f_touchUpdate:730-756`) is the standout mechanic: every
  interaction adds weighted mass = proximity × (1 + ½·rejection) × momentum,
  debounced 3 bars — near-misses count partially, rejections outweigh mere
  touches. This is materially better than a raw touch count.
- **8-factor confidence score** (`f_scoreAndRender:896-918`): touch, reaction,
  confluence, trend-alignment, volume, freshness (time decay), sweep, SMC
  footprint — normalised (`f_norm01`), TF-weighted (`0.6+0.4·w`), and penalised by
  break quality (`:917`). Graded A+/A/B/C/D. **Scoring never mutates price/identity**
  (two-pass: score, then render) — a genuine, well-enforced invariant (`:887-890`).
- **Eviction** (`f_addLevel:608-644`) protects the structural extremes (highest/
  lowest unbroken level) and evicts broken-first then lowest-score — not FIFO.
  Proven levels persist. Good.
- ⚠ **Uncalibrated constants.** ~8 factor weights plus every `f_norm01` k-scale
  are hand-set with **no out-of-sample calibration**. The engine *does* ship a live
  calibration panel (predicted vs realised win-rate by bucket, `:1474-1492`,
  `:1578-1582`) — excellent instrumentation — but it is observational, not a
  validation. Overfitting surface is real and unmeasured.

## 3 · Zone Construction

- Level zones (`:590`, `:940-943`) are **symmetric** bands `± max(atrSafe,
  atrTF·0.5)·zoneWidthK·zoneScale` around the wick. Off by default.
- ⚠ This is a cosmetic band, **not a true supply/demand zone**: no proximal/distal
  edge, no open-to-wick body, no orderblock-derived boundaries. FVG and OB zones
  are drawn separately (`:789`, `:823/830`) and are the real institutional zones.
- **Verdict:** adequate for an S/R *line* product; not a zone/orderflow product.

## 4 · Multi-Timeframe Validation (Monthly → M5)

- **7 timeframes** (MN/W/D/4H/1H/15/5) each compute their **own** regime → own
  adaptive leg → own swings *inside* `request.security` (`f_htfPack:359-393`,
  `:395-401`) — true per-TF independence, 7 pack calls + a few extras, **11 total
  `request.security`**, well under budget.
- **Prev-period extremes** (PDH/PDL, PWH/PWL, …) committed as first-class levels
  from the 2nd bar of each TF (`:1066-1089`) — the exact prices institutions defend,
  available before any swing confirms.
- **Population-vs-display split** (`:967-990`) is the cross-TF-parity architecture:
  a book is *populated* whenever its TF ≥ chart TF (so `request.security` reads it
  reliably), and the source toggles / `htfOnly` are display-only. Sub-chart phantom
  sampling is correctly excluded.
- **Seeding** retries through the first 50 bars until HTF pivot arrays deliver
  (`:1013-1034`) — fixes missing W/D levels on 1m/5m charts.
- **Verdict:** ✅ this is the most genuinely institutional part of the engine. MN is
  opt-in; M15/M5 down-weighted by `ltfNoise`.

## 5 · Institutional Behaviour

| Concept | Status | Evidence |
|---|---|---|
| Polarity flip (broken S↔R) | ✅ | `:689-692`, optional flip markers `:693-699`. |
| Equal highs/lows (EQH/EQL) | ✅ | `f_sameSideNear:846-853`, feeds SMC score. |
| PDH/PDL/PWH/PWL pools | ✅ | prev-period extremes as levels `:1066-1089`. |
| **Premium / discount** | ❌ Absent | Grep: 0. No equilibrium (range-50%) framework — a core ICT gate is missing. |
| **Killzones / sessions** | ❌ Absent | Grep: 0. No Asia/London/NY session liquidity, no killzone timing. |
| Session H/L pools | ❌ Absent | Only period extremes, not session extremes. |
| Displacement | ⚠ Partial | Used for OBs (`:816`) but not required by the decision-engine sweep. |

## 6 · Trade Validation

- **Full gate** (`:1706-1718`): direction ∧ quality ∧ probability ∧ HTF-align ∧
  S/R-confidence ∧ structure ∧ levels ∧ R:R ∧ entry-proximity. Never forces a trade.
- **3-tier output** (`:1731-1737`): A = execute (all hard gates), B = watch
  (weighted gate-score ≥ 55), C = ignore. Borderline setups surface as WATCH rather
  than vanishing — good product behaviour.
- **Entry** = nearest opposing structure; **stop** = beyond the next level, ATR-
  buffered and **bounded to [⅓·m .. 2·m] ATR** (`:1685-1691`) — no micro-risk, no
  stale far-stop. **Targets** = next levels in direction with ATR-expansion fallback
  (`:1692-1700`). **Position %** from account-risk ÷ stop-distance (`:1705`).
- **Journal post-mortem** (`:1783-1851`): simulates the real limit-order lifecycle
  (fill window 40 bars → conservative stop-before-target race → timeout), yielding a
  live plan win-rate. Non-repaint (confirmed bars only).
- ⚠ **No entry trigger.** Entry is a resting level, not a swept-and-displaced
  trigger (the sibling `setup_engine.pine` has the IDLE→SWEPT→TRIGGERED machine;
  this engine does not). The plan is a *limit idea*, validated by the fill window —
  acceptable as a plan, but it is not an entry-timing engine.
- ✅ **Honest scanner** (`:1932-1957`): explicitly reports that the full stateful
  engine cannot run for foreign symbols/TFs (nested `request.security` prohibited)
  rather than substituting fake logic. Rare integrity.

## 7 · Stress Testing & Determinism (Stability)

- **Non-repaint:** all HTF reads are `lookahead_off` (**7×, 0× `lookahead_on`**);
  every stat mutation is gated on `barstate.isconfirmed` (`:674`, `:751`, `:1190`,
  `:1742`, `:1783`). Confirmed-bar-only construction ⇒ no intrabar repaint. ✅
- **TF-native identity:** merge radius and break buffer use **only** the level's own
  TF ATR (`:571`, `:669`) — a level's existence and broken-state are identical on
  every chart. ✅
- ⚠ **Scores are NOT cross-TF-invariant, by design.** Confluence band and the
  per-bar `adMergeMult`/`atrSafe` feed the score (`:893-894`), so the same level can
  read e.g. 57% on 5m and 64% on 1h. The Power Line had to be redesigned around a
  **±15% score tolerance** (`:1290-1303`) precisely to stop it "jumping" between
  charts. Identities are deterministic; **scores and anything gated on them are
  not.** This is the single most important stability finding.
- ⚠ **No in-engine hash/freeze proof.** `sr_engine.pine` has no determinism
  self-test. That proof lives in **`sr_poc.pine`**: an append-only union DB with a
  commutative (order-independent) hash and an A=B=C freeze/replay test — reported
  passing on 1D (`17343419 ×3`, 530 levels, per the POC plan). **Open issue:** the
  POC currently throws **RE10110 (40s timeout) on 15m** because ingestion re-scans
  the whole ~530-level union linearly per level per bar (`f_find`, O(N) inside the
  per-bar ingest). A tracked O(1) index-map fix is planned (`plans/hi-delegated-pike.md`)
  — **not yet applied, and correctly deferred behind this audit.**

## 8 · Performance

- `sr_engine.pine`: cost is **bounded** — 7 stores × `MAXBOOK=20` levels; the
  heaviest per-bar work is `f_scoreAndRender` pass-1 (`f_nearCount ×6` per level ≈
  6·20·20 per store) plus `f_nearest`/`f_gather`/`f_powerPick` over ~140 levels.
  Bounded by the cap, so it does not blow the 40s limit even on deep history. Draw
  budgets: 200 lines / 200 labels / 250 boxes.
- `sr_poc.pine`: **open RE10110 on 15m** (see §7). This is a pure performance
  problem on the POC — its deterministic *result* is correct.

## 9 · Final S/R Report — Scored

Scores are institutional (capital-weighted): what a desk would require before
trusting the component, not a generous self-grade.

| Dimension | Score | One-line justification |
|---|---:|---|
| **Institutional Quality** | **68 / 100** | Excellent MTF, touch-gravity, confluence, polarity flip, FVG, sweeps-with-rejection, live calibration. Missing inducement, breaker/mitigation blocks, MSS, multi-OB tracking, premium/discount, killzones. |
| **Accuracy** | **72 / 100** | Non-repaint verified; wick-identity; sound RR/stop math; honest scanner. Deductions: BOS/CHoCH from a single 1H swing; decision-sweep lacks displacement; scoring weights never out-of-sample validated. |
| **Robustness** | **70 / 100** | Adaptive across assets/regimes (vol/regime/liquidity/noise), ATR-normalised, na-safe, seeding retries, extreme-protecting eviction. Deductions: ~30 uncalibrated constants (overfitting surface), raw volume on FX. |
| **Stability** | **62 / 100** | Identity/merge/break are TF-native & non-repaint (strong). But scores/confluence/Power-Line are chart-TF-dependent by design (needed a ±15% tolerance); no in-engine hash proof; the POC that *does* prove DB determinism currently errors on 15m. |
| **Performance** | **66 / 100** | Main engine bounded and within budget; the determinism POC has an open 15m RE10110 (fix planned, not applied). |
| **Overall S/R readiness** | **≈ 67 / 100** | A strong, honest institutional *level* engine with a proven-deterministic identity layer, held back by a non-invariant scoring layer and missing SMC liquidity primitives. |

## 10 · Prioritised remediation (report only — do NOT rewrite yet)

**S-tier (stability / capital-trust, do first):**
1. **Make score cross-TF-invariant** — drive the confluence band and freshness
   decay from TF-native ATR only (as merge/break already are), removing chart-bar
   `atrSafe`/`adMergeMult` from `f_scoreAndRender`. Then the Power Line no longer
   needs its ±15% fudge and a hash can cover scores, not just identities.
2. **Land the `sr_poc.pine` RE10110 fix** (O(1) index map) so the determinism proof
   passes on 15m as well as 1D — then port the append-only-union + freeze test into
   `sr_engine.pine` so the production engine is hash-provable, not just the POC.

**A-tier (institutional completeness):**
3. Per-TF market-structure sequence (HH/HL/LH/LL) so BOS/CHoCH/MSS are real and
   per-timeframe, not a single held 1H swing.
4. Multi-OB tracking with mitigation state; add breaker & mitigation blocks.
5. Inducement detection (minor-pool sweep before displacement).
6. Premium/discount equilibrium gate; killzone/session liquidity.

**B-tier (validation):**
7. Out-of-sample + cross-market calibration of the scoring weights (retire the
   overfitting risk the live calibration panel can only *observe*).

**Do NOT rewrite the S/R engine until the above is sequenced and each change is
proven with the hash/freeze harness — the audit stands; remediation is the next,
separate step.**

---

*Cross-reference: system-wide readiness and the platform-side risk/governance
remediation are tracked in `institutional-audit-v1.md`. This document is the
deep-dive on the S/R engine specifically, per the S/R audit instruction.*
