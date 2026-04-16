from __future__ import annotations

from decimal import Decimal

from app.services.opportunities.contracts import ChallengeOutput
from app.services.opportunities.repository import OpportunityRepository


class ChallengerService:
    def __init__(self, repository: OpportunityRepository) -> None:
        self.repository = repository

    def run(self, candidate_id: str) -> dict:
        candidate = self.repository.get_candidate(candidate_id)
        if not candidate:
            return {"ok": False, "error": "candidate_not_found"}

        risk_flags: list[str] = []
        decision = "PASS"
        confidence = Decimal("0.74")

        if float(candidate["data_confidence"]) < 0.65:
            risk_flags.append("low_data_confidence")
            decision = "CHALLENGE"
            confidence = Decimal("0.68")

        if float(candidate["regime_fit"]) < 0.6:
            risk_flags.append("weak_regime_fit")
            decision = "CHALLENGE"

        if candidate["trust_grade"] in {"D", "E"}:
            risk_flags.append("low_trust_grade")
            decision = "BLOCK"
            confidence = Decimal("0.91")

        summary = "Candidate passed challenger checks." if decision == "PASS" else "Candidate requires risk escalation."
        output = ChallengeOutput(
            candidate_id=candidate_id,
            decision=decision,  # type: ignore[arg-type]
            confidence=confidence,
            challenge_summary=summary,
            risk_flags=risk_flags,
        )
        self.repository.save_challenge(output)
        self.repository.update_status(candidate_id, "CHALLENGED" if decision != "PASS" else "RISK_REVIEW")
        return {"ok": True, **self.repository.get_challenge(candidate_id), "status": self.repository.get_candidate(candidate_id)["status"]}
