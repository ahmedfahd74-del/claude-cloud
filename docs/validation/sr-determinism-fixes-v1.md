# S/R Determinism & Performance Fixes — v1 (2026-07-12)

Two changes from the S/R audit's S-tier (stability) list, delivered together:

1. **`sr_poc.pine`** — fix the RE10110 (40 s) timeout on 15 m **without changing a
   single hash or freeze-test value**.
2. **`sr_engine.pine`** — make the confluence score factor (the heaviest weight)
   **cross-timeframe invariant**, so the same level scores the same on 5 m and 1 h.

Every item below follows the required checklist: design, unit tests, historical
validation, edge cases, performance, integration. Pine cannot execute in this
container, so runtime confirmation on TradingView is called out explicitly where
it is the final gate; everything else is proven here with deterministic harnesses.

---

## Feature 1 — `sr_poc.pine` RE10110 timeout fix

### Design explanation

The prior plan blamed a linear `f_find` identity scan, but that code was already
gone: the union is now **cleared and rebuilt from the three frozen books on every
chart bar** (`Dp.clear() … f_ingest ×3`), and three O(union) hash scans
(`f_hash`, `f_wincount`, `f_whash`) also ran on **every** bar. On a 1 D chart the
4 H book is dropped (`use4 = false`) and daily/weekly history is small, so it
stayed under budget. On 15 m all three books are built and thousands of chart
bars each paid for a full rebuild **plus** three full hash scans — quadratic work
whose result is invisible on all but a handful of bars. That is the 40 s blow-up.

Two determinism-preserving cuts:

1. **Gate the hash scans to where they are read.** `dbHash`/`winLevels` are shown
   only in the HUD at `barstate.islast`; `wHash` is captured into `rA/rB/rC` only
   at three sample bars (`last`, `last-500`, `last-1000`). They now compute *only*
   on those bars (`… ? f_hash() : 0`). Same values everywhere they are consumed.
2. **Rebuild the union only when a source advanced.** `f_book` now also returns the
   HTF bar `time`; the caller rebuilds the union only when a *used* book's time
   changed (`ta.change`) — or on a sample bar, so the freeze test always sees a
   fresh union. Between HTF closes the frozen books are byte-identical, so the
   retained `var` union is exactly what an unconditional rebuild would produce.

Neither cut can change a hash: on the bars where a value is used, the inputs are
identical to before; on the bars we skip, the value was never read.

### Unit tests (`scratchpad/determinism_tests.py`, all PASS)

- **DB hash order-independence** — reordering 500 levels 200× never changes the
  hash; ingest order `W+D+4H == 4H+D+W`. (The hash is a commutative sum mod a
  prime, so union rebuild order is irrelevant — the property the fix leans on.)
- **Gated union == full-rebuild union on EVERY bar** — 2 600-bar simulation with
  random source changes: **0 mismatched bars**.
- **… on SAMPLE bars** (the freeze A/B/C bars): **0 mismatches**.
- **Bursty-then-quiet** edge simulation (all changes in the first 200 bars, then
  1 000+ quiet bars up to the sample bars): **0 mismatches** — proves the retained
  union never goes stale where it is measured.

### Historical validation

The freeze/replay test **is** the historical-determinism instrument: it hashes the
frozen window (levels born ≤ a fixed time cut) at `last`, `last-500`, `last-1000`
and asserts A = B = C. The fix forces a union rebuild on exactly those three bars,
so the test samples the same immutable set it did before. Prior on-chart result to
preserve: **1 D → DB HASH 17973606, Replay 17343419/…/… = PASS, 530 levels.**

### Edge-case testing

- **Chart TF == a source** (1 D): that source's `time` changes every bar ⇒ rebuild
  every bar ⇒ old behaviour, which was already fast. The `(useW/useD/use4 and …)`
  guards stop a *dropped* sub-chart book (whose clamped `time` ticks every bar)
  from forcing needless rebuilds.
- **First bar**: `barstate.isfirst` forces the initial rebuild.
- **`ta.change` = na on bar 0**: treated as no-change; covered by `isfirst`.

### Performance impact assessment

Per non-sample chart bar the work drops from **1 full union rebuild + 3 O(union)
hash scans** to **at most 1 rebuild, only when an HTF bar closed**. On 15 m that is
a 4 H rebuild ~every 16 bars, daily ~every 96, weekly ~every 672 — and **zero**
hash scans between the three sample bars. Order-of-magnitude less per-bar work on
exactly the low chart TFs that timed out; unchanged (already-fast) on 1 D.

### Integration testing

Structural audit (`scratchpad/pine_audit.py`, PASS): balanced delimiters,
`wTM/dTM/h4TM/srcChanged/sampleBar` all declared before use, no dangling `f_find`.
No `lookahead_on` (5× `lookahead_off`), no negative-offset/forward reads — no
repaint or future leak introduced. `rA/rB/rC` capture bars match `sampleBar`
exactly, so the HUD and freeze test read real values.

