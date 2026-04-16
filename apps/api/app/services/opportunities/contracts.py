from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

CandidateStatus = Literal["NEW", "CHALLENGED", "RISK_REVIEW", "APPROVED", "REDUCED", "REJECTED", "HOLD"]


@dataclass
class Candidate:
    candidate_id: str
    pod_name: str
    setup_family: str
    asset: str
    direction: Literal["LONG", "SHORT"]
    timeframe: str
    entry_zone_low: Decimal
    entry_zone_high: Decimal
    hard_stop: Decimal
    target_1: Decimal
    target_2: Decimal
    holding_horizon: str
    thesis: str
    invalidation: str
    requires_human_review: bool
    discovered_at: datetime
    status: CandidateStatus
    setup_quality: Decimal
    regime_fit: Decimal
    execution_quality_forecast: Decimal
    data_confidence: Decimal
    trust_grade: Literal["A", "B", "C", "D", "E"]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["discovered_at"] = self.discovered_at.isoformat()
        return payload


@dataclass
class CandidateScoreBreakdown:
    candidate_id: str
    setup_quality: Decimal
    regime_fit: Decimal
    execution_quality_forecast: Decimal
    data_confidence: Decimal


@dataclass
class ChallengeOutput:
    candidate_id: str
    decision: Literal["PASS", "CHALLENGE", "BLOCK"]
    confidence: Decimal
    challenge_summary: str
    risk_flags: list[str]


@dataclass
class RiskReviewOutput:
    candidate_id: str
    outcome: Literal["APPROVE", "REDUCE", "REJECT", "HOLD"]
    reason: str
    size_adjustment: Decimal
    paper_trading_only: bool
    live_execution_enabled: bool
