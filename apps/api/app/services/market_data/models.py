from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

TrustGrade = Literal["A", "B", "C", "D"]


@dataclass(slots=True)
class MarketBar:
    symbol: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str
    trust_grade: TrustGrade


@dataclass(slots=True)
class MarketQuote:
    symbol: str
    ts: datetime
    bid: Decimal
    ask: Decimal
    last: Decimal
    source: str
    trust_grade: TrustGrade


@dataclass(slots=True)
class SourceHealth:
    source: str
    status: Literal["ok", "degraded", "down"]
    latency_ms: int
    stale_seconds: int
    trust_grade: TrustGrade
    checked_at: datetime


@dataclass(slots=True)
class SourcePayload:
    bars: list[MarketBar]
    quote: MarketQuote
    health: SourceHealth


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)
