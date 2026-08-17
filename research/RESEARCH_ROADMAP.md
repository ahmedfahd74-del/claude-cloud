# RESEARCH ROADMAP — what deserves testing, and how

## 0. THE PROTOCOL (binding, from now on)

Every proposed edge is a **falsifiable hypothesis**. Before ANY of it touches the engine,
we write down, up front:

1. **Claim (H1)** — the exact predictive statement, in numbers.
2. **Null (H0)** — what "no edge" looks like (usually a shuffle-surrogate or random-entry
   control that keeps the price distribution but destroys the thing being claimed).
3. **In-sample vs out-of-sample** — what we're allowed to fit on, and the held-out data
   the claim must survive *without refitting*.
4. **Reject-if** — the result that kills the idea. Written BEFORE we look.
5. **Metric** — and it must be the RIGHT one: **expectancy (R-multiple), not hit-rate**,
   whenever the thing is used to place trades. "Does price bounce" ≠ "is it tradeable."

No integration without a passed test. No "it looks right." The Lab decides.

## 0.1 Descriptive vs Predictive (the distinction that cost us last night)

- **Descriptive** components *describe state* — they make no forward claim, so testing them
  as predictors is a category error. They earn their place by *conditioning* other signals
  or *placing risk*, not by beating a null on direction.
- **Predictive** components *claim the future* — they must beat a null or they're decoration.

Classify first. Then only null-test the predictive claims.

---

## 1. COMPONENT LEDGER

