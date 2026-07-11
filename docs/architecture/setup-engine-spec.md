# Institutional Setup & Market-Structure Engine — Final Specification (v1 · FOR APPROVAL)

> Status: **DRAFT for sign-off.** No implementation begins until you approve this
> document. Every rule below is deterministic: fixed operators, ATR-normalised
> thresholds, explicit tie-breaks, confirmed-close only, no lookahead, no repaint.
> Defaults are shown as `name = value`; all are configurable inputs.

---

## 0 · Principles & topology

**Determinism contract (applies to every rule in this doc):**
- All detection runs on **confirmed closes only** (`barstate.isconfirmed`; HTF via
  `request.security(..., lookahead = barmerge.lookahead_off)`).
- A signal is emitted **only on the close of its confirming bar** — never intrabar,
  so nothing repaints.
- All price thresholds are expressed in **ATR multiples**, never raw price, so the
  same config behaves consistently across symbols.
- State records are **append-only within a bounded window**; ties broken by a
  stated total order (lower index wins) so results are order-independent.

**Topology (3 source engines + 1 decision engine):**
```
Structure Engine ─┐  (bias: 2-of-3 W/D/4H trend)
S/R Engine ───────┤→  SETUP ENGINE (new, runs on the LTF chart)
Liquidity Engine ─┘   reads bias + nearest W/D level + sweeps, runs the
                      confirmation state machine, scores, manages the trade
```
Pine indicators cannot read each other's state, so the **Setup Engine is
self-contained**: it re-implements the *minimal* deterministic sub-modules it needs
(HTF trend via scalar `request.security`, nearest W/D level, sweep + micro-structure
on the chart TF) using the **identical rules** proven in the three POC engines. The
three POCs remain the independent reference/validation engines.

---

## 1 · Market-Structure Engine (item 13 + 14)

### 1.1 Swing detection — pivots as the *detection* layer only
- Candidate swings: `ta.pivothigh(close, L, R)` / `ta.pivotlow(close, L, R)` with
  `L = R = pivotLen` (**default 5**, range 2–30). Close-based — wicks never define a
  swing.
- A candidate is promoted to a **structural swing** only if it passes ALL filters:
  1. **Minimum swing distance:** `|swing − lastSameSideSwing| ≥ minSwingATR × ATR`
     (`minSwingATR = 0.50`).
  2. **Close confirmation:** the pivot is taken from `close[pivotLen]` (already
     confirmed `pivotLen` bars later — non-repaint).
  3. **Swing-strength score** (0–100, frozen at birth):
     `strength = round( 50·min(1, legMove/(3·ATR)) + 50·min(1, barsInLeg/legBarsRef) )`
     where `legMove = |swing − priorOppositeSwing|`, `legBarsRef = 10`.
- **Adaptive** = pivot length stays fixed but the ATR filters auto-scale detection to
  volatility (bigger ATR → wider min distance → fewer, larger swings). No hidden
  regime switching (keeps it deterministic and debuggable).

### 1.2 Internal vs external structure
- **External (major) swing:** `legMove ≥ extSwingATR × ATR` (`extSwingATR = 1.50`)
  measured from the last external swing of the opposite side.
- **Internal (minor) swing:** passes `minSwingATR` but `legMove < extSwingATR × ATR`.
- Trend/BOS/CHoCH/MSS classification uses **external** swings; micro-entry confirmation
  uses **internal** swings.

### 1.3 Strong vs weak highs/lows
- A swing **HIGH is WEAK** the moment a later candle **closes above it** (it was
  liquidity, taken out).
- A swing **HIGH is STRONG** if, before any close above it, price first **closes below
  the most recent external swing low** (it produced a bearish BOS — it defended).
- Lows are the mirror. Classification is monotonic (a strong low can become weak, never
  the reverse) and only flips on a **confirmed close**.

### 1.4 HH / HL / LH / LL (vs last confirmed same-side external swing)
- New high → **HH** if `> lastExtHigh`, else **LH**.
- New low → **HL** if `> lastExtLow`, else **LL**.

