# Equilibrium Lab — Findings (v1)

**Question:** Is equilibrium *dynamic* in a way that reveals auction intent **before**
conventional confirmation — i.e. do independent equilibrium lines (W/D pivot 2–14)
migrate together and get **respected** more than random chance explains?

**Data:** real BTC daily OHLC, 3,410 bars (Feb 2011 → Aug 2020), from a public GitHub
dataset. Non-repaint pivots, forward-respect measured 10 bars ahead (no lookahead).

**Method:** the effect (coherence gap, sequencing gap) is compared to a **40-shuffle
permutation null** (returns + intrabar offsets shuffled → same distribution, time-order
destroyed). Real must beat the 95th percentile of shuffles to count.

## Result (real vs 40-shuffle null)

| test | real | null (mean±sd) | > shuffles | verdict |
|---|---|---|---|---|
| coherence **TOUCH** gap | +7.4 | +4.6 ± 1.9 | **95%** | marginally beats null |
| coherence **HOLD** gap | +11.4 | +11.5 ± 2.0 | 52% | within noise |
| sequencing **TOUCH** gap | +5.4 | +9.4 ± 2.4 | 8% | **below** null |
| sequencing **HOLD** gap | +14.2 | +17.6 ± 2.2 | 5% | **below** null |

## Honest conclusion

- The **migration is real** (equilibrium genuinely relocates on new structure — that's
  mechanical, not disputed). What we tested is whether it carries a *predictive edge*.
- **Three of four metrics fail.** Coherence-HOLD is pure distribution; **sequencing is
  BELOW null** on both measures — the "higher-low stair-step" is *not* respected more
  than random; real BTC actually does it slightly *less* (trends get swept).
- **One flicker:** coherence-TOUCH beats 95% of shuffles (z≈1.5). BUT we ran **4 tests** —
  under the global null, seeing one at the 95th percentile happens ~18% of the time by
  chance (1 − 0.95⁴). After multiple-comparison correction, **it does not survive**.
- **Verdict: NOT PROVEN.** No robust evidence that equilibrium confluence predicts respect
  beyond what price distribution already explains. The single coherence-TOUCH thread is
  *suggestive, not significant* — worth chasing with more assets + out-of-sample, not
  worth trading.

## What would make it real (next passes)
1. Repeat on ETH, SOL, more assets — a real edge repeats across markets.
2. Out-of-sample: fit nothing, test on a held-out era.
3. Multiple forward windows (5/10/20 bars) — an edge shouldn't vanish at one horizon.
4. Correct for multiple comparisons up front.

**The win:** the method is honest and it protected us from trading a pretty story that
isn't there. The equilibrium family is a good *descriptive/visual* tool; as a *predictive*
edge it is unconfirmed.

---

# S/R Lab — Findings (v1)

**Data:** same real BTC daily (3,410 bars). Pivot L=5, 351 levels. Forward respect
10 bars, no lookahead. Nulls: random-levels (weak) + shuffled surrogate (strong) +
40-shuffle permutation.

| test | real | null | verdict |
|---|---|---|---|
| T1 levels vs RANDOM · TOUCH | 21% | 16% | beats random (but see below) |
| T1 levels vs RANDOM · HOLD | 83% | 46% | beats random |
| T1 vs SURROGATE · HOLD excess | — | — | **−4pt → mechanical, no real edge** |
| **T2 memory: held-before vs not** | **47% vs 27% (+19)** | **surrogate +8±3** | **beats 100% of shuffles ✓✓** |

## Honest conclusion
- **Test 1 is mostly a tautology.** A pivot low is a recent low, so "price holds above
  it" is baked in — the shuffled surrogate reaches the same HOLD rate. Beating *random
  lines* is true but trivial; there is **no edge over the strong null** here.
- **Test 2 is the real result.** A level that HAS HELD before is respected ~19pt more on
  its next touch, and the lift **exceeds the surrogate null (+8)** → a genuine ~+11pt
  excess that survives time-order destruction. **The engine's memory/scoring premise —
  "a proven level is a stronger level" — is real.**
- **Where the edge lives:** not in the existence of a pivot, but in its HISTORY. This
  validates the confidence-scoring direction and says the S/R engine's value is the
  *memory*, not the line.

## Caveats / next
Single asset (BTC), daily, one 10-bar horizon. Replicate on ETH/SOL and multiple
horizons before banking it. But unlike the equilibrium claim, this one **passed** the
strong control.

## Test 3 — confluence (placement)
HIGH confluence (>=3 of 5 pivot-lengths agree) HOLD 86% vs LOW 82% = +4pt, permutation
85th pct (n=42, underpowered) → **suggestive, NOT significant.** A lead to confirm with
more assets, not a confirmed feature. Do not bank it yet.

---

# HOW WE PERFECT THE ENGINE — the test-driven loop (the real trophy)

