# Intraday dataset — spec, provenance, quality (acquisition only, no analysis)

## Requirements (defined BEFORE download)
- **Assets:** BTC + an alt (ETH / SOL), USDT-quoted.
- **Exchange:** single source → native timestamp alignment (no cross-exchange roll skew).
- **Timeframe:** 1h (lead-lag lives intraday; 1h keeps OOS-sized history sane).
- **History:** ≥ 2 yrs overlapping, enough to hold out an out-of-sample era.
- **Grid:** UTC hourly, strictly increasing unique timestamps.
- **Columns:** ts_utc, open, high, low, close, volume.
- **Alignment:** inner-join on the common UTC hour; log dropped/gap bars.
- **OOS split:** reserve most-recent ~35% as held-out, fit nothing on it.

## Acquired (v1) — BTC + ETH 1h
- **Source:** Binance spot klines (BTCUSDT, ETHUSDT), committed plain-CSV in the public
  repo `lth-elm/Backtrading-Python-Binance` (`/data/*-1h.csv`). Single exchange → aligned.
- **Coverage:** 29,309 hourly bars each, **2017-08-17 → 2020-12-25 UTC**.
- **Quality:** inner-join = 29,309 (0 dropped either side — perfectly co-timed, same source).
  Hourly-spacing breaks (gaps): 21 (**0.07%**). No zero/negative prices; high ≥ low enforced.
- **OOS split (suggested):** in-sample 2017-08-17 → 2019-10-23 · **held-out 2019-10-23 → 2020-12-25**.
- **Files:** `btc_eth_1h_aligned.csv` (merged), `btc_1h.csv`, `eth_1h.csv`.
- **Why BTC→ETH first:** it is the canonical lead-lag pair; a real "BTC leads alts" effect
  must show here before anything exotic.

## Gaps / not yet acquired
- **SOL intraday:** SOL did not trade until ~2020, so it is absent from this 2017-2020 set.
  A SOL test needs a **2021→present** trio (BTC+ETH+SOL 1h, same source) — a separate pull.
- **Recent era (2021→2025):** the current set ends 2020; a fresher pull would add a second,
  independent out-of-sample era and enable SOL. Recommended next acquisition.

## Access notes (for reproducibility)
- Crypto exchange APIs and `data.binance.vision` are **blocked** by egress policy (403).
- git-LFS media is **gated** (LFS batch API denied) → only PLAIN committed CSVs are usable.
- Plain public GitHub repos clone fine; that is the working data channel here.