### 1.5 BOS / CHoCH / MSS (all on close, external swings)
- **BOS (continuation):** `close > lastExtHigh` while trend already bullish (or unset)
  → bullish BOS. `close < lastExtLow` while bearish → bearish BOS.
- **CHoCH (first opposing break):** trend bullish and `close < lastExtLow` → bearish
  CHoCH (flips trend to −1). Trend bearish and `close > lastExtHigh` → bullish CHoCH.
- **MSS (structure shift w/ displacement):** a CHoCH whose breaking candle also passes
  §3 displacement. MSS is the **stronger** confirmation used to validate entries; a
  plain CHoCH without displacement scores lower and does not by itself confirm an entry.
- **Micro BOS/MSS (entry timeframe):** the same rules applied to **internal** swings on
  the chart TF, in the trade direction, after sweep+reclaim.

### 1.6 Noise filtering
- Swings failing `minSwingATR` are discarded (never stored).
- Doji/again-inside candles (`range < noiseATR × ATR`, `noiseATR = 0.15`) cannot create
  a swing or a BOS.

---

## 2 · Liquidity Sweep — exact rules (item 2)

Level zone: `zoneHalf = zoneATR × dailyATR` (`zoneATR = 0.25`) around an HTF level `Lv`.

**Bullish sweep (at support, for longs):** ALL true on the confirmed candle —
1. `low  < Lv − sweepATR × ATR`  (`sweepATR = 0.25`) — wick pierces below.
2. `close > Lv`                    — closes back above the level.
3. `(close − low) / (high − low) ≥ rejFrac` (`rejFrac = 0.55`) — close in upper part.
4. Reclaim occurs within `reclaimBars = 2` confirmed bars of the pierce.
5. Displacement (§3) confirms on the reclaim candle **or** the next confirmed candle.

**Bearish sweep (at resistance, for shorts):** mirror (high pierces above, close below,
close in lower part).

All distances ATR-normalised; every constant above is a configurable input.

---

## 3 · Displacement confirmation (item 3)

A move qualifies if it passes the **required set** (configurable which are mandatory):
- **Body:** `|close − open| ≥ dispBodyATR × ATR` (`dispBodyATR = 0.55`).
- **Range:** `high − low ≥ dispRangeATR × ATR` (`dispRangeATR = 1.00`).
- **Close at extreme:** trade-direction close in `closeFrac` of range
  (`closeFrac = 0.66`).
- **ATR expansion:** `range ≥ expMult × ATR` (`expMult = 1.20`).
- **Relative volume:** `volume ≥ volMult × SMA(volume, volLen)` (`volMult = 1.50`,
  `volLen = 20`). **Volume proxy** when `na(volume)`: use
  `range ≥ volMult × SMA(range, volLen)`.

Default requirement: **(Body OR Range) AND (Volume OR ATR-expansion).**

---

## 4 · HTF bias + multi-timeframe sync (items 1, 6)

- `wTrend`, `dTrend`, `h4Trend` from the lightweight trend-only engine (confirmed close
  BOS/CHoCH, scalar `request.security`, correct on any chart).
- **Bias = 2-of-3 majority** (BULLISH if ≥2 bullish, BEARISH if ≥2 bearish, else
  NEUTRAL). No trades while NEUTRAL.
- **Sync/invalidation:** every armed/active setup stores the bias + `wTrend`/`dTrend` at
  arming. If **Weekly or Daily trend flips**, **all** pending and active setups are
  immediately invalidated (§7).

---

## 5 · Power Line & tolerance (items 5, 7)

- **Power Line** `PL1` = nearest **unbroken Weekly/Daily** level to price (as in the S/R
  POC). `PL2` = next opposing W/D level (used as final target).
- **Touch tolerance** (price "at" the level): valid when
  `|price − Lv| ≤ max(tolATR × dailyATR, tolPct × zoneWidth)`
  (`tolATR = 0.50`, `tolPct = 0.25`). Configurable.
- **Power-Line confluence** (score bonus): true when the swept level is within tolerance
  of `PL1`.

---

## 6 · Entry confirmation sequence — state machine (item 1)

