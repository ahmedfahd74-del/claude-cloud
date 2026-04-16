from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.services.market_data.models import MarketBar, MarketQuote, SourceHealth, SourcePayload, utc_now


class SourceAdapter(ABC):
    source_name: str

    @abstractmethod
    def fetch(self, symbol: str, interval: str, limit: int) -> SourcePayload:
        raise NotImplementedError


class _BaseMockAdapter(SourceAdapter):
    source_name = "base"
    latency_ms = 100
    trust_grade = "B"
    status = "ok"

    def fetch(self, symbol: str, interval: str, limit: int) -> SourcePayload:  # noqa: ARG002
        now = utc_now()
        bars = []
        base = Decimal("100")
        for i in range(limit):
            close = base + Decimal(i)
            bars.append(
                MarketBar(
                    symbol=symbol,
                    ts=now,
                    open=close - Decimal("0.7"),
                    high=close + Decimal("0.9"),
                    low=close - Decimal("1.2"),
                    close=close,
                    volume=Decimal("1000") + Decimal(i * 10),
                    source=self.source_name,
                    trust_grade=self.trust_grade,  # type: ignore[arg-type]
                )
            )

        quote = MarketQuote(
            symbol=symbol,
            ts=now,
            bid=bars[-1].close - Decimal("0.05"),
            ask=bars[-1].close + Decimal("0.05"),
            last=bars[-1].close,
            source=self.source_name,
            trust_grade=self.trust_grade,  # type: ignore[arg-type]
        )

        health = SourceHealth(
            source=self.source_name,
            status=self.status,  # type: ignore[arg-type]
            latency_ms=self.latency_ms,
            stale_seconds=5,
            trust_grade=self.trust_grade,  # type: ignore[arg-type]
            checked_at=now,
        )
        return SourcePayload(bars=bars, quote=quote, health=health)


class ResearchPrimaryAdapter(_BaseMockAdapter):
    source_name = "research_primary"
    latency_ms = 95
    trust_grade = "A"


class FallbackSourceAdapter(_BaseMockAdapter):
    source_name = "fallback_source"
    latency_ms = 180
    trust_grade = "B"


class CacheSourceAdapter(_BaseMockAdapter):
    source_name = "cache_source"
    latency_ms = 20
    trust_grade = "B"


class CryptoExchangeNativeAdapter(_BaseMockAdapter):
    source_name = "crypto_exchange_native"
    latency_ms = 110
    trust_grade = "A"
