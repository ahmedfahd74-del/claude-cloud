# Institutional-Grade System Audit — v1 (2026-07-12)

Scope: the entire repository — 8 Pine engines, the FastAPI trading-OS backend
(23 Python modules), the Next.js frontend, shared packages, configs, and docs.
Method: static inspection of every module, compile checks, the deterministic
validation harnesses, and grep-verified wiring checks. **Nothing was assumed
correct; nothing that could not be executed here is claimed as verified.**
(The API's runtime behavior needs Postgres + a venv — not available in this
container — so runtime findings are code-level, marked accordingly.)

---

## 1 · Code integrity

| Check | Result |
|---|---|
| Python compile (all 23 modules incl. migrations, seed, smokes) | ✅ PASS |
| Pine structural audit (4 active engines: delimiters, indent, dup-globals, stray refs) | ✅ PASS |
| Pine deterministic harness (29 property/static checks) | ✅ PASS |
| Config invariants (`PAPER_TRADING_ONLY=true`, `LIVE_EXECUTION_ENABLED=false`) | ✅ present in env + hardcoded in responses |
| Module wiring (routes → services → repository) | ✅ imports resolve, DI is explicit |
| **Kill-switch wiring** (governance → execution) | ❌ **NOT ENFORCED — see §4-C1** |
| Runtime deps (fastapi etc.) | ⚠ not installed in this container — API not runtime-tested here |
| Legacy Pine files (`sr_engine`, `sr_fusion`, `sr_db_engine`, `fvg_proj`) | ⚠ superseded, unmaintained — archive or delete to avoid trading off stale logic |

**Will fail in production (code-level evidence):**
- **P1.** `GovernanceService`, `PaperExecutionService`, and `OpportunityRepository`
  hold ALL state in process memory (`self.orders: list`, singleton snapshots).
  A restart silently resets the kill switch to GREEN and erases every order,
  position, and event. DB models exist (`models.py`, 285 lines, migrations
  present) but the live services do not use them.
- **P2.** `place_paper_order` trusts `payload["price"]`/`qty` from the client with
  no validation against market data — a paper fill at any arbitrary price.
- **P3.** No auth on any route, including `POST /v1/governance/kill` and
  `/transition` — anyone who can reach the API can flip the company state.

## 2 · Institutional trading-rules audit (per-signal checklist)

Two signal-producing subsystems exist. Verdicts per required element:

| Requirement | Pine Setup Engine | Platform pipeline |
|---|---|---|
| Market regime detection | ✅ phase engine (Trending/Pullback/Compression/Accum/Dist/Expansion) | ⚠ `regime_fit` is a **hardcoded constant** in pods |
| Trend confirmation | ✅ weighted MTF bias (3·W+2·D+1·4H) + structure trend | ⚠ nominal only |
| Liquidity analysis | ✅ mapped pools (PDH/PDL/PWH/PWL/EQ/session/swing) + sweep validation | ❌ none |
| Volatility check | ✅ hard ATR floor gate | ❌ none |
| S/R context | ⚠ liquidity levels yes; the S/R engine is a separate script (fusion pending) | ⚠ static fields |
| Risk/reward calculation | ✅ R computed; target capped at 3R; R:R displayed | ⚠ targets are `base ± const` |
| Stop-loss logic | ✅ beyond sweep extreme + ATR buffer | ✅ `hard_stop` REQUIRED or HOLD (good gate) |
| Position sizing | ❌ **not possible in an indicator** — must live platform-side | ⚠ exists but flawed (§4) |
| Invalidation conditions | ✅ level-break / bias-flip / expiry — no immortal setups | ⚠ status machine only |
| Capital preservation first | ✅ hard gates precede any signal; NEUTRAL = no trade | ✅ REJECT paths + paper-only invariant (intent is right) |

**Verdict:** the Pine engine genuinely implements the checklist except sizing
(architecturally impossible in an indicator). The platform pipeline has the right
*shape* (Scan→Challenge→Risk→Rank→Allocate→Execute with reject paths at every
stage) but its analytical content is **placeholder**: pods derive candidates from
`len(asset)*10+100`, market adapters emit a synthetic linear price ramp, and
challenger confidences are constants (0.74/0.68/0.91). No production signal may
be taken from it in its current state.

## 3 · Strategy validation

- **Entry/exit/SL/TP/invalidation (Pine):** deterministic state machine
  (IDLE→SWEPT→TRIGGERED), 5,000 randomized transition tests + 3,000 trade-map
  math tests pass; confirmed-close-only (no intrabar repaint); every
  `request.security` is `lookahead_off` (verified by static scan — no look-ahead).
- **Trailing logic:** ❌ not implemented yet (spec §9.3 partial-at-1R/BE/trail is
  documented; only entry/SL/TP1/target are live). Management is manual today.
- **MTF confirmation:** ✅ weighted, W+D outranks D+4H (proven exhaustively).
- **Market structure / SMC:** ✅ close-based swings, internal/external, strong/weak,
  real-time BOS/CHoCH/MSS with origin→break anchoring, sweep+displacement quality.
- **Volume analysis:** ✅ rel-volume with range proxy where volume is absent.
- **Momentum filter:** ✅ ADX/EMA-slope trend-strength.
- **Overfitting risk:** ⚠ MEDIUM — ~30 tunable thresholds. Mitigated by ATR
  normalization + asset presets + frozen constants, but **no out-of-sample
  evidence exists** (spec Phase 9 validation was never run). Unmitigated until a
  stats module + cross-market replay pass exists.
