# S/R Clarity + Power-Line + Sweep-Precision Sprint (v1 · 2026-07-12)

Sprint objective (user): **not more features — a cleaner chart, fewer but stronger
levels, and more trustworthy signals. Every displayed line must justify its
existence.** All changes here are **display / signal quality**; none touch the
level book, scores, or the STRUCT/DB hash — determinism (freeze/hash, non-repaint)
is preserved. Validated by `scratchpad/determinism_tests.py` (38/38) and
`pine_audit.py` (all files PASS).

---

## 1 · Chart Clarity — fewer, stronger, non-overlapping lines

New **Chart Clarity** input group (display-only). Three mechanisms, applied in
PASS 2 of `f_scoreAndRender` and a per-bar cross-store registry:

1. **Relevance-ranked budget.** The display budget is filled by **relevance =
   strength ÷ (1 + k·distance-in-Daily-ATR)** instead of raw score. So a small
   "Max Levels" shows the levels that matter *now* (near and strong), not distant
   high-score ones. This fixes both "75 % of lines are too far" and "reduce the
   count and the chart looks empty of relevant levels."
2. **Cluster de-dup.** A global registry of levels already drawn this bar (HTF
   stores render first) hides any level within `clusterATRk × Daily-ATR` of a
   stronger / higher-timeframe level already shown — nearby levels collapse to the
   single strongest representative.
3. **Hide-far.** Levels beyond `hideFarATRk × Daily-ATR` from price are hidden.

**Validated:** shown levels are never within the cluster distance; none beyond the
hide-far distance; distant high-score levels are dropped in favour of near+strong;
fewer lines than the raw book but never emptied; deterministic (same inputs → same
shown set). It is a **pure display filter** — a hidden level keeps its exact frozen
price and reappears unchanged, and the hash is untouched.

**How to use:** leave "Max Levels per Timeframe" generous (e.g. 12–20) and control
the chart with Chart Clarity — cluster distance, hide-far, and proximity weight.

---

## 2 · Power Line — one stable, highest-conviction reference

**Symptom:** the Power Line read a different price on 15m / 4H / 1D — unusable as
"the single highest-conviction institutional reference."

**Root cause:** the candidate floor was `max(4H, chartTF)`. 4H is a **sub-chart on
a Daily chart** and therefore **not populated** there, so a 15m chart (which does
populate 4H) and a 1D chart chose from **different candidate sets** → different
picks.

**Fix:** floor the candidate set at **Daily**. Daily/Weekly/Monthly are populated
on *every* chart at or below them, so the candidate universe — and the pick — is
**identical across 15m / 4H / 1D**. Verified: `{D, W, MN}` on all three; the old 4H
floor gave `{4H,D,W,MN}` on 15m vs `{D,W,MN}` on 1D (the divergence). Combined with
the incumbent-stickiness hysteresis already shipped, the Power Line is now one
stable, high-timeframe reference, and its label already carries the evidence
(side · score · distance-in-ATR · HTF bias · status).

*Full explainable **ICS number** on the Power label is R3 in the microstructure
audit — the current score is the interim conviction proxy; wiring the auction-aware
ICS is the next increment.*

---

## 3 · Liquidity-sweep audit — true vs false positives

**Old decision-engine test:** `sweep = big wick (> mWick ATR) AND within 0.5 ATR of
the nearest level`. This is a *proximity + wick* test only.

### False-positive classes it accepted (now fixed)

| Class | Why it's not a sweep | Old | New |
|---|---|:--:|:--:|
| **Continuation / breakout** | Big wick but the bar **closes through** the level (liquidity broken, not reclaimed) | ✅ flagged | ❌ rejected |
| **Weak rejection** | Pierces and closes back, but closes in the **upper half** (no rejection) | ✅ flagged | ❌ rejected |
| **No-reclaim drift** | Closed well past the level with no return | ✅ (if wick big) | ❌ rejected |

*(A "never-pierced" false positive turns out to be **geometrically impossible** for
the nearest level: a wick large enough to pass the size gate while price closes
within 0.5 ATR of the level must exceed it. So the real false positives are
close-through and weak-rejection — both now excluded.)*

### The precision fix

A sweep now requires, per Harris/O'Hara (liquidity is *taken* then price
**reclaims**): **(1) the wick PIERCES the level** (`high ≥ resPx` / `low ≤ supPx`),
**(2) the bar CLOSES BACK across it** (`close < resPx` / `close > supPx`), and
**(3) rejection** — the close sits in the far half of the bar's range. Confirmed-bar
only (non-repaint). Verified on 20 000 random bars: the new test accepts **only**
genuine pierce+reclaim bars; the true sweep is still accepted; both false classes
are rejected.

This tightens every consumer of `sweepRes/sweepSup`: the probability engine, the
`Liquidity Hunt` market state, sweep lines, and alerts — **precision before adding
any new liquidity features**, exactly as scoped. Sweeps are not in the hash, so
determinism is unchanged.

---

## 4 · What was intentionally deferred (stability-first)

- The full **Level Quality Engine as an explicit ICS number** (structural +
  liquidity + auction + effort/result) — this sprint delivers the *display*
  quality (relevance/cluster/hide-far) and the *selection* quality (Power Line);
  the runtime per-level ICS with reason codes is R3 from the microstructure audit,
  the natural next increment on this now-clean base.
- **Auction layer** (POC/VAH-VAL/single prints) — R1, the biggest remaining
  institutional-quality lift; gated behind the freeze/hash instrument.

## Verification summary

| Check | Result |
|---|---|
| `pine_audit.py` (delimiters, decl-before-use of 8 new clarity ids, shorttitle, bool-na) | ✅ all files |
| `determinism_tests.py` | ✅ 38/38 |
| Clarity: cluster spacing / hide-far / near-strong / deterministic | ✅ |
| Power Line: identical candidate set across 15m/4H/1D (Daily floor) | ✅ |
| Sweep: accepts only pierce+reclaim (20k random) | ✅ |
| No repaint / no future leak (lookahead_off only; confirmed-bar sweep) | ✅ |
| Book / scores / STRUCT+DB hash unchanged (display + signal only) | ✅ by construction |

On-chart gate (user): with Chart Clarity on, the chart shows a handful of near,
strong, non-overlapping lines; the ⚡ Power Line reads the **same** level on
15m/4H/1D of the same symbol; and sweep marks/`Liquidity Hunt` fire far less often
and only on genuine reclaims.
