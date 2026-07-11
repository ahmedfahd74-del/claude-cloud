# Institutional Setup & Market-Structure Engine — Final Specification (v2 · FOR APPROVAL)

> Status: **DRAFT for sign-off.** v2 folds in the 11 requested additions (Liquidity
> Map, displacement quality, trend-strength filter, weighted bias, market-phase
> detection, volatility filter, premium/discount, killzones, expanded dashboard,
> statistics module, validation phase). No implementation begins until you approve.
> Every rule is deterministic: fixed operators, ATR-normalised thresholds, explicit
> tie-breaks, confirmed-close only, no lookahead, no repaint. Defaults shown as
> `name = value`; all are configurable inputs.

---

## 0 · Principles & topology

**Determinism contract (applies to every rule):**
- Detection on **confirmed closes only** (`barstate.isconfirmed`; HTF via
  `request.security(..., lookahead = barmerge.lookahead_off)`).
- A signal is emitted **only on the close of its confirming bar** — never intrabar.
- All price thresholds in **ATR multiples**, never raw price.
- State records **append-only within a bounded window**; ties → lower index wins.
- **Analytics never feed back into trading logic** (§14) — the trigger is a pure
  function of price/time/config, independent of past outcomes.

**Topology:**
```
Structure Engine ─┐ (bias: weighted W/D/4H trend)
S/R Engine ───────┤→ SETUP ENGINE (new, runs on the LTF chart)
Liquidity Engine ─┘   Liquidity Map + sweep + micro-structure + filters +
                      state machine + scoring + management + analytics
```
Pine indicators cannot read each other's state, so the **Setup Engine is
self-contained**, re-implementing the minimal sub-modules with the identical
deterministic rules validated in the three POC engines.

---

## 1 · Market-Structure Engine

### 1.1 Swing detection — pivots as the *detection* layer only
- Candidates: `ta.pivothigh(close, L, R)` / `ta.pivotlow(close, L, R)`, `L=R=pivotLen`
  (**default 5**, 2–30). Close-based — wicks never define a swing.
- Promote to structural swing only if ALL pass:
  1. **Min distance:** `|swing − lastSameSideSwing| ≥ minSwingATR × ATR` (`0.50`).
  2. **Close confirmation:** taken from `close[pivotLen]` (non-repaint).
  3. **Strength score** (0–100, frozen):
     `round(50·min(1, legMove/(3·ATR)) + 50·min(1, barsInLeg/10))`.
- **Adaptive** = fixed pivot length, ATR filters auto-scale to volatility (no hidden
  regime switching).

### 1.2 Internal vs external structure
- **External:** `legMove ≥ extSwingATR × ATR` (`1.50`) from last opposite external swing.
- **Internal:** passes `minSwingATR` but `< extSwingATR`.
- Trend/BOS/CHoCH/MSS use **external**; micro-entry confirmation uses **internal**.

### 1.3 Strong vs weak highs/lows
- **Weak high:** a later candle **closes above it** (liquidity taken).
- **Strong high:** before any close above, price first **closes below the last external
  low** (produced a bearish BOS — it defended). Lows mirror. Monotonic; flips on close.

### 1.4 HH/HL/LH/LL (vs last same-side external swing)
- High → **HH** if `> lastExtHigh` else **LH**. Low → **HL** if `> lastExtLow` else **LL**.

### 1.5 BOS / CHoCH / MSS (close, external swings)
- **BOS:** `close > lastExtHigh` in bull trend (or unset) → bull BOS; `close < lastExtLow`
  in bear trend → bear BOS.
- **CHoCH:** first opposing break — bull trend & `close < lastExtLow` → bear CHoCH
  (flips trend); mirror for bull.
- **MSS:** a CHoCH whose breaking candle passes §3 displacement (stronger; validates
  entries). Plain CHoCH scores lower and cannot alone confirm an entry.
- **Micro BOS/MSS:** same rules on **internal** swings on the chart TF, in bias
  direction, after sweep+reclaim.

### 1.6 Noise filtering
- Swings failing `minSwingATR` discarded. Candles with `range < noiseATR × ATR`
  (`0.15`) cannot create a swing or a break.

---

## 2 · Liquidity Map (NEW — item 1)

A deterministic register of liquidity pools, each `{price, type, side, strength}`:
- **Swing liquidity:** external/internal swing highs = **buy-side (BSL)** above; swing
  lows = **sell-side (SSL)** below.
- **Equal Highs/Lows (EQH/EQL):** ≥2 same-side swings within `eqTol × ATR` (`0.10`) →
  EQH (strong BSL) / EQL (strong SSL).
- **Previous Day / Week H/L (PDH/PDL/PWH/PWL):** `request.security(sym, "D"/"W",
  high[1]/low[1], lookahead_off)` — prior completed bar.
