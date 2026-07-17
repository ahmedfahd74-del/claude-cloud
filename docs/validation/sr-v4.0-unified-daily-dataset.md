# v4.0 — UNIDATA: one deterministic reference dataset for every timeframe

## The problem this closes for good

The reference levels and the Power Line are built from a fixed set of institutional
anchors — prev/current **Day, Week and Month** highs & lows. Through v3.9 those anchors
came from **three separate `request.security` calls** (`"D"`, `"W"`, `"M"`).

That is the source of the recurring MTF divergence. On a shallow intraday chart
(15m / 5m / 1m) TradingView back-loads each of those three series to a **different
calendar depth**. The Daily series loads deep on every chart — which is exactly why
"previous-month-high" tools work on a 1m chart — but a separate `"W"` / `"M"` request
can be back-loaded shallower, so a **prior-week or prior-month extreme that exists on a
4H chart can be missing (or truncated) on a 15m chart**. Different inputs per chart →
different clusters → different lines. No downstream patch can fix it, because the
*datasets themselves* differ before any ranking runs.

The Power Line already survived (it is Daily-dominated and the Daily anchors always
load), which is why ⚡ 530.44 was byte-identical across TFs while the weaker secondary
reference lines (548.89 vs 555.03) drifted. Same root cause, different symptom.

## The redesign — read from ONE Daily dataset

**Collapse to a single Daily fetch and derive Weekly & Monthly from the Daily bars.**

`f_refData()` is evaluated in the **Daily** context by one `request.security(…, "D", …)`
and returns all twelve anchors:

- **Day** — `high[1]/low[1]` (prior), `high/low` (current).
- **Week** — a running high/low that **resets on each new ISO week**
  (`ta.change(weekofyear)`), yielding prior-week and current-week extremes.
- **Month** — a running high/low that **resets on each new calendar month**
  (`ta.change(month)`), yielding prior-month and current-month extremes.

Plus the prior Daily close (`nDref`), the native Daily ATR (`nDatr`), and the last-8
Daily extreme arrays (`dHiE/dLoE`) that feed the touch count.

Because a Daily series back-loads to the **same deep history on every chart timeframe**,
the Weekly/Monthly extremes derived from it are identical on 1m → 1M. Everything
downstream (clustering, zones, Power, reference lines, Level Adjustment) is a pure
function of these twelve numbers, so **the readings are identical on every timeframe by
construction** — a per-chart dataset can no longer exist. Weekly/Monthly context is
**kept in full**; only its *source* changed from three fragile requests to one robust one.

Performance is also better: three security calls → **one**.

## Proof on the chart — the DS fingerprint

`f_anchorHash()` hashes the twelve anchors (each quantised to `mintick`) into a small
integer shown **bottom-right beside the BUILD** as `DS <n>`. Because the anchors are all
Daily-derived, this fingerprint is identical on every chart timeframe.

**How to verify:** put the indicator on 1m and on 1D. The `DS` number must match. If it
ever differs, the dataset itself diverged — the only thing that can move a reading across
TFs — and you can see it at a glance instead of guessing.

## What did not change

- Level identity / selection / clustering / ICS / freeze / STRUCT-hash logic: untouched.
- `PAPER_TRADING_ONLY` / `LIVE_EXECUTION_ENABLED`: untouched.
- The touch count was already Daily-only (v3.9.1); `f_bestTouch` is now Daily-only too,
  consistent with it (the Weekly/Monthly *extreme arrays* were the only thing removed —
  Weekly/Monthly *anchors* remain, now Daily-derived).

## Validation

| Check | Result |
|---|---|
| `pine_audit.py` (all files) | ✅ |
| `determinism_tests.py` (all properties) | ✅ |
| derived anchors identical across chart depth (1m ↔ 1D) | ✅ |
| DS fingerprint identical across chart depth | ✅ |
| derived dataset identical in 2000 fuzzed feeds | ✅ |
| reproduces the OLD separate-request divergence (prior-month truncation) | ✅ |
| a one-tick anchor move changes the DS fingerprint (divergence stays visible) | ✅ |

## User verification (BUILD `v4.0.0-UNIDATA`)

Remove the old indicator instance and re-add this build (bottom-right must read
`v4.0.0-UNIDATA · 2026-07-17`). Then, on **BTC / ETH / SOL / ZEC / EURUSD / GBPUSD /
XAUUSD / NAS100 / US30**, compare 1m, 15m, 1H, 4H, 1D:

1. The `DS` fingerprint must be the **same number** on every timeframe.
2. The reference lines and ⚡ Power price must read the **same** on every timeframe.

If the `DS` numbers match but a *line count* differs between two chart windows, that is
purely a **display setting** difference (Max Reference Lines / Min Touches / Show
Liquidity), not a dataset divergence — the fingerprint makes the distinction unambiguous.
