# Cross-TF Database Fingerprint — evidence-driven identity proof (2026-07-15)

**Directive:** *Stop debugging the Power Line. Freeze all Power Line work and
prove that every chart timeframe produces an identical institutional candidate
database before any ranking occurs. Do not continue until the databases are
byte-identical.*

Power Decision ranking is **frozen** (no logic changed). This step replaces the
Power-candidate debug dump with a **database fingerprint** instrument that
answers one question with evidence, not hypothesis: *does the candidate database
itself differ across chart timeframes, or only the ranking on top of it?*

## The instrument (`f_storeFp`, temporary)

For every store (MN, W, D, H4, H1, M15, M5) it computes an **order-independent
(commutative) hash of the entire level book** and renders a centered table:

| Column | Meaning | Must match across chart TFs? |
|---|---|---|
| `live` | count of unbroken levels | **yes** (HTF rows) |
| `brk` | count of broken-and-kept levels | **yes** (HTF rows) |
| `idHash` | commutative hash over `(priceTick, type)` — the **frozen identity** | **YES — byte-identical** |
| `scHash` | commutative hash over `(priceTick, round(score))` — chart-**influenced** | may differ (documented) |

Footer `HTF-BOOK` = combined D+W+MN `idHash` and total live count: the single
number that must be identical on 15m / 1H / 4H / 1D. `ref` echoes `dRef`
(already confirmed identical).

Hash: `h := |(h + tickP·131 + type) mod 99999989|` accumulated over the book —
summation is commutative, so internal array order (which differs by rebuild path)
cannot change the result. Proven in `determinism_tests.py`.

## Why split idHash from scHash

The book **identity** (which price levels exist, and their support/resistance
type) is frozen and *should* be chart-independent. The **score** is honestly
chart-*influenced* (touch mass accrues on chart bars — documented in ADR-002 /
I1). Splitting the two hashes localizes any divergence on sight:

- **idHash or counts differ** → the *book itself* diverges (detection / eviction
  / floor). This is the real root cause the directive is hunting, and it lives
  **upstream of all ranking**.
- **idHash matches, only scHash differs** → the book is identical; divergence is
  the chart-influenced score, not the candidate database.

Either way the screenshot is now decisive: it points at book-build or at score,
never at "the Power Line."

## Validation

| Check | Result |
|---|---|
| `pine_audit.py` (delimiters, decl-before-use incl. `f_storeFp`/`showDbFp`, arg-parity) | ✅ all files |
| `determinism_tests.py` | ✅ all pass (incl. 4 new fingerprint properties) |
| storeFp: same book any order → identical fingerprint (2k shuffles) | ✅ |
| storeFp: one-tick / flipped-type difference changes idHash (divergence visible) | ✅ |
| storeFp: idHash independent of score (book isolated from chart-influenced ICS) | ✅ |
| Power Decision / book / identity logic changed | ❌ none — display-only instrument |

## Next — user action (evidence collection)

Load the engine, screenshot the centered fingerprint table on **15m, 1H, 4H,
1D** (same symbol). Compare the **D / W / MN rows and HTF-BOOK**:

1. **All idHashes + counts + HTF-BOOK match across all four charts** → the
   candidate database is proven byte-identical. We then rebuild the Power Line on
   this verified foundation, and any residual scHash drift is the known
   chart-influenced score (addressed separately).
2. **They differ** → we have located the true root cause in the book build
   (detection / eviction / TF floor), upstream of ranking, and fix *that* — not
   the Power Line.

Instrument is temporary (`showDbFp`, default on); removed once identity is proven.
