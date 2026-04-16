from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal

from app.services.opportunities.contracts import Candidate


class StrategyPod(ABC):
    pod_name: str
    setup_family: str

    @abstractmethod
    def generate(self, asset: str) -> Candidate:
        raise NotImplementedError


class LiquidityReversalPod(StrategyPod):
    pod_name = "LiquidityReversalPod"
    setup_family = "liquidity_reversal"

    def generate(self, asset: str) -> Candidate:
        base = Decimal(str(len(asset) * 10 + 100))
        return Candidate(
            candidate_id=f"LRP-{asset}-001",
            pod_name=self.pod_name,
            setup_family=self.setup_family,
            asset=asset,
            direction="LONG",
            timeframe="4H",
            entry_zone_low=base - Decimal("1.5"),
            entry_zone_high=base - Decimal("0.5"),
            hard_stop=base - Decimal("3.5"),
            target_1=base + Decimal("2.0"),
            target_2=base + Decimal("4.0"),
            holding_horizon="2-5 days",
            thesis="Sweep-and-reclaim structure with improving momentum.",
            invalidation="Fails to hold reclaimed liquidity pocket.",
            requires_human_review=True,
            discovered_at=datetime.now(tz=timezone.utc),
            status="NEW",
            setup_quality=Decimal("0.78"),
            regime_fit=Decimal("0.71"),
            execution_quality_forecast=Decimal("0.67"),
            data_confidence=Decimal("0.82"),
            trust_grade="B",
        )


class ContinuationPullbackPod(StrategyPod):
    pod_name = "ContinuationPullbackPod"
    setup_family = "continuation_pullback"

    def generate(self, asset: str) -> Candidate:
        base = Decimal(str(len(asset) * 12 + 110))
        return Candidate(
            candidate_id=f"CPP-{asset}-001",
            pod_name=self.pod_name,
            setup_family=self.setup_family,
            asset=asset,
            direction="SHORT",
            timeframe="1H",
            entry_zone_low=base + Decimal("0.3"),
            entry_zone_high=base + Decimal("1.2"),
            hard_stop=base + Decimal("2.1"),
            target_1=base - Decimal("1.4"),
            target_2=base - Decimal("2.8"),
            holding_horizon="8-24 hours",
            thesis="Trend continuation after weak pullback rejection.",
            invalidation="Break and hold above pullback pivot.",
            requires_human_review=False,
            discovered_at=datetime.now(tz=timezone.utc),
            status="NEW",
            setup_quality=Decimal("0.74"),
            regime_fit=Decimal("0.69"),
            execution_quality_forecast=Decimal("0.72"),
            data_confidence=Decimal("0.77"),
            trust_grade="B",
        )
