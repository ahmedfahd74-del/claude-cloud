"""Portfolio Intelligence — exposure and correlation control.

Signed exposure units per risk factor: a LONG EURUSD is +EUR/-USD; a LONG
BTCUSD adds +CRYPTO; indices/metals map to their own factors. The controller
walks opportunities best-first and rejects any that would concentrate a
factor, exceed the position cap, or blow the total risk budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CURRENCIES = {"USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"}
FACTOR_MAP = {
    "BTCUSD": ["CRYPTO", "BTC"], "ETHUSD": ["CRYPTO", "ETH"], "SOLUSD": ["CRYPTO", "SOL"],
    "XAUUSD": ["METALS", "GOLD"], "XAGUSD": ["METALS", "SILVER"],
    "WTIUSD": ["ENERGY"],
    "SPX500": ["EQUITY", "US"], "NAS100": ["EQUITY", "US"], "GER40": ["EQUITY", "EU"],
}


def factors(symbol: str, direction: str) -> dict[str, int]:
    """Signed exposure factors for a position (+1 long that factor, -1 short)."""
    sign = 1 if direction == "LONG" else -1
    base, quote = symbol[:3], symbol[3:6]
    if base in CURRENCIES and quote in CURRENCIES:
        return {base: sign, quote: -sign}
    return {f: sign for f in FACTOR_MAP.get(symbol, [symbol])}


@dataclass
class PortfolioConfig:
    max_positions: int = 5
    max_factor_exposure: int = 2      # |net units| allowed per risk factor
    max_total_risk_pct: float = 5.0
    risk_per_trade_pct: float = 1.0


@dataclass
class PortfolioController:
    cfg: PortfolioConfig = field(default_factory=PortfolioConfig)
    exposure: dict[str, int] = field(default_factory=dict)
    open_risk_pct: float = 0.0
    positions: int = 0

    def can_take(self, symbol: str, direction: str) -> tuple[bool, str]:
        if self.positions >= self.cfg.max_positions:
            return False, "max positions"
        if self.open_risk_pct + self.cfg.risk_per_trade_pct > self.cfg.max_total_risk_pct:
            return False, "risk budget"
        for f, s in factors(symbol, direction).items():
            if abs(self.exposure.get(f, 0) + s) > self.cfg.max_factor_exposure:
                return False, f"correlated exposure: {f}"
        return True, ""

    def take(self, symbol: str, direction: str) -> None:
        for f, s in factors(symbol, direction).items():
            self.exposure[f] = self.exposure.get(f, 0) + s
        self.positions += 1
        self.open_risk_pct += self.cfg.risk_per_trade_pct

    def select(self, ranked: list) -> tuple[list, list[tuple[object, str]]]:
        """Walk best-first; return (approved, [(rejected, reason)])."""
        approved, rejected = [], []
        for opp in ranked:
            ok, why = self.can_take(opp.symbol, opp.direction)
            if ok:
                self.take(opp.symbol, opp.direction)
                approved.append(opp)
            else:
                rejected.append((opp, why))
        return approved, rejected