- **Session H/L:** running high/low of the current & previous London / NY sessions
  (§10), frozen at session close.
- **Strength order (for scoring):** PWH/PWL > PDH/PDL ≈ EQH/EQL > external swing >
  internal swing.

**Use — "Liquidity target quality" score factor:** a sweep that takes a *mapped*
pool scores by that pool's strength; a sweep of unmapped price scores 0 on this factor.
Only pools **in bias direction of the intended trade** count (a long wants a swept
SSL/EQL/PDL below).

---

## 3 · Displacement — quality, not a single ATR test (item 2)

Computed over the displacement leg (reclaim candle + up to `dispLook = 3` bars):
- **Body size:** `|close − open| ≥ dispBodyATR × ATR` (`0.55`).
- **Range:** `high − low ≥ dispRangeATR × ATR` (`1.00`).
- **Consecutive impulse:** `≥ impSeq` candles (`2`) in-direction, each body
  `≥ dispBodyATR × ATR`.
- **Body dominance:** mean `body/range ≥ bodyDom` (`0.60`) across the leg.
- **Low overlap:** each candle opens beyond the prior candle's midpoint in-direction;
  mean overlap `≤ maxOverlap` (`0.50`).
- **Close at extreme:** in-direction close within `closeFrac` of range (`0.66`).
- **Rel-volume / ATR-expansion:** `volume ≥ volMult × SMA(volume, volLen)`
  (`1.50 / 20`; range-proxy if `na(volume)`) **or** `range ≥ expMult × ATR` (`1.20`).

**Displacement quality (0–1)** = weighted fraction of the above passed; the reclaim
must reach `dispQualMin = 0.60` to advance the state machine. All weights/thresholds
are inputs.

---

## 4 · HTF bias — weighted, W+D prioritised (items 4, 6)

- `wTrend/dTrend/h4Trend` from the trend-only engine (confirmed close BOS/CHoCH,
  scalar `request.security`, correct on any chart).
- **Weighted direction score:** `dirScore = 3·sign(wTrend) + 2·sign(dTrend) +
  1·sign(h4Trend)` (range −6…+6).
- **Bias:** `BULLISH if dirScore ≥ +3 · BEARISH if ≤ −3 · else NEUTRAL`.
  - Consequence (as requested): **Weekly+Daily** agreement (3+2 = 5) sets bias even if
    4H disagrees (5−1 = 4 ≥ 3). **Daily+4H** agreement against Weekly (−3+2+1 = 0) is
    **NEUTRAL** — W+D outranks D+4H.
- **Bias-strength score factor:** `|dirScore| ≥ 5` (W+D or 3/3) = full points; `= 3/4`
  (bare majority) = partial.
- **MTF sync:** every armed/active setup stores `wTrend`+`dTrend` at arming; a **Weekly
  or Daily flip invalidates all** pending/active setups (§8).

---

## 5 · Power Line & tolerance (items 5, 7)
- **PL1** = nearest **unbroken W/D** level; **PL2** = next opposing W/D level (final
  target).
- **Touch tolerance:** `|price − Lv| ≤ max(tolATR × dailyATR, tolPct × zoneWidth)`
  (`tolATR = 0.50`, `tolPct = 0.25`).
- **Confluence factor:** swept level within tolerance of `PL1`.

---

## 6 · Trend-Strength & Volatility & Phase & Premium/Discount filters (items 3, 5, 6, 7)

### 6.1 Trend-Strength filter (item 3)
- `ADX(adxLen = 14) ≥ adxMin` (`20`) **or** EMA slope: `ema(close, 50)` change over
  `slopeLen = 10` bars `≥ slopeMinATR × ATR` (`0.75`) in bias direction.
- **trendStrength (0–1)** = normalised blend of ADX and slope; weak trend **reduces
  confidence** (score factor scales with it). Below `trendMin = 0.30` the trend
  component scores 0 (does not hard-block by itself).

### 6.2 Volatility filter (item 6) — HARD GATE
- Require `ATR ≥ volFloorMult × SMA(ATR, volFloorLen)` (`0.60 / 50`). Below → **dead
  market, no setup armed** (prevents low-ATR false sweeps).

### 6.3 Market-Phase detection (item 5)
Deterministic, evaluated each confirmed bar; first match wins in this priority:
- **Expansion:** `ATR ≥ atrHi × SMA(ATR,50)` (`1.30`) **and** displacement present.
- **Trending:** last two external breaks **same direction** and `trendStrength ≥
  trendMin`.
- **Pullback:** external trend intact but an **internal** counter-move (internal CHoCH)
  is in progress.