A setup advances through explicit states; **no state is skipped**, each has an
expiration (§7):

```
IDLE
 └─(bias≠NEUTRAL AND price within tol of an HTF level in bias direction)→ ARMED
ARMED
 └─(valid §2 sweep of that level, with §3 displacement)→ SWEPT
SWEPT
 └─(close reclaims level within reclaimBars)→ RECLAIMED
RECLAIMED
 └─(micro BOS/MSS §1.5 in bias direction, with §3 displacement)→ CONFIRMED
CONFIRMED
 └─(entry rule met — §8 default: market on the confirming close)→ TRIGGERED
TRIGGERED → MANAGED (§8) → CLOSED
any state →(§7 invalidation)→ INVALID
```
Only a setup reaching **TRIGGERED** with **score ≥ threshold** (§8) fires an entry alert.

---

## 7 · Invalidation & expiration (items 5, 6, 10)

**Invalidation (immediate, any pending/active setup):**
- Close beyond the **sweep extreme** (pre-entry) → INVALID.
- Opposite **BOS/CHoCH** forms → INVALID.
- **HTF bias changes** (Weekly/Daily flip) → INVALID.

**Expiration (bars are confirmed chart bars):**
- `armedExpiry = 20` — bars a setup may sit ARMED at a level before a sweep.
- `sweepExpiry = 2` — bars to RECLAIM after the sweep (= `reclaimBars`).
- `confirmExpiry = 10` — bars to reach CONFIRMED after RECLAIMED.
- `triggerExpiry = 5` — bars to TRIGGER after CONFIRMED.
No setup remains active indefinitely; on any expiry → INVALID.

---

## 8 · Confidence score, grade & trade management (items 4, 8, 12)

### 8.1 Score (0–100) — weighted checklist, evaluated at CONFIRMED
| Component | Points | Mandatory |
|---|---|---|
| HTF bias 2-of-3 aligned | 25 | ✓ |
| HTF bias 3-of-3 aligned (bonus) | +10 | — |
| At Weekly/Daily S/R within tolerance | 15 | ✓ |
| Valid liquidity sweep (§2) | 20 | ✓ |
| Micro BOS/MSS with displacement (§1.5/§3) | 15 | ✓ |
| Power-Line confluence (§5) | 10 | — |
| Volume / displacement confirm (§3) | 10 | — |
| In preferred session (§9) | 5 | — |
Score capped at 100. A setup missing any **mandatory** component never reaches
CONFIRMED (cannot score at all).

**Grade:** `A+ ≥ 90 · A ≥ 80 · B ≥ 65 · C ≥ 50 · else NO-TRADE`.
**Alert threshold** = `minScore` (**default 80**, configurable). Alerts fire only at/above it.

### 8.2 Trade management (item 8)
- **Entry:** default **market on the CONFIRMED close** (alt: limit at level retest —
  see decision D3).
- **Initial SL:** beyond the **sweep extreme** ± `slBufferATR × ATR`
  (`slBufferATR = 0.10`). `R = |entry − SL|`.
- **Partial TP:** at **1R**, close `partialPct = 50%`, move SL → **break-even**.
- **Trailing:** after 1R, trail by `max(trailATR × ATR, last internal swing)`
  (`trailATR = 1.00`).
- **Final target:** next opposing HTF Power Line (`PL2`); if none within `maxTargetR = 3`,
  use fixed **3R**.

---

## 9 · Session filter (item 9)
Deterministic via `time(timeframe.period, session, tz)`; default `tz = "UTC"`.
- **London** `0700–1600`, **New York** `1200–2100`, **Overlap** `1200–1600`,
  **Asian (optional)** `2300–0800`.
- Default enabled: London + NY + Overlap; Asian **off** (avoids low-liquidity false
  sweeps). A sweep outside enabled sessions does not arm/score (configurable to
  "score −0" vs "hard block" — decision D4).

---

## 10 · ATR configuration & asset presets (item 11)
`atrLen = 14` (configurable). An **Asset Preset** selector loads intelligent defaults;
every value stays individually overridable.

