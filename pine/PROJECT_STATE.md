# PROJECT STATE — Institutional S/R + Market-Structure Engine

> **Read this FIRST every session.** Single source of truth for the Pine work.
> Branch: `claude/institutional-sr-pine-script-4gab3r` · all Pine lives in `pine/`.
> User trades **crypto** (SOL, PEPE, ETH, ZEC, BTC) + indices; validates on TradingView
> (I cannot compile Pine — every "compile" is the user's one paste). Project rule:
> `PAPER_TRADING_ONLY=true`. Discipline: **build one module at a time, validate, freeze
> before the next. No patching. Verify every build 3 ways (structural + logic + determinism).**

## FREEZE CANDIDATES (the only 2 active files)
| File | Role |
|---|---|
| `pine/level_core_v2.pine` | The S/R engine ("Level Core") — levels, memory, scoring, merge, appearance, nudge |
| `pine/ms_core.pine` | MS-Core market-structure **bias panel** (separate indicator) |

Everything else in `pine/` is **legacy / not part of this freeze** (institutional_sr_ics.pine,
sr_engine.pine, sr_poc.pine, level_core.pine (v1), setup_engine.pine, sr_fusion.pine, etc.).

## LEVEL CORE v2 — architecture (frozen intent)
- Levels sourced from **fixed degrees 1H / 4H / 1D / 1W** via `request.security` — NOT chart
  candles → same level shows same price on **every chart TF**. Only degrees ≥ chart TF are active.
- **Immutable anchors** (born once from a confirmed pivot, never drift).
- Every interaction appended to a per-level **event log** (touch/held/break/retest + measured
  rejQ + sweep flag). **Every displayed stat is a reduction over that log** — nothing estimated.
- **Closed-bar only** detection (no repaint). Book stays centred on price (evicts furthest when full).
- **LIVE** = nearest level above + below price (always shown, emphasised).
- Modules done + validated: M1 event-sourced core · M1.1 cross-TF multi-degree · M2 confidence
  scoring + explainable audit · M3 confluence merge (renders as **classic red/green lines**, not zones).
- **Scoring:** `conf = clamp(raw·degW·100)`, `raw` = weighted blend of win-rate, rejection,
  displacement, sweep, separation(anti-cluster), evidence; `degW` = per-degree/TF weight
  (1W 1.0 · 1D .85 · 4H .70 · 1H .55). raw,degW ∈ [0,1] ⇒ clamp never fires ⇒ audit reconciles exactly.
- **Audit (hover ★ levels):** calc order = 1 interactions (real qualified count, ≥sepNorm bars apart,
  NOT round(nEv·sepF)) · 2 decay · 3 rejection · 4 displacement · 5 sweep · 6 win · 7 separation ·
  8 evidence · subtotal · 9 timeframe (own signed pts, = subtotal·(degW−1)) · 10 FINAL CONF.
  subtotal + tfPts ≡ CONF (proven; only a ≤0.5pt *display* rounding optic remains).
- **Input groups:** Detection · Degrees · Confidence Scoring · Appearance—Lines ·
  Appearance—Active Zone · Appearance—Labels · Confluence Merge · Manual Nudge (LIVE floor/ceiling).
- **Manual Nudge:** presentation-only % shift of the LIVE floor/ceiling line+label+zone; true anchor,
  memory, score, detection all unchanged.
- **CROSS-TF DETERMINISM FIX (root cause, user-approved edit to Module 1):** the book used to differ per
  chart TF because four things were measured against the CHART, not the level's own degree. All four are
  now TF-invariant: (1) `f_found` eviction distance uses `refPx` (fastest available HTF close 1H→4H→1D→1W)
  not chart `close`; (2) `f_audit` decay uses `(nowRef − ev.t)/f_degMs(deg)` (degree-bars) not
  `bar_index − ev.bar`; (3) `f_separation` and (4) `f_qualified` spacing use event timestamps `.t` in
  degree-bars not `.bar`. `nowRef` = 1H-aligned epoch ms. Result: membership + confidence + star rank are
  byte-identical on 1m/5m/15m/1H (proven by `parity_audit.py` before/after). `decayBars`/`sepNorm` now mean
  the level's OWN degree-bars. `ev.bar` is retained but no longer read by any scoring reduction.
- **REACH FIX (the real "levels missing on 1m/5m" cause, distinct from the above):** the book was
  ACCUMULATED over CHART bars, so a low TF only created the HTF pivots inside its own bar-window
  (1m≈3.5d, 5m≈17d, 15m≈52d, 1h≈208d) — older 4H/1D levels never appeared on 1m/5m. Fix: anchors are now
  sourced INSIDE each degree's own context — `f_degAnchors()` (dedup accumulator via `f_pushUniq`) is run
  through `request.security(<deg>, …, lookahead_off)` returning `array<float>` `aVals1/4/D/W`; `f_seed`
  feeds them into `f_found` on the chart. Driven by the degree's OWN history → the complete set appears on
  every chart TF. Proven by `reach_audit.py` (OLD 1m=2/5m=6/15m=9/1h=19; NEW 19 on every TF). **Known
  follow-up:** event COUNT/CONF are still tallied by chart-side `f_interact`, so older levels read lower ev
  on very low TFs — the LINES + distances (the engine's job) are complete/identical; HTF-sourcing the event
  log is the next step. (array-return-from-security COMPILES + RUNS — confirmed on chart.)
- **RE10110 PERF FIX (Sentinel baseline candidate):** the first HTF-sourced build seeded every bar
  (O(bars×anchors×book) ≈ 240M → 20s timeout). Now: (1) `f_seedFrom` seeds each anchor ONCE (append-only
  index), (2) eviction removed — book holds the full distinct set (safety cap 480), (3) render draws only
  the `maxLvls` nearest `close` (`distThr`, computed once on the last bar). Detection/scoring untouched;
  membership still TF-invariant (identical book + same last-bar price → same nearest set). `refPx`/eviction
  retired. All validators PASS.

## MS-CORE v1.1 — independent market-structure panel (freeze candidate)
- **REVERTED to v1.1 (independent) on user's call** after the v1.2 state-engine upgrade "didn't look
  right" on the live SOL weekly: with no 2/3 directional agreement, the system verdict was set by the
  LOWEST HTF's DISTRIBUTION/ACCUMULATION state (a lone 4H ACCUM → "ACCUMULATION ▲" on a weekly that had
  just made a lower high + broke down). Aggregation flaw = lowest-TF D/A dominates the verdict. User
  prefers the simple, independent structure read here; Level Core's Position Layer remains the decision
  authority (they may now diverge — accepted). MS-Core = the structure PICTURE, not the decision.
- Dashboard rows (1W/1D/4H/1H **+ Chart**) read the **HH/HL/LH/LL sequence classifier** `f_structPrev`
  via `request.security([1] + lookahead_on)` = last CLOSED bar. Bias: **HH+HL = BULL · LH+LL = BEAR ·
  conflicting = MIXED**. Not candle direction, not EMAs, no momentum/volatility.
- Two swing sizes decoupled: `Bias Swing Size` (mtfSwing) drives all bias rows incl. Chart; `Label Swing
  Size` (swL) drives HH/HL/LH/LL labels + BOS/CHoCH visuals only — never bias.
- BOS/CHoCH protected-swing drawing engine is separate and untouched.
- NOTE for any future re-attempt: fix the D/A aggregation (only surface DISTRIBUTION/ACCUMULATION from the
  DOMINANT/highest HTF, never from a lone lower TF) before re-porting the state engine.

## VALIDATORS (Python models of the Pine logic — run before every freeze)
`pine/level_core_validate.py` (detection 5 props) · `pine/level_core_v2_score_validate.py` (scoring) ·
`pine/level_core_v2_merge_validate.py` (merge) · `pine/parity_audit.py` (cross-TF determinism: OLD
diverges, FIXED byte-identical on 1m/5m/15m/1H). All currently PASS.
NOTE: these validate the LOGIC, not compiled Pine — the real compile check is the user's paste.

## ADVERSARIAL REVIEW (last run) — verdict per question
1 Reconciliation PASS (clamp can't fire; ≤0.5pt display rounding only) · 2 Qualified count PASS
(no cluster double-count) · 3 HTF/LTF states PASS (may disagree = correct; each row matches own labels)
· 4 Insufficient pivots PASS (→ MIXED / "—") · 5 Tests PARTIAL (logic solid; compile risk remains).
**Recommended: FREEZE (conditional on user's clean compile of both files).**

## M4 — ENTRY ENGINE (liquidity-first) — v3 BUILT + LOGIC-VALIDATED, **NOT frozen**
- Lives inside `level_core_v2.pine`, group "Entry Engine (liquidity-first) — M4". Read-only over the
  frozen book — no detection/scoring changes (all prior validators re-run and pass). **Module 1 untouched.**
- **Pipeline (v3)**: HTF bias → target a STRONG level in the right location → QUALIFIED sweep →
  internal BOS/CHoCH break → entry toward opposing liquidity.
- **Bias**: sequence classifier (HH+HL/LH+LL) on W/D/4H/1H closed bars, weights .40/.30/.20/.10,
  deadband ±0.15 → +1/−1/0. **MIXED = no signals.** Input `entryBiasSw` (default 5). *(unchanged from v2)*
- **Execution-TF guard**: engine idle above `maxExecTF` (default "5" = 5m). Execution is 1m–5m only.
- **Arm gates (v3, logged if failed, never silent), in order**: (1) **ATR sweep depth** — wick must
  pierce the level by ≥ `minSweepATR`(0.25)×ATR(`atrLen`14); kills micro-pokes. (2) **premium/discount
  location** (`useLocFilter`, range `locLookback`50) — SHORT only if swept level ≥ range-mid (premium),
  LONG only if ≤ mid (discount); blocks longs at range highs. (3) **level strength** = f_conf +
  conflBonus×neighbours-in-merge-band ≥ `entryMinCnf`(40). (4) **sweep-bar rejection quality**
  (short (high−close)/range; long mirror) ≥ `rejMin`(0.5).
- **Confirmation (v3 = REAL internal BOS/CHoCH, replaced the LTF LH/HL pivot sequence)**: a global
  internal-structure tracker keeps the last confirmed internal swing hi/lo (pivots of size `internalPiv`=3)
  and fires a **one-shot** break flag when a CLOSE crosses one; classifies CHoCH (flips internal trend)
  vs BOS (continuation). SHORT confirms on `brokeLoNow` after the sweep bar; LONG on `brokeHiNow`.
  Within `seqWindow`(20). Resets logged: bias flip · window expiry · close beyond sweep extreme.
- **Signal**: label "sweep → internal CHoCH/BOS <level>", stop = sweep wick, **target = opposing
  liquidity** (`f_oppLiq`: nearest opposing level with strength ≥ entryMinCnf = draw on liquidity;
  fallback = range extreme = the SSL/BSL pool), R:R; entry/stop/target lines; cooldown `coolBars`(10).
  Alerts "M4 LONG/SHORT (liquidity-first)".
- **Rejected-setups log**: rolling 30 with timestamps + reasons; panel row REJECTED (count) — hover = full log.
  Panel (bottom-right): ENTRY BIAS(score) / STATE (SWEPT await break, bars left) / SIGNALS / REJECTED.
- Validator: `pine/level_core_v2_entry_validate.py` — 13 scenarios (full short & long pipelines, ATR-depth
  gate, location gate, strength gate, rejection gate, expiry, invalidation, bias flip, MIXED, exec-TF guard,
  no-repaint, opposing-liquidity target, determinism) PASS.
- **Freeze blockers**: user compile + forward-test on 1m/5m crypto (fires only on real swept setups now?);
  tune minSweepATR / useLocFilter / entryMinCnf / rejMin / internalPiv / seqWindow from observation.
  Backtest before real money.

## LAYERED DECISION SYSTEM (target architecture — approved)
Top-down authorization, bottom-up execution. Higher layer grants permission + direction;
lower layer only refines timing/price. A signal is valid only when all active layers agree;
a lower layer can NEVER create or override higher-layer bias.
- **POSITION LAYER** (BUILT — see below): HTF market-state engine (TREND/PULLBACK/TRANSITION/
  DISTRIBUTION/ACCUMULATION/RANGE) → bias derived from state, 2/3 HTF agreement confirms.
- **INTRADAY LAYER** (next): AOI/liquidity setup validation → setup-quality score, SL from
  invalidation, TP from opposing liquidity, break&retest. Gates execution.
- **EXECUTION LAYER** = M4 v3 (built), now bias-free — consumes Position bias only. Next: optional
  EMA50 reaction filter, wire the setup-quality gate. Timing only: sweep→internal BOS/CHoCH→entry.

## POSITION LAYER — HTF MARKET-STATE ENGINE — BUILT + VALIDATED, **NOT frozen**
- Lives in `level_core_v2.pine`, group "Position Layer (HTF bias + regime)". Module 1 untouched.
- **Market STATE per HTF (1W/1D/4H)** — `f_state` classifies one of six from HH/HL/LH/LL progression
  (last two highs/lows), swing expansion (broadening vs contracting), momentum (price vs EMA `posMomLen`),
  and volatility (Kaufman efficiency ratio, `erLen`):
  **0 RANGE · 1 TRENDING · 2 PULLBACK · 3 TRANSITION · 4 DISTRIBUTION · 5 ACCUMULATION.**
  Clean HH+HL/LH+LL → TREND (momentum with) or PULLBACK (momentum against, direction kept); broadening
  (HH&LL) → TRANSITION; coil (LH&HL) after an up/down trend with low efficiency → DISTRIBUTION/ACCUMULATION,
  else TRANSITION; nothing two-sided → RANGE. `erChop`(0.12) volatility gate downgrades a dead-grind
  "trend" to RANGE; `erTrend`(0.35) is the churn cutoff for topping/bottoming.
- **Bias is DERIVED from state**: a directional vote (`bv` ±1) arises **only in TREND/PULLBACK**;
  TRANSITION/DISTRIBUTION/ACCUMULATION/RANGE never vote directionally (D/A carry a neutral lean only).
- **2/3 agreement is the CONFIRMATION** (not the primary decision): `posDir` = ±1 iff ≥2 HTFs vote the
  same side, else 0. `sysState` = system market state (TREND if ≥2 agreeing HTFs are TREND else PULLBACK
  when confirmed; conflict→TRANSITION; else surface DISTRIBUTION/ACCUMULATION; else RANGE). `sysLean`, `erSys`.
- **Execution layer stays bias-free**: `entryDir = posDir` (state-derived, confirmed). M4 timing/gates
  unchanged (all 13 entry scenarios still PASS). Counter-state trades are now impossible — M4 can only fire
  when the system is in a confirmed TREND/PULLBACK.
- **Panel** (bottom-right, 2×5): HTF BIAS (n/3, hover = per-TF state·vote·efficiency) · MARKET STATE
  (name + ▲/▼ lean, hover = definitions + system efficiency) · EXEC · SIGNALS · REJECTED.
- Validator: `pine/position_layer_validate.py` — 7 claims (six-state classification, volatility gate,
  directional vote only in TREND/PULLBACK, PULLBACK keeps trend dir, 2/3 confirmation + system precedence,
  selectivity/no counter-state false signals [160 confirmed combos all backed by ≥2 clean votes],
  determinism) PASS.
- **Freeze blockers**: user compile + observe MARKET STATE matches the visible 1W/1D/4H picture (trend vs
  pullback vs topping) and NEUTRAL suppresses chop. Tune posMomLen / erLen / erTrend / erChop / entryBiasSw.

## OPEN / NON-BLOCKING FOLLOW-UPS
- (polish) print FINAL CONF to 1 decimal to kill the display-rounding optic.
- (future) optional min-confidence gate on which levels can arm M4; session-H/L + EQH/EQL pools as
  additional sweep sources; backtest harness for M4 signal quality.

## GLOSSARY (desk / SMC terms the user uses)
- **BSL** buy-side liquidity = buy stops above highs (red-dashed eye levels). **EQH** equal highs.
- **SSL** sell-side liquidity = sell stops below lows (green-dashed eye levels). **EQL** equal lows.
- **DOL** draw on liquidity = untested pool acting as a magnet. **Sweep/stop-run/spring** =
  wick through a pool then close back = liquidity grab (engine marks ✕; MS-Core treats as sweep not break).
- **LIVE** = nearest S/R above/below price. **STR** = merged-cluster strength. **★** = top-N by confidence.
- Thin/dotted engine lines = **minor / internal / LTF reference S/R** (context, not decision levels).

## WORKING AGREEMENTS
- Honesty over optimism; report failures with evidence. No live-execution code.
- Commit + push each validated change to the branch; deliver the `.pine` file to the user each time.
- Do NOT put the model id in commits/PRs/code. End commits with the Co-Authored-By + Claude-Session lines.
