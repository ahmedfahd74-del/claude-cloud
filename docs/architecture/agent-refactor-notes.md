# Future refactor — Agent abstraction layer (deferred, for TradeAgentFramework)

> Captured on request. **Do NOT start until the Pine event-database build is
> finished.** This is a Python-engine architecture refactor, not a trading-logic
> change.

## Intent
Keep the current scanner/engine behaviour **exactly as-is** (no trading-logic
change). Introduce an abstraction layer so every major subsystem becomes an
**independent, independently-testable Agent** with defined typed inputs and
outputs, communicating only through typed data objects. This lets us later swap
in **TradeAgentFramework** without rewriting the trading engine.

## First-version agents
- **SRAgent** — the S/R level database (wraps the frozen level engine).
- **StructureAgent** — BOS / CHoCH / market structure.
- **LiquidityAgent** — sweeps / liquidity events (Institutional Event DB).
- **EntryAgent** — entry model / signal generation.
- **RiskAgent** — sizing, risk gates, kill-switch.
- **LearningAgent** — journals, decision memory, review/learning loop.
- **DashboardAgent** — read-only presentation/reporting.

## Rules
- Refactor **architecture only** — do not change trading logic or the methodology.
- Each agent independently testable in isolation.
- Agents communicate through **typed data objects** (contracts), not shared state.
- Target: drop-in compatibility with TradeAgentFramework once complete.

## Sequencing
1. Finish Pine event database (Sweep ✓ → BOS → CHoCH → FVG → Order Block → …).
2. Then do this Agent refactor as its own phase in `intelligence/`.