### Final gate (user, on TradingView)

1. 15 m no longer throws RE10110. 2. DB HASH unchanged vs 1 D (17973606).
3. Freeze test still PASS ✓ (A = B = C) on both 15 m and 1 D.

---

## Feature 2 — `sr_engine.pine` TF-native confluence

### Design explanation

The audit's top stability finding: level **identities** are cross-TF deterministic
(merge/break already use only the level's own-TF ATR), but **scores** were not,
because the confluence factor — `W_CONF = 0.24`, the single heaviest weight — used
a chart-dependent band:

```
atrRef = math.max(atrSafe, s.atrTF * 0.5)   // atrSafe = chart-bar ATR(14)
band   = atrRef * adMergeMult * 1.5          // adMergeMult = per-bar chart regime
```

Both `atrSafe` and `adMergeMult` grow with the chart timeframe, so the same level
counted a different number of neighbours (hence a different score) on 5 m vs 1 h —
the drift the Power Line had to absorb with a ±15 % tolerance. Fix: drive the band
from the level's **own-TF ATR and a frozen constant**, exactly like merge/break:

```
CONF_BAND_K = 0.75                           // frozen
atrRef = s.atrTF > 0 ? s.atrTF : atrSafe     // TF-native (chart-independent)
band   = atrRef * CONF_BAND_K
```

`atrRef` also feeds the equal-level tolerance (`atrRef * 0.2`), so that becomes
TF-native for free. `s.atrTF` comes from `request.security(…, ta.atr(14))` per TF
— identical on every chart.

### Unit tests (`determinism_tests.py`, all PASS)

- **OLD band varies across chart TFs** — a fixed scene scored 2 vs 6 neighbours on
  two chart contexts (the bug, reproduced).
- **NEW band identical across chart TFs** — same scene, 3 == 3.
- **NEW band invariant across 5 000 randomized chart contexts** (random `atrSafe`,
  `adMergeMult`): never differs.
- **OLD band demonstrably chart-dependent**: differed in **3 851 / 5 000** scenes
  (77 %) — quantifies what was broken.

### Historical validation

Confluence is now a pure function of chart-independent inputs (frozen level prices
+ own-TF ATR + frozen constant), so a historical replay yields the identical
confluence contribution on every chart TF by construction. On-chart confirmation:
the per-level score % for a given W/D/4H level should now read the same on 5 m,
15 m, 1 h, 4 H (the Power Line's `⚡` score should stop drifting between charts).

### Edge-case testing

- `s.atrTF == 0` (ATR not yet resolved / bar 1): falls back to `atrSafe` so the
  band is never zero-width — no divide/degenerate confluence.
- Sparse book (0–1 neighbours): count is trivially invariant (covered by the sweep,
  which includes empty neighbour lists).

### Performance impact assessment

Neutral. Same number of `f_nearCount` passes; only the band *value* changed
(one `math.max` and one multiply removed). No new loops, no extra state.

### Integration testing

Structural audit PASS: `CONF_BAND_K` declared before first use; delimiters
balanced; the change is local to `f_scoreAndRender` (confirmed by inspection — no
other reader of `atrRef`/`band`). Non-repaint posture unchanged (7× `lookahead_off`,
0× `lookahead_on`; scoring already runs in the two-pass, price-frozen structure).

### Honest scope — residual chart-dependence

This makes the **confluence** and **equal-level** components fully TF-invariant. The
touch/reaction/volume/sweep factors remain chart-driven because touch mass is
accumulated from **chart bars** in `f_touchUpdate` (a lower chart TF simply sees
more bars). Freshness is already ~wall-clock-invariant by construction. Full
byte-identical scores across TFs require building the touch book **inside**
`request.security` — the `sr_poc.pine` architecture — which is the tracked
convergence, not this increment. This change removes the largest, most-cited,
zero-cost-to-fix source of score drift.

---

## Verification summary

| Harness | Result |
|---|---|
| `pine_audit.py` — delimiters, decl-before-use, no dangling refs (both files) | ✅ PASS |
| `determinism_tests.py` — 9 property tests (hash commutativity, gated==full union, TF-native invariance) | ✅ 9/9 PASS |
| `lookahead_off` present / `lookahead_on` absent (both files) | ✅ 5 & 7 / 0 & 0 |
| Future-leak scan (negative/forward offsets in edits) | ✅ none |
| **TradingView runtime** (RE10110 gone; DB HASH unchanged; freeze PASS; score no longer drifts) | ⏳ **user to confirm on-chart** |

Harnesses live in the session scratchpad (models of the edits, not the repo build).
No S/R engine logic was rewritten beyond these two targeted, proven changes.