| Threshold | Forex | Crypto | Gold | Indices |
|---|---|---|---|---|
| `sweepATR` | 0.20 | 0.30 | 0.25 | 0.25 |
| `zoneATR` | 0.20 | 0.30 | 0.25 | 0.25 |
| `dispBodyATR` | 0.50 | 0.60 | 0.55 | 0.55 |
| `dispRangeATR` | 0.90 | 1.10 | 1.00 | 1.00 |
| `minSwingATR` | 0.50 | 0.60 | 0.55 | 0.50 |
| `extSwingATR` | 1.40 | 1.70 | 1.50 | 1.50 |
| `tolATR` | 0.50 | 0.60 | 0.50 | 0.50 |
| `slBufferATR` | 0.10 | 0.15 | 0.12 | 0.10 |
| `volMult` | 1.50 | 1.50 | 1.50 | 1.40 |

---

## 11 · Setup dashboard (item 12)
Live checklist with ✓/✗ per component: **HTF Bias · W/D Level · Liquidity Sweep ·
BOS/MSS · Power Line · Volume · Session**. Plus:
- **State** (IDLE→…→TRIGGERED/INVALID), **Direction**, **Confidence 0–100**,
  **Grade (A+/A/B/C)**.
- **Entry / SL / TP1 / Final target** and **R:R**.
This panel is the final trade-approval readout before entry.

---

## 12 · Determinism, non-repaint & Pine/TradingView limits (item 13)
- HTF context via `request.security(lookahead_off)`; entry logic on confirmed chart-bar
  closes only.
- **Freeze-test upgrade (fixes the LTF FAIL you saw):** hash a **bounded recent band**
  of frozen records — records with `birthTime ∈ [freezeCutT − bandMs, freezeCutT]` — not
  "everything older than the cutoff." On low timeframes the cutoff is only ~a day of real
  time, so the old definition made almost the whole HTF book "frozen" and book-aging then
  mutated it → A≠B≠C. A bounded band is immune to tail eviction → PASS on all TFs.
- Bounded arrays; `calc_bars_count` and small `max_bars_back`; drawing-object caps; ATR
  and volume-proxy fallbacks so it runs on every symbol within the memory/time budget
  (RE10139/RE10110 safe — same fixes already validated in the POCs).

---

## 13 · Decisions needing your sign-off (defaults chosen; override any)
- **D1 — Structure source for entries:** external swings for HTF context + **internal
  swings for the micro-entry confirmation** (default). Or entries off external only?
- **D2 — Levels used:** sweeps validated **only at 1W/1D** Power Lines (default), or also
  4H levels?
- **D3 — Entry style:** **market on CONFIRMED close** (default) vs limit order at a level
  retest after confirmation.
- **D4 — Session handling:** **hard-block** setups outside enabled sessions (default) vs
  merely score them lower.
- **D5 — Score weights & threshold:** table in §8.1 with `minScore = 80` (default) — keep
  or adjust.
- **D6 — Asset preset default:** `Crypto` (your SOL/USDT testing) vs `Forex`.
- **D7 — Packaging:** one **new combined "IA-Setup" overlay** (default) vs folding entry
  arrows into the existing S/R script.

---

## 14 · Phased build plan (starts only after approval)
1. **Micro-structure core** on chart TF: pivots→filters→internal/external, strong/weak,
   BOS/CHoCH/MSS, non-repaint + freeze-band fix. Validate hashes/freeze on 3m→1W.
2. **Sweep + displacement** detectors (§2/§3) with the ATR preset system.
3. **HTF context**: 2-of-3 bias + nearest W/D Power Line + tolerance, inside the Setup
   Engine.
4. **State machine** (§6), invalidation & expiration (§7).
5. **Scoring, grade, session** (§8/§9) + **dashboard** (§11).
6. **Trade management** (§8.2): SL/BE/partials/trail/target + alerts.
Each phase is committed, audited, and delivered for your test before the next begins.

---

### Approval
Reply **"approved"** (optionally with answers to D1–D7) and I will begin Phase 1.
Nothing is coded until then.