| # | Component | Role | Type | Status |
|---|---|---|---|---|
| A | Location / Claude Line (equilibrium, premium/discount, zone state) | where price sits in the range | **Descriptive** | **TESTED → fails as predictor** (BTC/SOL/EURUSD, no edge). Valid only as location/conditioner. |
| B | S/R memory (proven-holds scoring) | rank levels by history | Predictive | **TESTED → partial** (BTC/EURUSD sig, SOL not). Needs basket replication. |
| C | Market Structure (BOS / CHoCH / MSS, trend, phase) | what structure price is making | Mixed (labels descriptive, events predictive) | **UNTESTED** predictively. Logic-validated only. |
| D | Context (BTC leads alts · TOTAL2 tide · RS) | external environment / direction | Predictive | **UNTESTED**. Highest prior of a real edge. |
| E | Position Layer (HTF 2/3 bias, market state) | HTF trend bias | Predictive | **UNTESTED**. (It's trend-following in disguise.) |
| F | Liquidity (sweeps, equal H/L, prev H/L) | what price reaches for | Predictive | **NOT BUILT + UNTESTED**. Do not build until tested. |
| G | Execution / M4 (sweep→BOS→entry/stop/target) | the actual trade | Predictive | **UNTESTED** as a system. This is the one that measures MONEY. |
| H | Risk / Governance (kill-switch, sizing, state machine) | capital protection | Control (not an edge) | N/A for edge-testing. Sizing overlays testable later. |

---

## 2. HYPOTHESIS CARDS (the testable ones)

### D — Context: BTC leads alts  ★ top priority (highest prior)
- **H1:** BTC's return over the last k bars predicts an alt's next-bar return, beyond the
  contemporaneous correlation. (Also: alt-long setups taken while BTC-bullish out-expect
  BTC-bearish ones.)
- **H0:** shuffle BTC's return series → any lead-lag predictive power vanishes.
- **In/out:** fit lag k on one pair (BTC→SOL), test unchanged on BTC→{ETH, others}.
- **Reject-if:** lagged predictive excess ≤ null on the held-out pairs.
- **Data:** **INTRADAY** (1h or finer) BTC + alts, timestamp-aligned. ⚠ *daily lead-lag ≈ 0
  — the lead lives in minutes/hours.* **DATA GAP.**

### G — Execution/M4 expectancy  ★ measures what matters
- **H1:** the full M4 setup (sweep → internal BOS → entry, with its stop/target geometry)
  has positive expectancy in **R-multiples**, after costs.
- **H0:** random entries with the SAME stop/target geometry and frequency (surrogate).
- **In/out:** tune nothing new; test the shipped rules across a ticker basket + eras.
- **Reject-if:** expectancy ≤ null, or ≤ 0 after realistic fees/slippage.
- **Data:** **1–5 min** OHLC, multi-ticker. Partial (have 1-min BTC; need alts). **GAP.**
- *This also rescues (or buries) the Claude Line as a **risk anchor** rather than a predictor.*

### F — Liquidity: sweep-reversal
- **H1:** price that sweeps a prior swing high (wicks past, closes back) has negative
  forward return over N bars (a liquidity grab → reversal); equal highs/lows get hit more
  than random levels.
- **H0:** random wicks / random levels, same frequency (surrogate).
- **In/out:** define sweep on BTC, test on alts + forex unchanged.
- **Reject-if:** forward excess ≤ 0 vs null.
- **Data:** OHLC, intraday preferred. Partial.

### C — Structure: BOS/CHoCH continuation
- **H1:** a confirmed BOS in trend direction is followed by positive forward return
  (continuation) vs null; an MSS is followed by a reversal.
- **H0:** same-count entries at random bars (surrogate), same holding period.
- **In/out:** no params to fit; test across basket.
- **Reject-if:** forward excess ≤ 0 / not significant on the basket.
- **Data:** OHLC multi-ticker (intraday for LTF structure). Mostly HAVE (daily).

### E — Position Layer: HTF bias
- **H1:** when 2/3 HTFs agree BULL, forward return over the horizon is positive vs null.
- **H0:** shuffle the bias labels / random-time entries.
- **Reject-if:** not significant across basket (this is trend-following; expect weak).
- **Data:** multi-ticker daily/HTF. HAVE.

### B — S/R memory: finish the job
- **H1:** proven-holds lift > null across a basket of ≥8 tickers (not cherry-picked).
- **H0:** shuffle surrogate per ticker.
- **In/out:** curve fit on BTC (done); test unchanged on 8 others.
- **Reject-if:** significant on < ~60% of the basket → demote/remove from the score.
- **Data:** 8–10 tickers daily OHLC. Mostly HAVE (need a few more).

### A — Location: only as a conditioner
- **H1:** signals taken in discount out-expect the same signals in premium (location
  conditions, it doesn't trigger).
- **H0:** location label has no effect on the forward-return distribution.
- **Reject-if:** no expectancy difference by location bucket.
- **Data:** whatever the conditioned signal uses. HAVE.

---

## 3. DATA INVENTORY (honest)

**Have (daily OHLC, via reachable GitHub):** BTC 10y · SOL 3.7y · EURUSD + ~10 forex pairs ·
+ 29 BTC on-chain daily metrics (netflow, MVRV, etc.).
**Have (minute):** 1-min BTC (Bitstamp 2012–2020, Coinbase).
**Gaps that block the top priorities:**
- **Intraday, timestamp-aligned BTC + several alts** (for D lead-lag and G/F execution).
  This is THE data to source next — most edges live intraday, not daily.
- A few more daily alts (ETH etc.) for the B basket.

## 4. PRIORITY (my honest prior — a prior, not a promise)

1. **D · BTC-leads-alts** — best chance of a real edge; needs intraday data first.
2. **G · M4 expectancy (R-multiples)** — tests money, reframes levels as risk anchors.
3. **F · liquidity sweep-reversal** — classic, cleanly testable.
4. **C · structure continuation** — testable, moderate prior.
5. **B · memory basket** — finish/settle what we started.
6. **E · HTF bias** — weak-but-maybe trend-following.
7. **A · location as conditioner** — descriptive; only ever a conditioner.

**Next decision (no build):** either (a) source intraday aligned multi-ticker data so #1/#2
become possible, or (b) run #3/#5 now on the daily data we already have. Pick the gate, then
we write the hypothesis card in full and only THEN touch the Lab.
