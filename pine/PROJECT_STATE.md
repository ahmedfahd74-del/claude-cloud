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

## MS-CORE — bias panel (frozen intent)
- Dashboard rows (1W/1D/4H/1H **+ Chart**) all read the **same HH/HL/LH/LL sequence classifier**
  `f_structPrev` via `request.security([1] + lookahead_on)` = last CLOSED bar.
  Bias: **HH+HL = BULL · LH+LL = BEAR · conflicting = MIXED**. Not candle direction, not EMAs.
- **Two swing sizes, decoupled:** `Bias Swing Size` (mtfSwing) drives **all** bias rows incl. Chart
  (Chart row = security on `timeframe.period`, so on any TF it is byte-identical to that TF's MTF row);
  `Label Swing Size` (swL) drives HH/HL/LH/LL labels + BOS/CHoCH visuals **only** — never bias.
- Panel: TF | bias | struct(e.g. LH+LL); hover a row = audit (last swing high/low, state, reason).
- BOS/CHoCH protected-swing drawing engine is separate and untouched.

## VALIDATORS (Python models of the Pine logic — run before every freeze)
`pine/level_core_validate.py` (detection 5 props) · `pine/level_core_v2_score_validate.py` (scoring) ·
`pine/level_core_v2_merge_validate.py` (merge). All currently PASS.
NOTE: these validate the LOGIC, not compiled Pine — the real compile check is the user's paste.

## ADVERSARIAL REVIEW (last run) — verdict per question
1 Reconciliation PASS (clamp can't fire; ≤0.5pt display rounding only) · 2 Qualified count PASS
(no cluster double-count) · 3 HTF/LTF states PASS (may disagree = correct; each row matches own labels)
· 4 Insufficient pivots PASS (→ MIXED / "—") · 5 Tests PARTIAL (logic solid; compile risk remains).
**Recommended: FREEZE (conditional on user's clean compile of both files).**

## M4 — ENTRY ENGINE (liquidity-first) — BUILT + LOGIC-VALIDATED, **NOT frozen**
- Lives inside `level_core_v2.pine`, group "Entry Engine (liquidity-first) — M4". Read-only over the
  frozen book — no detection/scoring changes (all prior validators re-run and pass).
- **Bias**: sequence classifier (HH+HL/LH+LL) on W/D/4H/1H closed bars, weights .40/.30/.20/.10,
  deadband ±0.15 → +1/−1/0. **MIXED = no signals.** Input: `Bias Swing Size` (entryBiasSw, default 5).
- **State machine (closed bars only)**: IDLE → sweep of LIVE level in bias direction (bear: wick > ceiling,
  close ≤ ceiling; bull: mirror) = ARM (✕ mark) → within `confirmBars`(3) a close through the sweep bar's
  opposite extreme = **SIGNAL** (label + entry/stop/target lines, stop = sweep wick, target = opposing LIVE
  level, R:R shown) → cooldown `coolBars`(10). Expiry / close-beyond-sweep-extreme / bias-flip all reset.
- Alerts: "M4 LONG/SHORT (liquidity-first)". Bottom-right entry panel: BIAS(score) / STATE / SIGNALS count.
- Validator: `pine/level_core_v2_entry_validate.py` — 9 scenarios (arm, confirm, expiry, invalidation,
  bias-flip reset, cooldown, MIXED, no-repaint gate, determinism) all PASS.
- **Freeze blockers**: user compile + forward-test on live crypto (does it only fire on real sweeps?),
  then tune confirmBars/coolBars from observation. Backtest before trusting with money.

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
