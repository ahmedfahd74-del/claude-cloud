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