- **Unrealistic signals:** volatility floor, expiry, cooldown dedupe, and
  confirm-window prevent most; platform-side, mock pods can emit any candidate —
  but the REJECT/HOLD gates and paper-only invariant contain them.

## 4 · Risk engine audit — the weakest area

| Control | Status |
|---|---|
| Max risk per trade | ⚠ exists (`base_risk=0.5%` × multipliers) but **equity is hardcoded `100000`** and a magic `×10` turns risk% into size — not a real sizing model |
| Max daily loss protection | ❌ **does not exist anywhere** (grep-verified) |
| Drawdown protection | ❌ the "drawdown multiplier" is a hardcoded `0.90` — never computed from actual PnL |
| Dynamic position sizing | ⚠ multiplies quality/regime/confidence, but on fake inputs and fake equity |
| Can reject bad trades | ✅ genuinely yes — REJECT/HOLD/REDUCE paths, `hard_stop` mandatory, allocation refused without approved review, execution refused without allocation |
| **Risk controls override signals** | ❌ **CRITICAL: the governance kill switch (GREEN/YELLOW/RED/BLACKOUT, `new_trade_allowed`, `size_haircut`) is never consulted by `place_paper_order` or `AllocationService`.** CLAUDE.md claims "kill-switch enforced at execution layer" — the code does not do it. In BLACKOUT, orders still fill. |

## 5 · AI system audit

**There is no live AI decision system.** Findings on what exists:
- The multi-agent design (SRAgent/StructureAgent/LiquidityAgent/EntryAgent/
  RiskAgent/LearningAgent/DashboardAgent) is a **documented plan**
  (`docs/architecture/agent-refactor-notes.md`) with correct principles (typed
  contracts, isolated responsibilities, risk overrides) — not implemented.
- `MemoryService` (journals, decision memory, policy queue) is a data layer, not
  an agent; consistent but in-memory (same persistence flaw as P1).
- Explainability: every pipeline stage returns reason codes (`risk_flags`,
  `reason`, `challenge_summary`) — the right pattern, ready for real logic.
- ⚠ One conflicting instruction found: CLAUDE.md's kill-switch claim vs. actual
  wiring (§4). Docs must never overstate enforcement — that is how a future
  agent (or human) trusts a control that isn't there.

## 6 · Backtesting & research validation

- **No backtesting engine exists** — platform or Pine. Nothing to validate.
- No fees, slippage, spread, or latency modeling anywhere.
- **What IS solid:** the determinism substrate a credible backtest needs —
  no look-ahead (`lookahead_off` everywhere, verified), no future leakage
  (confirmed-bar-only), reproducibility instruments (order-independent hashes,
  A=B=C freeze/replay tests, TradingView-runtime checklists in
  `docs/validation/`). Rare and genuinely institutional-grade discipline.
- Performance metrics: none computed anywhere (spec §13 stats module unbuilt).

## 7 · Institutional readiness score: **34 / 100**

Breakdown: signal engine (Pine) 7/10 · architecture & safety intent 7/10 ·
risk engine 2/10 · data pipeline 1/10 · execution realism 2/10 · AI layer 1/10
(plan only) · backtesting 0/10 · determinism/validation discipline 9/10 ·
persistence/ops 1/10 · docs/spec quality 8/10 — weighted for capital risk.

### CRITICAL (fix before anything else touches even paper capital)
- **C1 — Enforce governance at execution.** `place_paper_order` and
  `AllocationService.allocate` must check `new_trade_allowed` and apply
  `size_haircut`; BLACKOUT/RED must hard-reject. (~15 lines + tests.)
- **C2 — Persist state.** Governance snapshot, orders, positions, events →
  Postgres (models already exist). A kill switch that resets on reboot is not a
  kill switch.
- **C3 — Daily-loss + real drawdown guards.** Compute realized+unrealized PnL
  per day; breach → automatic governance transition (RED). Replace the
  hardcoded 0.90 with equity-curve-derived drawdown.
- **C4 — Fix sizing.** Real equity input, remove the ×10 multiplier, cap
  per-trade risk (e.g. ≤1%), portfolio-level concentration from actual positions.
- **C5 — Correct CLAUDE.md** so no doc claims an enforcement that code lacks.

### HIGH priority
- H1 — Auth on governance/execution routes; validate order price/qty against quotes.
- H2 — Real market-data adapter (even one free source) behind the existing
  interface; trust-grade the source honestly.
- H3 — Wire the Pine Setup Engine's signal (webhook alert → candidate) into the
  pipeline as the first real pod, replacing `len(asset)*10+100`.
- H4 — Pine Phases 6–8 (score/grade/killzones, dashboard, read-only stats).
- H5 — Trailing/BE management (spec §9.3) so management matches the spec.

### MEDIUM priority
- M1 — Backtest harness with fees/slippage models; out-of-sample + cross-market
  runs (spec Phase 9) to retire the overfitting risk.
- M2 — Archive the 4 legacy Pine engines out of `pine/`.
- M3 — Implement the Agent abstraction (typed contracts) per the existing notes,
  with RiskAgent structurally upstream of EntryAgent output.
- M4 — TradingView runtime matrix (hash/freeze across 9 TFs × 5 markets) — still
  pending user execution; local checks cannot substitute.

### Missing entirely for institutional quality
Reconciliation & audit-trail persistence · portfolio-level exposure/correlation
limits · data-quality monitoors (gap/staleness detection) · alerting/on-call ·
config management with signed changes · model/param versioning tied to results ·
compliance log (who changed what limit when).

---

*Upgrade sequencing recommendation: C1→C5 first (they are small and
capital-critical), then H2/H3 to make the pipeline real, then M1 before any
serious weight is put on strategy performance claims.*
