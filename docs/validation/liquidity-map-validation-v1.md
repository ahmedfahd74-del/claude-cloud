# Liquidity Map — Validation Report (v1)

Scope: `pine/setup_engine.pine` Liquidity Map (PDH/PDL/PWH/PWL, London/NY/Asian/
Sydney session H-L, EQH/EQL, swing BSL/SSL) + per-group visualization + Power Line.

> **Honesty note.** I cannot execute TradingView from this environment, so I do **not**
> claim any live Hash or Freeze pass here. This report separates what is **proven
> locally by deterministic modelling + static analysis** from what **still requires the
> TradingView runtime**. Hash/Freeze are marked *verified* only after you confirm them
> in TradingView.

---

## 1 · Locally Verified (proven)

Tooling: `scratchpad/liq_validate.py` (deterministic models of the exact Pine math,
run over many random inputs) + `scratchpad/audit.py` (delimiter/indent/arity/ref
static audit). A property that holds for every random case holds by construction in
Pine, because the model computes the identical math.

| # | Check | Method | Result |
|---|---|---|---|
| 1 | **Cross-TF level invariance** — PDH/PDL/PWH/PWL identical price on every chart TF | modelled 8-day 1-min data → aggregated to 3/5/15/30/60/240m; prev-day extreme identical across all (30 seeds) | ✅ PASS |
| 2 | **Session extreme + anchor** — frozen level = true session max/min, anchor = the extreme's candle | 200 random sessions | ✅ PASS |
| 3 | **Session TF-independence** — level identical across TFs, anchor in correct bucket | 50 sessions × 5 aggregations | ✅ PASS |
| 4 | **Equal H/L sourcing** — EQH/EQL price is an actual source swing; anchor = earlier swing | 200 random swing sets | ✅ PASS |
| 5 | **Hash/Freeze non-interference** — liquidity code never writes `sP/sTy/sExt/sBar/sBt/sStr/sState/sBroken` | static scan of the liquidity block | ✅ PASS |
| 6 | **Calc/visual separation** — renderer never writes `Lp/Lt/LaT/Lg` (levels) | static scan of the renderer | ✅ PASS |
| 7 | **No duplicate levels** — each tag added by exactly one `f_add` | static scan | ✅ PASS |
| 8 | **No HTF repaint** — every `request.security` uses `lookahead_off` | static scan | ✅ PASS |
| 9 | **Tuple arity** — `f_sess` returns/destructures 4; `f_hasEqual` 3 | static scan | ✅ PASS |
| 10 | **Non-repaint source** — structure/swing detection gated on `barstate.isconfirmed` | static scan | ✅ PASS |
| 11 | **Structural audit** — delimiters balanced, indentation valid, no stray refs | `audit.py` | ✅ PASS |

**What these prove:** every liquidity level's **price is a source value** (never
offset/smoothed/relocated by the display layer) and is **timeframe-independent**;
each level **anchors to its originating candle**; the **visualization layer is
read-only** over the calculated levels; and the liquidity code **cannot change the
structure hash or freeze test** (it only reads structure arrays).

**Boundary / settings validation (static):** every input has explicit
`minval/maxval` (widths 1–4, transparency 0–100, priority 1–10, tolerances bounded);
extend ∈ {None,Left,Right,Both}; style ∈ {Solid,Dashed,Dotted}; label size ∈
{Tiny,Small,Normal}. Group→setting mappings (`f_gCol/f_gStyS/f_gW/f_gTr/f_gExtS/
f_gLbl/f_gLzS/f_gPri`) cover all group ids 0–7 with a total (else) branch, so no
group can fall through to an undefined visual.

---

## 2 · Requires TradingView Runtime Verification (NOT yet claimed)

These depend on the TV engine (real bar data, real security resolution, pixel
rendering, live sessions) and cannot be proven locally. **Please run this matrix and
report any FAIL.** I have not marked Hash or Freeze as passing.

### 2.1 Hash + Freeze matrix (record STRUCT HASH and Freeze result in each cell)
Timeframes: **1m · 3m · 5m · 15m · 30m · 1H · 4H · 1D · 1W**
Markets × suggested tickers:
- **Crypto:** BTCUSDT, ETHUSDT, SOLUSDT
- **Forex:** EURUSD, GBPJPY, AUDUSD
- **Gold:** XAUUSD
- **Indices:** US100 (NAS100), SPX500, US30
- **Stocks:** AAPL, TSLA, NVDA

For each ticker × timeframe:
- [ ] Script loads with **no runtime error** (no RE10139/RE10110/RE10026).
- [ ] **Freeze test = PASS ✓** (needs ≥1000+ bars; on TFs with <1000 bars it reads
  "need 1000+ bars" — that is expected, not a fail).
- [ ] **STRUCT HASH stable** — unchanged on scroll/reload; note the value.
- [ ] Toggle a liquidity group on/off and confirm **STRUCT HASH does not change**
  (visual-only proof at runtime).

### 2.2 Replay-mode determinism
- [ ] On 1D and 4H, run Bar Replay; step forward — confirmed levels/labels **do not
  repaint or move**; Freeze stays PASS at each replay point.

### 2.3 Visual anchoring
- [ ] PDH/PDL start at the **previous day**; PWH/PWL at the **previous week**.
- [ ] Each session H/L line starts at the **candle where that extreme printed**.
- [ ] EQH/EQL start at the **earlier equal swing**; BSL/SSL at their swing candle.
- [ ] Change chart TF (e.g. 15m → 1H → 4H): each level's **price stays the same**;
  only the anchor candle resolution changes (never the price).
- [ ] No duplicate, missing, or misplaced lines; extend None/Left/Right/Both behave.

### 2.4 Session validation (set chart tz awareness in mind)
- [ ] London / New York / Asian / Sydney each plot their prior-session H/L at the
  correct wall-clock window; enabling Asian/Sydney adds them without shifting others.
- [ ] Verify on a symbol with real session structure (Forex EURUSD is clearest).

### 2.5 Visualization settings (per group: PrevDay, PrevWeek, Sessions, Equal, Swing)
- [ ] Show/Hide, Color, Style, Width, Transparency, Extend, Label on/off, Label size,
  Label position, Draw priority each behave and **never move the level price**.
- [ ] Parameter extremes (width 1 & 4, transparency 0 & 100, priority 1 & 10, every
  extend/style/size option) render without error.

---

## 3 · Status

- **Local deterministic validation: COMPLETE — 11/11 PASS.**
- **TradingView runtime validation: PENDING your confirmation** (matrix in §2).

The task is **not** marked complete for the runtime portion until you run §2 and
confirm. If any runtime cell fails, tell me the ticker + timeframe + error and I will
fix, re-run the local suite, and re-issue this report.