- **Compression:** `ATR ≤ atrLo × SMA(ATR,50)` (`0.70`) and `≥ compBars` (`5`)
  narrowing/inside bars.
- **Accumulation:** Compression **after a downtrend**, in **discount** (§6.4), near
  SSL/EQL.
- **Distribution:** Compression **after an uptrend**, in **premium**, near BSL/EQH.

**Phase filter:** trend-continuation setups are taken in **Trending / Pullback /
Expansion**; **Compression / Accumulation / Distribution** lower the phase score factor
(configurable to hard-block — decision **D8**).

### 6.4 Premium / Discount (item 7)
- **Dealing range** = current structural leg's external `rangeHigh`…`rangeLow`;
  **equilibrium** = 50%.
- **Discount** = price `< 50%`; **Premium** = price `> 50%`.
- **Longs preferred in Discount, shorts in Premium.** Aligned → score bonus;
  **against** (long in premium / short in discount) → penalty or block (decision **D9**;
  default: block).

---

## 7 · Entry confirmation — state machine (item 1)
```
IDLE
 └─(bias≠NEUTRAL · volatility OK · price within tol of an HTF level & mapped pool in
     bias direction · premium/discount aligned)→ ARMED
ARMED     └─(valid §2 sweep of a mapped pool, displacement quality ≥ dispQualMin)→ SWEPT
SWEPT     └─(close reclaims level within reclaimBars)→ RECLAIMED
RECLAIMED └─(micro BOS/MSS §1.5 in bias direction, displacement ≥ dispQualMin)→ CONFIRMED
CONFIRMED └─(entry rule met — default market on the confirming close)→ TRIGGERED
TRIGGERED → MANAGED (§8) → CLOSED
any state →(§8 invalidation / expiration)→ INVALID
```
Only a setup reaching **TRIGGERED** with **score ≥ minScore** fires an entry alert.

---

## 8 · Invalidation & expiration (items 5, 6, 10)
**Invalidation (any pending/active):** close beyond the **sweep extreme**; opposite
**BOS/CHoCH**; **HTF bias change** (Weekly/Daily flip).
**Expiration (confirmed chart bars):** `armedExpiry = 20`, `sweepExpiry = 2`
(= `reclaimBars`), `confirmExpiry = 10`, `triggerExpiry = 5`. Any expiry → INVALID. No
setup lives indefinitely.

---

## 9 · Confidence score, grade & trade management (items 4, 8)

### 9.1 Hard gates (fail → no setup): bias≠NEUTRAL · at W/D S/R · valid sweep of a mapped
pool · micro BOS/MSS · volatility ≥ floor · premium/discount aligned (if D9 = block).

### 9.2 Score (0–100), evaluated at CONFIRMED
| Component | Max pts |
|---|---|
| Bias strength (W+D / 3-of-3 vs bare majority) | 20 |
| Liquidity target quality (swept pool strength, §2) | 15 |
| Displacement quality (§3, scaled 0–1) | 15 |
| Sweep+reclaim clean (rejFrac, quick reclaim) | 10 |
| Micro BOS/MSS with displacement | 10 |
| Power-Line confluence (§5) | 8 |
| Premium/Discount alignment (§6.4) | 8 |
| Trend strength (§6.1, scaled 0–1) | 8 |
| Market phase favourable (§6.3) | 6 |
| Killzone — London/NY/overlap (§10) | 5 |
| Volume / rel-vol confirm (§3) | 5 |
Sum capped at **100**.
**Grade:** `A+ ≥ 90 · A ≥ 80 · B ≥ 65 · C ≥ 50 · else NO-TRADE`. Alerts at
`minScore` (**default 80**).

### 9.3 Trade management (item 8)
- **Entry:** market on CONFIRMED close (alt: limit at level retest — D3).
- **SL:** beyond sweep extreme ± `slBufferATR × ATR` (`0.10`); `R = |entry − SL|`.
- **Partial TP:** 1R, close `partialPct = 50%`, SL → break-even.
- **Trail:** after 1R, `max(trailATR × ATR, last internal swing)` (`trailATR = 1.00`).
- **Final target:** `PL2`; if none within `maxTargetR = 3`, fixed 3R.

---

## 10 · Sessions & Killzones (item 8) — prioritised
Deterministic via `time(timeframe.period, session, tz)`, `tz = "UTC"` default.
- **Killzones (high-probability, prioritised):** **London Open** `0700–1000`,
  **New York Open** `1200–1500`, **London/NY Overlap** `1200–1600`.
- Broader sessions (London `0700–1600`, NY `1200–2100`, Asian `2300–0800` optional/off)
  tracked for the Liquidity Map session H/L.
- **Killzone factor:** setups whose sweep occurs inside an enabled killzone score the
  §9 killzone points; outside enabled killzones → lower score or block (decision **D4**;
  default block outside all enabled sessions, but killzone only affects the 5-pt factor).

