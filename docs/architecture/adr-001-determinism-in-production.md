# ADR-001 · Determinism, Hash & Freeze Validation inside the Production Engine

**Status:** Accepted (increment 1 implemented) · **Date:** 2026-07-12
**Context owner:** S/R engine (`pine/sr_engine.pine`, IA-SR v2.1.1)

## Decision

Make `sr_engine.pine` the **single source of truth**. Move the determinism proof
(commutative identity **hash** + **freeze/replay** test) out of the standalone
`sr_poc.pine` and **into the production engine**, as a **read-only validation
layer** that observes the engine's real level identities without altering any
existing behaviour. Retire the POC to reference/testing status.

## Why the POC could not be the destination

On real instruments the POC failed in three ways (user-confirmed on ZECUSDT.P):

1. **Freeze FAIL on 1h** (A ≠ B = C, A = the live bar). Building a stateful `var`
   book *inside* `request.security` means the still-forming HTF bar returns a
   slightly different book on the realtime bar than on confirmed history — a
   realtime-security recomputation artifact.
2. **Runtime error on forex LTF.** `request.security("W"/"D"/"240", f_book())`
   replays the entire HTF history to build a `var` array; on deep-history forex
   LTF that exceeds TradingView's memory/time limits (RE10139/RE10110) *inside*
   the security call — unreachable from any chart-bar optimisation.
3. **Does not match v2.1.1.** The POC uses different detection (`ta.pivothigh`
   books) — it was a proof of concept, never a reproduction of the engine.

All three trace to one root: **doing stateful work inside `request.security` over
full history.** The production engine does not have this problem — its level book
is built on **chart bars** and capped at `MAXBOOK = 20`/timeframe.

## Design — the read-only identity log

A new **append-only identity log** runs parallel to the display book:

- Four integer arrays only — `detKey` (price in ticks, the frozen identity),
  `detSide`, `detTfC` (coarse TF code = `round(storeWeight·100)`), `detBirth`
  (`bar_index` at creation). **No lines, labels, or boxes** → negligible memory.
- **Fed from the single level-creation point** (`f_addLevel`, the `not dup`
  branch), so it captures exactly the identities the engine commits — and only
  when a swing/period-extreme actually confirms. Populated stores are those with
  `tfMin ≥ chartMin`, so the log holds the same HTF identities on every chart.
- **No `request.security` replay.** The HTF data was already fetched by the
  engine; the log just records the resulting identities on the chart bar.
- **Rolling-capped** (`DET_LOGCAP = 4000`) so memory is bounded on deep-history
  LTF. The cap comfortably exceeds the level count inside the freeze window
  (levels are created only on confirmations, a few hundred over 1200 bars), so
  the freeze window is always fully contained in the log.

### Two instruments over the log

- **DB HASH** — commutative sum `Σ (tickP·131 + side·17 + tfC·7) mod P` over the
  whole log. Order-independent, so rebuild/scan order is irrelevant.
- **HTF HASH** — the same over identities with `tfC ≥ 60` (4H/D/W/MN only). This
  is the **cross-TF-comparable** fingerprint: those timeframes are populated on
  every intraday chart, so the value should match across 5m/15m/1h/4h.
- **FREEZE A/B/C** — hash of `{identities born ≤ (last_bar − detWindow)}`, sampled
  at **three confirmed bars** (`last−1`, `last−501`, `last−1001`). Append-only +
  frozen identities ⇒ that set is immutable ⇒ A = B = C on a non-repainting
  engine. **Sampling on confirmed bars (not the live bar) fixes POC issue #1.**

## Key architectural consequences (trade-offs documented)

1. **Hashing the append-only log, not the live (evicted) book, is deliberate.**
   The display book evicts the weakest levels beyond `MAXBOOK`, and that eviction
   uses `score`, which is chart-influenced — a cross-TF *identity* leak if you
   hashed the live book. Hashing the append-only log makes the DB/HTF hash
   **immune to chart-dependent eviction** without changing eviction itself.
   *Trade-off:* the hash reflects "all identities detected," which can exceed the
   ≤20 currently drawn per TF. That is correct for an identity-determinism proof;
   it is not a count of visible lines. Documented in the HUD ("log/ drawn").

2. **Freeze test is a same-chart non-repaint proof; cross-TF parity is the HTF
   HASH.** `detBirth` is in chart bars (chart-dependent), so the freeze window is
   per-chart — exactly like the POC. Cross-TF equality is claimed only for the
   HTF HASH (TF-native identities), and only for the shared ≥4H subset.
   *Trade-off:* we do **not** claim byte-identical hashes across *all* chart TFs
   (a 1h chart also logs 1h-store levels a 4h chart never sees). Honest scope.

3. **Scores remain chart-influenced by design.** Touch mass accrues on chart
   bars. Determinism guarantees delivered here are: **stable identity** (prices
   frozen on creation), **stable confluence** (now TF-native, ADR follow-on to
   the CONF_BAND_K change), **no repaint**, **no future leak** — *not* identical
   scores across TFs. Full score parity would require rebuilding touch/scoring
   inside `request.security` — the POC path we are explicitly leaving. This is the
   single most important honesty boundary of this ADR.

4. **Read-only ⇒ zero risk to existing institutional features.** The layer only
   appends ints and draws one extra HUD table (`position.middle_left`, an unused
   corner). It cannot change levels, scores, ranking, the Power Line, trade plans,
   the journal, or alerts. This satisfies "preserve all existing features" and
   "stability has priority" — it is additive and inert.

## Verification (this increment)

Modelled in `scratchpad/determinism_tests.py` (Pine cannot run in-container):
- commutative hash order-independence;
- append-only freeze invariance under a rolling cap (freeze window ⊂ cap);
- confirmed-bar sampling avoids the live-bar artifact;
- structural audit (`scratchpad/pine_audit.py`): delimiters, decl-before-use of
  the new globals, no dangling refs; `lookahead_off` only; no forward offsets.

On-chart gate (user): DB/HTF HASH stable, HTF HASH matches across 5m/15m/1h/4h,
FREEZE test PASS on 1h and 1D, and **no change** to any existing panel/plan.

## Institutional roadmap — staged AFTER core stability

Per the directive, new institutional features (MSS, multi-order-block management,
breaker blocks, mitigation blocks, inducement, premium/discount arrays,
session/killzone awareness, stronger liquidity classification) are **deferred to
subsequent increments** and each will be gated by the same verification matrix
before merging. Rationale: they add *detection/state*, which is exactly where
repaint/instability/nondeterminism risk lives, and they cannot be runtime-tested
in this container. We land the determinism instrument first so that every future
feature can be regression-checked against the hash/freeze test on-chart. **If any
feature degrades stability, runtime, repaint, or determinism, it is paused until
the core is green.**

**Ordering rationale (trade-off):** shipping the validation harness *before* the
features is slower to visible institutional value but is the only way to detect a
determinism regression the moment a feature introduces one — which the directive
ranks above feature velocity.