The equilibrium detour didn't fail — it built us a **fitness function that can't be fooled.**
From now on the S/R engine improves by a closed loop, never by opinion:

1. PROPOSE a change to how levels are placed/scored (e.g. weight confidence on held-count).
2. MEASURE it in the Lab on real data: respect rate + memory/confluence lift.
3. CONTROL it: it only counts if it beats the SHUFFLE SURROGATE (permutation p<0.05).
4. If it beats the null → PORT to the Pine engine. If not → discard, no matter how pretty.

CONFIRMED so far (safe to build on):
  • MEMORY is real (+11pt over null). Live rule: a level's strength should lean hard on
    its PROVEN HOLDS; a fresh untested level starts weak and earns trust by holding.
LEADS (need more data before building):
  • CONFLUENCE placement (+4pt, not yet significant) — retest on ETH/SOL.
DISCARDED (proven not to help):
  • equilibrium migration as a predictor; raw "beats a random line" (mechanical).

The engine is no longer "we think this level matters." It is "this level has EARNED its
strength, measured, against a control." That is the victory.

---

# Cross-Ticker Honesty Test (v2) — the line you actually trade

Ran the Claude-Line (equilibrium) respect AND the memory lift on THREE tickers vs a
25-shuffle surrogate null, out-of-sample. research/cross_ticker.py.

| ticker | class | Claude-Line HOLD (real / shuffled / excess) | sig | memory lift (real / null) | sig |
|---|---|---|---|---|---|
| BTC | crypto | 51% / 53% / **−2** | no | +19 / +8 | **YES** |
| SOL | crypto | 48% / 50% / **−2** | no | +17 / +11 | no |
| EURUSD | forex | 60% / 70% / **−10** | no | +16 / +8 | **YES** |

## Two hard truths
1. **The Claude Line (equilibrium) has NO predictive edge on ANY ticker** — BTC, SOL,
   or forex. On all three, real ≤ shuffled. It is a *location/context* tool (premium/
   discount, fair value), NOT a bounce predictor. The "works on crypto, fails on forex"
   feeling is an illusion: it doesn't predict anywhere; forex just exposes it brutally
   (−10, worse than random) while crypto sits near chance (−2), which memory/selection
   makes *feel* like it works.
2. **Memory does NOT cleanly replicate.** Significant on BTC + EURUSD, but NOT on SOL.
   The +11pt BTC "victory" was **over-called** — it is real on some markets, absent on a
   high-vol alt. Direction is positive on all three, but it clears the bar on only 2/3.

## What this changes
- Trade the Claude Line as a MAP, never a trigger.
- The proven-holds factor stays in the score but is downgraded from "validated" to
  "confirmed on BTC/EURUSD, weak on SOL — needs per-asset calibration."
- The real, unshaken asset is the METHOD: we can now measure any idea per-ticker before
  believing it. Tonight it stopped us trusting a line that doesn't predict.

---

# Expectancy Backtest (v3) — CAN the S/R levels be traded? (the real test)

`research/expectancy_lab.py`. Full level population (every daily pivot, L=5), no
cherry-pick. A trade per level-touch; stop 0.5·ATR (=1R), target 2R, net of 0.05%/side.
Stratified proven-vs-untested; natural side vs trend-gated; vs random-entry null
(60-perm) + shuffle surrogate. Mean R per trade (break-even = 0).

| config | BTC | SOL | EURUSD |
|---|---|---|---|
| natural, ALL | −0.087R | +0.024R | −0.206R |
| trend-gated, ALL | −0.005R | +0.078R | −0.109R |
| **proven + trend** | **+0.034R** | **+0.086R** | **−0.072R** |

## Verdict: NO tradeable standalone edge
- Across 3 markets the levels are **break-even to losing** net of cost. Best case
  (proven + with-trend) is barely + on BTC/SOL, still − on EURUSD. Not tradeable alone.
- **The "beats random" green flag is a TRAP:** the random-entry null enters at random
  bars, but a pivot is a local extreme → beating it is the same Test-1 tautology. The
  honest control is the SHUFFLE SURROGATE, which returns **+0.4…+0.6R** while real ≈ 0 →
  **real market trends make level-entries WORSE than random-walk data.** Damning.

## Two real, keepable positives
1. **The score sorts money:** PROVEN beats UNTESTED in every row (the +11pt memory
   finding, now in R). The ranking separates better from worse — it just can't turn a
   losing base entry into a winner.
2. **Trend-gating always helps:** with-structure > natural side, every asset. Confirms
   trades should never be counter-trend (the Trade Card's counter-trend LONG was wrong).

## Bottom line
The S/R engine is a good MAP with a working RANKING — but the levels are NOT a profitable
entry on their own. Income needs the map PLUS a real trigger we don't yet have.
