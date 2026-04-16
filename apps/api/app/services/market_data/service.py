from __future__ import annotations

from dataclasses import asdict

from app.services.market_data.adapters import (
    CacheSourceAdapter,
    CryptoExchangeNativeAdapter,
    FallbackSourceAdapter,
    ResearchPrimaryAdapter,
    SourceAdapter,
)
from app.services.market_data.models import SourcePayload


class MarketDataService:
    def __init__(self) -> None:
        self.adapters: list[SourceAdapter] = [
            ResearchPrimaryAdapter(),
            FallbackSourceAdapter(),
            CacheSourceAdapter(),
            CryptoExchangeNativeAdapter(),
        ]

    def _select_adapter(self, symbol: str) -> SourceAdapter:
        if symbol.upper().endswith("USD") and len(symbol) > 4:
            return self.adapters[3]
        return self.adapters[0]

    def get_payload(self, symbol: str, interval: str = "1m", limit: int = 20) -> SourcePayload:
        selected = self._select_adapter(symbol)
        return selected.fetch(symbol=symbol, interval=interval, limit=limit)

    def get_bars(self, symbol: str, interval: str = "1m", limit: int = 20) -> dict:
        payload = self.get_payload(symbol=symbol, interval=interval, limit=limit)
        return {
            "symbol": symbol,
            "interval": interval,
            "bars": [asdict(bar) for bar in payload.bars],
            "source": payload.health.source,
            "trust_grade": payload.health.trust_grade,
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }

    def get_quote(self, symbol: str) -> dict:
        payload = self.get_payload(symbol=symbol, limit=1)
        return {
            "symbol": symbol,
            "quote": asdict(payload.quote),
            "source": payload.health.source,
            "trust_grade": payload.health.trust_grade,
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }

    def get_source_health(self) -> dict:
        checks = [asdict(adapter.fetch(symbol="AAPL", interval="1m", limit=1).health) for adapter in self.adapters]
        return {
            "checks": checks,
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }
