from __future__ import annotations

from decimal import Decimal

from app.services.opportunities.contracts import RiskReviewOutput
from app.services.opportunities.repository import OpportunityRepository


class _FallbackSettings:
    paper_trading_only = True
    live_execution_enabled = False


def _get_settings():
    try:
        from app.core.config import settings

        return settings
    except Exception:
        return _FallbackSettings()


class RiskReviewService:
    def __init__(self, repository: OpportunityRepository) -> None:
        self.repository = repository

    def review(self, candidate_id: str) -> dict:
        settings = _get_settings()
        candidate = self.repository.get_candidate(candidate_id)
        if not candidate:
            return {"ok": False, "error": "candidate_not_found"}

        outcome = "APPROVE"
        reason = "meets initial hard rules"
        size_adjustment = Decimal("1.00")

        if candidate.get("trust_grade") in {"D", "E"}:
            outcome = "REJECT"
            reason = "trust_grade_below_minimum"
            size_adjustment = Decimal("0.00")
        elif candidate.get("hard_stop") in (None, ""):
            outcome = "HOLD"
            reason = "hard_stop_required"
            size_adjustment = Decimal("0.00")
        elif not settings.paper_trading_only or settings.live_execution_enabled:
            outcome = "HOLD"
            reason = "safety_mode_violation"
            size_adjustment = Decimal("0.00")
        elif float(candidate.get("setup_quality", 0)) < 0.65:
            outcome = "REDUCE"
            reason = "quality_below_full_size_threshold"
            size_adjustment = Decimal("0.50")

        output = RiskReviewOutput(
            candidate_id=candidate_id,
            outcome=outcome,  # type: ignore[arg-type]
            reason=reason,
            size_adjustment=size_adjustment,
            paper_trading_only=settings.paper_trading_only,
            live_execution_enabled=settings.live_execution_enabled,
        )
        self.repository.save_review(output)
        next_status = "APPROVED" if outcome == "APPROVE" else "REDUCED" if outcome == "REDUCE" else "REJECTED" if outcome == "REJECT" else "HOLD"
        self.repository.update_status(candidate_id, next_status)
        return {"ok": True, **self.repository.get_review(candidate_id), "status": self.repository.get_candidate(candidate_id)["status"]}