---

## 11 · Setup dashboard — detailed breakdown (item 9)
Two-column panel with a **per-component score breakdown**, not just the total:
- **Header:** State · Direction · **Confidence 0–100** · **Grade (A+/A/B/C)**.
- **Context rows:** Bias (`W▲ D▲ 4H▼`, dirScore) · Market Phase · Premium/Discount ·
  Trend strength · Volatility state · Liquidity target (type + side).
- **Checklist w/ points:** each §9.2 component shown as `✓/✗  +pts` so you see *why*
  the score is what it is.
- **Trade rows:** Entry · SL · TP1 · Final target · R:R.
This panel is the final trade-approval readout.

---

## 12 · Determinism, non-repaint & Pine/TradingView limits
- HTF context via `request.security(lookahead_off)`; entry logic on confirmed chart
  closes only.
- **Freeze-test upgrade (fixes the 30m/3m FAIL):** hash a **bounded recent band** of
  frozen records (`birthTime ∈ [freezeCutT − bandMs, freezeCutT]`) instead of
  everything-older-than-cutoff — immune to tail eviction, so A=B=C on all timeframes.
- Bounded arrays; `calc_bars_count`; small `max_bars_back`; drawing-object caps;
  ATR/volume-proxy fallbacks. RE10139/RE10110-safe (same fixes proven in the POCs).

---

## 13 · Statistics & Analytics module (item 10) — ANALYSIS ONLY
A rolling record of the **last 200 TRIGGERED setups** and their outcomes, updated only
when a setup CLOSES (TP/SL/BE). **It never influences the trigger** (read-only sink).
Tracks per setup: direction, grade, score, session/killzone, sweep type (which mapped
pool), BOS vs MSS confirmation, phase, premium/discount, realised R, outcome.
**Aggregates displayed in a separate stats panel:** win rate, avg realised R,
**profit factor** (Σwins/Σlosses), **max drawdown** of the tracked equity curve,
**win rate & avg R by grade**, **by session/killzone**, **by sweep type**, **by
BOS/MSS**. Configurable window (`statN = 200`). Because outcomes never feed back,
determinism/hashes are unaffected.

---

## 14 · Decisions needing your sign-off (defaults chosen; override any)
- **D1** Entry structure: external HTF + **internal micro-confirm** (default).
- **D2** Levels: sweeps validated at **1W/1D** Power Lines only (default) or also 4H.
- **D3** Entry style: **market on CONFIRMED close** (default) vs limit at retest.
- **D4** Off-session handling: **block outside enabled sessions** (default) vs score-only.
- **D5** Score weights/threshold: §9.2 table, `minScore = 80` (default).
- **D6** Asset preset default: **Crypto** (default) vs Forex.
- **D7** Packaging: one **new "IA-Setup" overlay** (default) vs entry arrows in S/R script.
- **D8** Market phase in Compression/Accumulation/Distribution: **soft (lower score)**
  (default) vs hard-block.
- **D9** Premium/Discount against-bias: **hard-block** (default) vs penalty-only.

---

## 15 · Phased build plan (starts only after approval)
1. **Micro-structure core** (§1) on chart TF + **freeze-band fix** (§12). Validate
   hashes/freeze 3m→1W.
2. **Liquidity Map** (§2): swings, EQH/EQL, PDH/PDL/PWH/PWL, session H/L.
3. **Sweep + displacement quality** (§3) + **ATR asset presets** (§16).
4. **Filters:** weighted bias (§4), trend-strength, volatility gate, market phase,
   premium/discount (§6).
5. **HTF context** (§5) + **state machine** (§7) + invalidation/expiration (§8).
6. **Scoring, grade, killzones** (§9/§10) + **detailed dashboard** (§11).
7. **Trade management** (§9.3) + alerts.
8. **Statistics & Analytics** (§13) — read-only.
9. **Validation & Optimization (item 11):** replay-determinism (A=B=C / stable hashes)
   + **cross-market testing** (Forex, Crypto, Gold, Indices) + performance under Pine
   limits + parameter sanity sweep. Engine is "complete" only after this phase passes.
Each phase: committed, audited, delivered for your test before the next begins.

---

## 16 · ATR asset presets (item — thresholds configurable)
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
| `volFloorMult` | 0.60 | 0.60 | 0.60 | 0.55 |
| `adxMin` | 20 | 18 | 20 | 22 |
| `volMult` | 1.50 | 1.50 | 1.50 | 1.40 |

---

### Approval
Reply **"approved"** (optionally with answers to D1–D9 and any threshold/weight tweaks)
and I will begin **Phase 1**. Nothing is coded until then.
