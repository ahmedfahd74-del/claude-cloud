# Phase 1 — Cross-TF book identity (chart-independent age + pure recency) (2026-07-15)

Follows the database-fingerprint proof (`sr-database-fingerprint-v1.md`), which
showed with live evidence that the candidate database was **not** byte-identical
across chart timeframes. Two root causes were localized from the fingerprint
tables (BTCUSDT, same symbol, four chart TFs):

| Chart TF | D live | D idHash | HTF-BOOK idHash |
|---|---|---|---|
| 1m | 17 | 27098443 | 98712275 |
| 1H | 20 | 62524896 | 86086944 |
| 4H | 20 | 37000497 | 50361556 |
| 1D | 20 | 37025939 | 52699149 |

Note the Daily store: **equal count (20) on 1H/4H/1D, three different hashes** —
so the *set* of retained levels differed, not just how many. That isolates the
cause to **eviction**, not detection.

## The two mechanisms (evidence-driven)

1. **`birthT` was the chart bar-time at ingestion, not the pivot's own time.**
   Age-based eviction ("keep newest-N") therefore ranked levels by *when this
   chart happened to ingest them*, which differs per chart TF.

2. **Structural-extreme protection pinned a chart-dependent level.** Eviction
   exempted the current highest/lowest price. A deeper-history chart sees a
   *different* all-time extreme and protected it forever → equal count, different
   set (exactly the Daily-store signature above).

Both are **eviction-only** concerns. Level identity (price + type), the
STRUCT/DB hash, and the freeze proof are untouched — `birthT` is not hashed — so
this change is determinism-safe by construction.

## The fix (v2.5)

- **Chart-independent age.** `f_htfPack` now carries each pivot's own HTF bar-time
  (`time[leg]`, since the pivot sits `leg` bars back) alongside its price, through
  the 7 `request.security` calls, into `f_addLevel(..., birthTime)`. `birthT` is
  now the pivot's time, identical on every chart TF that sees that pivot.
- **Pure-recency eviction.** Removed the highest/lowest-price protection. Eviction
  is now: broken levels first, then strictly the oldest surviving level by pivot
  time; index 0 (the just-added level) is never evicted. Prev-period extremes
  (PDH/PWH/PMH) are re-added every period, so major reference levels persist as
  recent regardless.

Result: **any two chart TFs that see the same newest-MAXBOOK pivots hold a
byte-identical book.** For the Daily/Weekly stores this covers 1H/4H/1D (all load
enough history to see the same recent pivots); Monthly is identical on 4H/1D and
near-identical on 1H.

## The residual (physical limit, → Phase 2)

Very low chart TFs (1m/5m/15m) load too few calendar days to *see* the same deep
HTF pivots at all (the 1m Daily store held only 17 vs 20). No eviction rule can
conjure history a chart never loaded. Phase 2 addresses the **Power Line**
identity down to 1m by drawing its candidate pool from **fixed institutional
anchors** (prior day/week/month high/low/close) — each a single `request.security`
value available on every chart TF — rather than the depth-limited pivot book.

## Validation

| Check | Result |
|---|---|
| `pine_audit.py` (delimiters, decl-before-use incl. new time ids, arg-parity via 25 `f_addLevel` sites) | ✅ all files |
| `determinism_tests.py` | ✅ all pass |
| extreme-protection model → books DIVERGE at equal count (reproduces measured bug) | ✅ |
| pure-recency model → books IDENTICAL across depths | ✅ |
| pivot-time birth is chart-independent | ✅ |
| identity / DB hash / freeze inputs changed | ❌ none (birthT not hashed) |

## Next — user verification

Reload (BUILD now **`v2.5-DBFP`**). Screenshot the fingerprint table on 1H / 4H /
1D and confirm the **D and W idHashes + counts now match** across those three
charts (MN should match on 4H/1D). Once confirmed, Phase 2 rebuilds the Power Line
on fixed institutional anchors for identity down to 1m.
