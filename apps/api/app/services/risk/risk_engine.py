"""Institutional risk engine — the LAST gate before any order is sized or placed.

Capital preservation before profit. Every check here can only REDUCE or REJECT;
nothing here can enlarge a trade. The engine is a pure state machine over risk
config + live account state, so it is deterministic and unit-testable without a
database. (State persistence to Postgres is the next increment; today the engine
holds live state in memory but exposes snapshot()/load() so a repository can
hydrate it.)

Controls (all configurable, institutional defaults):
  * max risk per trade          — cap on $ risked per position
  * max daily loss              — realised+unrealised loss for the session → halt
  * max drawdown                — equity vs high-water-mark → halt
  * equity-based position sizing — size = (equity * risk%) / stop_distance
  * portfolio exposure limits   — per-symbol and total gross exposure caps
  * max concurrent positions
Risk controls OVERRIDE strategy signals: a rejection here is final regardless of
how good the setup looked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

Verdict = Literal["APPROVE", "REDUCE", "REJECT"]

D0 = Decimal("0")


def _d(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


@dataclass
class RiskConfig:
    starting_equity: Decimal = Decimal("100000")
    max_risk_per_trade_pct: Decimal = Decimal("0.010")   # 1% of equity at risk / trade
    max_daily_loss_pct: Decimal = Decimal("0.03")        # 3% session loss → halt new trades
    max_drawdown_pct: Decimal = Decimal("0.10")          # 10% peak-to-trough → halt
    max_symbol_exposure_pct: Decimal = Decimal("0.20")   # 20% gross per symbol
    max_total_exposure_pct: Decimal = Decimal("1.00")    # 100% gross (no leverage default)
    max_open_positions: int = 8
    min_stop_distance_pct: Decimal = Decimal("0.0005")   # reject nonsensical (<0.05%) stops


@dataclass
class RiskState:
    equity: Decimal = Decimal("100000")
    day_start_equity: Decimal = Decimal("100000")
    high_water_mark: Decimal = Decimal("100000")
    realised_day_pnl: Decimal = D0
    # symbol -> gross market value currently open
    exposure: dict[str, Decimal] = field(default_factory=dict)
    open_positions: int = 0


class RiskEngine:
    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        eq = self.config.starting_equity
        self.state = RiskState(equity=eq, day_start_equity=eq, high_water_mark=eq)

    # ── live-state accounting ────────────────────────────────────────────────
    def start_new_day(self) -> None:
        self.state.day_start_equity = self.state.equity
        self.state.realised_day_pnl = D0

    def mark_to_market(self, equity: Decimal) -> None:
        self.state.equity = _d(equity)
        if self.state.equity > self.state.high_water_mark:
            self.state.high_water_mark = self.state.equity

    def register_fill(self, symbol: str, market_value: Decimal) -> None:
        self.state.exposure[symbol] = self.state.exposure.get(symbol, D0) + _d(market_value)
        self.state.open_positions += 1

    def register_close(self, symbol: str, market_value: Decimal, realised_pnl: Decimal) -> None:
        remaining = self.state.exposure.get(symbol, D0) - _d(market_value)
        if remaining <= D0:
            self.state.exposure.pop(symbol, None)
        else:
            self.state.exposure[symbol] = remaining
        self.state.open_positions = max(0, self.state.open_positions - 1)
        self.state.realised_day_pnl += _d(realised_pnl)
        self.mark_to_market(self.state.equity + _d(realised_pnl))

    # ── halt conditions (portfolio-level; independent of any single trade) ────
    def drawdown_pct(self) -> Decimal:
        hwm = self.state.high_water_mark
        if hwm <= D0:
            return D0
        return (hwm - self.state.equity) / hwm

    def daily_loss_pct(self) -> Decimal:
        base = self.state.day_start_equity
        if base <= D0:
            return D0
        loss = base - self.state.equity
        return loss / base if loss > D0 else D0

    def halt_reason(self) -> str | None:
        if self.daily_loss_pct() >= self.config.max_daily_loss_pct:
            return "daily_loss_limit_reached"
        if self.drawdown_pct() >= self.config.max_drawdown_pct:
            return "max_drawdown_reached"
        if self.state.open_positions >= self.config.max_open_positions:
            return "max_open_positions_reached"
        return None

    def total_exposure(self) -> Decimal:
        return sum(self.state.exposure.values(), D0)

    # ── the gate ─────────────────────────────────────────────────────────────
    def size_and_check(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_price: Decimal,
        *,
        size_haircut: Decimal = D0,
        quality_mult: Decimal = Decimal("1"),
    ) -> dict:
        """Return a sizing decision. quality_mult (0..~1.4) scales within the risk
        budget; size_haircut (0..1, from governance YELLOW/RED) shrinks it. The $
        risked can never exceed max_risk_per_trade regardless of multipliers."""
        cfg = self.config
        entry = _d(entry_price)
        stop = _d(stop_price)

        # 0 · portfolio halts win over everything
        halt = self.halt_reason()
        if halt is not None:
            return self._reject(halt)

        # 1 · sane inputs
        if entry <= D0 or stop <= D0 or entry == stop:
            return self._reject("invalid_entry_or_stop")
        stop_distance = abs(entry - stop)
        if stop_distance / entry < cfg.min_stop_distance_pct:
            return self._reject("stop_too_tight")

        # 2 · risk budget (equity-based), then quality + governance haircut
        hc = max(D0, min(_d(size_haircut), Decimal("1")))
        if hc >= Decimal("1"):
            return self._reject("governance_size_haircut_full")
        risk_budget = self.state.equity * cfg.max_risk_per_trade_pct
        risk_amount = (risk_budget * max(D0, min(_d(quality_mult), Decimal("1.4"))) * (Decimal("1") - hc))
        risk_amount = min(risk_amount, risk_budget)   # multipliers can only reduce vs the cap
        if risk_amount <= D0:
            return self._reject("zero_risk_budget")

        qty = risk_amount / stop_distance
        market_value = (qty * entry)

        # 3 · exposure limits (portfolio risk controls override the trade)
        sym_cap = self.state.equity * cfg.max_symbol_exposure_pct
        tot_cap = self.state.equity * cfg.max_total_exposure_pct
        proj_sym = self.state.exposure.get(symbol, D0) + market_value
        proj_tot = self.total_exposure() + market_value
        reduced = False
        if proj_sym > sym_cap:
            room = sym_cap - self.state.exposure.get(symbol, D0)
            if room <= D0:
                return self._reject("symbol_exposure_cap")
            market_value, reduced = room, True
        if self.total_exposure() + market_value > tot_cap:
            room = tot_cap - self.total_exposure()
            if room <= D0:
                return self._reject("total_exposure_cap")
            market_value, reduced = min(market_value, room), True
        if reduced:
            qty = market_value / entry
            risk_amount = qty * stop_distance

        return {
            "ok": True,
            "verdict": "REDUCE" if reduced or hc > D0 or quality_mult < Decimal("1") else "APPROVE",
            "symbol": symbol,
            "qty": float(qty.quantize(Decimal("0.00000001"))),
            "risk_amount_usd": float(risk_amount.quantize(Decimal("0.01"))),
            "risk_pct_of_equity": float((risk_amount / self.state.equity).quantize(Decimal("0.0001"))),
            "market_value_usd": float(market_value.quantize(Decimal("0.01"))),
            "stop_distance": float(stop_distance),
            "reason": "reduced_by_limits" if reduced else "within_risk_budget",
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }

    def _reject(self, reason: str) -> dict:
        return {
            "ok": False,
            "verdict": "REJECT",
            "qty": 0.0,
            "risk_amount_usd": 0.0,
            "reason": reason,
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }

    # ── observability (explainable risk state) ───────────────────────────────
    def snapshot(self) -> dict:
        return {
            "equity": float(self.state.equity),
            "day_start_equity": float(self.state.day_start_equity),
            "high_water_mark": float(self.state.high_water_mark),
            "realised_day_pnl": float(self.state.realised_day_pnl),
            "daily_loss_pct": float(self.daily_loss_pct()),
            "drawdown_pct": float(self.drawdown_pct()),
            "total_exposure_usd": float(self.total_exposure()),
            "open_positions": self.state.open_positions,
            "halt_reason": self.halt_reason(),
            "config": {
                "max_risk_per_trade_pct": float(self.config.max_risk_per_trade_pct),
                "max_daily_loss_pct": float(self.config.max_daily_loss_pct),
                "max_drawdown_pct": float(self.config.max_drawdown_pct),
                "max_symbol_exposure_pct": float(self.config.max_symbol_exposure_pct),
                "max_total_exposure_pct": float(self.config.max_total_exposure_pct),
                "max_open_positions": self.config.max_open_positions,
            },
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }


risk_engine = RiskEngine()
