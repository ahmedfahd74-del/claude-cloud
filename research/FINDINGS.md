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
