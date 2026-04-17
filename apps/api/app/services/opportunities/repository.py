from __future__ import annotations

from decimal import Decimal

from app.services.opportunities.contracts import Candidate, ChallengeOutput, RiskReviewOutput


class OpportunityRepository:
    def __init__(self) -> None:
        self._memory_candidates: dict[str, dict] = {}
        self._memory_challenges: dict[str, dict] = {}
        self._memory_reviews: dict[str, dict] = {}
        self._memory_scores: dict[str, dict] = {}
        self._memory_allocations: dict[str, dict] = {}

    def _get_db_handles(self):
        try:
            from app.db.models import AllocationDecision, CandidateScore, ChallengeReport, PodCandidate, RiskReview
            from app.db.session import SessionLocal

            return SessionLocal, PodCandidate, ChallengeReport, RiskReview, CandidateScore, AllocationDecision
        except Exception:
            return None, None, None, None, None, None

    def save_candidate(self, candidate: Candidate) -> None:
        self._memory_candidates[candidate.candidate_id] = candidate.to_dict()
        SessionLocal, PodCandidate, _, _, _, _ = self._get_db_handles()
        if not SessionLocal:
            return
        try:
            with SessionLocal() as session:
                row = PodCandidate(
                    candidate_id=candidate.candidate_id,
                    pod_name=candidate.pod_name,
                    setup_family=candidate.setup_family,
                    asset=candidate.asset,
                    direction=candidate.direction,
                    timeframe=candidate.timeframe,
                    entry_zone_low=candidate.entry_zone_low,
                    entry_zone_high=candidate.entry_zone_high,
                    hard_stop=candidate.hard_stop,
                    target_1=candidate.target_1,
                    target_2=candidate.target_2,
                    holding_horizon=candidate.holding_horizon,
                    thesis=candidate.thesis,
                    invalidation=candidate.invalidation,
                    requires_human_review=candidate.requires_human_review,
                    discovered_at=candidate.discovered_at,
                    status=candidate.status,
                    trust_grade=candidate.trust_grade,
                    setup_quality=candidate.setup_quality,
                    regime_fit=candidate.regime_fit,
                    execution_quality_forecast=candidate.execution_quality_forecast,
                    data_confidence=candidate.data_confidence,
                )
                session.add(row)
                session.commit()
        except Exception:
            pass

    def list_candidates(self) -> list[dict]:
        SessionLocal, PodCandidate, _, _, _, _ = self._get_db_handles()
        if SessionLocal:
            try:
                with SessionLocal() as session:
                    rows = session.query(PodCandidate).all()
                    if rows:
                        db_candidates = {r.candidate_id: self._row_to_dict(r) for r in rows}
                        self._memory_candidates.update(db_candidates)
            except Exception:
                pass
        return list(self._memory_candidates.values())

    def get_candidate(self, candidate_id: str) -> dict | None:
        SessionLocal, PodCandidate, _, _, _, _ = self._get_db_handles()
        if SessionLocal:
            try:
                with SessionLocal() as session:
                    row = session.query(PodCandidate).filter(PodCandidate.candidate_id == candidate_id).first()
                    if row:
                        result = self._row_to_dict(row)
                        self._memory_candidates[candidate_id] = result
                        return result
            except Exception:
                pass
        return self._memory_candidates.get(candidate_id)

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "candidate_id": row.candidate_id,
            "pod_name": row.pod_name,
            "setup_family": row.setup_family,
            "asset": row.asset,
            "direction": row.direction,
            "timeframe": row.timeframe,
            "entry_zone_low": row.entry_zone_low,
            "entry_zone_high": row.entry_zone_high,
            "hard_stop": row.hard_stop,
            "target_1": row.target_1,
            "target_2": row.target_2,
            "holding_horizon": row.holding_horizon,
            "thesis": row.thesis,
            "invalidation": row.invalidation,
            "requires_human_review": row.requires_human_review,
            "discovered_at": row.discovered_at,
            "status": row.status,
            "trust_grade": row.trust_grade,
            "setup_quality": row.setup_quality,
            "regime_fit": row.regime_fit,
            "execution_quality_forecast": row.execution_quality_forecast,
            "data_confidence": row.data_confidence,
        }

    def update_status(self, candidate_id: str, status: str) -> None:
        if candidate_id in self._memory_candidates:
            self._memory_candidates[candidate_id]["status"] = status

    def save_scores(self, candidate_id: str, score_payload: dict) -> None:
        self._memory_scores[candidate_id] = score_payload
        SessionLocal, _, _, _, CandidateScore, _ = self._get_db_handles()
        if not SessionLocal:
            return
        try:
            with SessionLocal() as session:
                row = CandidateScore(
                    candidate_ref=candidate_id,
                    setup_quality=Decimal(str(score_payload["setup_quality"])),
                    regime_fit=Decimal(str(score_payload["regime_fit"])),
                    data_confidence=Decimal(str(score_payload["data_confidence"])),
                    execution_quality=Decimal(str(score_payload["execution_quality"])),
                    portfolio_fit=Decimal(str(score_payload["portfolio_fit"])),
                    historical_expectancy=Decimal(str(score_payload["historical_expectancy"])),
                    fragility=Decimal(str(score_payload["fragility"])),
                    final_score=Decimal(str(score_payload["final_score"])),
                    rank_in_batch=int(score_payload["rank_in_batch"]),
                )
                session.add(row)
                session.commit()
        except Exception:
            pass

    def get_scores(self) -> list[dict]:
        return list(self._memory_scores.values())

    def save_allocation(self, candidate_id: str, allocation_payload: dict) -> None:
        self._memory_allocations[candidate_id] = allocation_payload
        SessionLocal, _, _, _, _, AllocationDecision = self._get_db_handles()
        if not SessionLocal:
            return
        try:
            with SessionLocal() as session:
                row = AllocationDecision(
                    candidate_ref=candidate_id,
                    approved_size_usd=Decimal(str(allocation_payload["approved_size_usd"])),
                    decision=allocation_payload["decision"],
                    trade_risk_pct=Decimal(str(allocation_payload["trade_risk_pct"])),
                    sizing_multiplier=Decimal(str(allocation_payload["sizing_multiplier"])),
                )
                session.add(row)
                session.commit()
        except Exception:
            pass

    def get_allocation(self, candidate_id: str) -> dict | None:
        return self._memory_allocations.get(candidate_id)

    def save_challenge(self, output: ChallengeOutput) -> None:
        payload = {
            "candidate_id": output.candidate_id,
            "decision": output.decision,
            "confidence": float(output.confidence),
            "challenge_summary": output.challenge_summary,
            "risk_flags": output.risk_flags,
        }
        self._memory_challenges[output.candidate_id] = payload

        SessionLocal, _, ChallengeReport, _, _, _ = self._get_db_handles()
        if not SessionLocal:
            return
        try:
            with SessionLocal() as session:
                row = ChallengeReport(
                    candidate_ref=output.candidate_id,
                    decision=output.decision,
                    confidence=output.confidence,
                    challenge_summary=output.challenge_summary,
                    risk_flags=", ".join(output.risk_flags),
                    report_text=output.challenge_summary,
                    status="CLOSED",
                )
                session.add(row)
                session.commit()
        except Exception:
            pass

    def get_challenge(self, candidate_id: str) -> dict | None:
        SessionLocal, _, ChallengeReport, _, _, _ = self._get_db_handles()
        if SessionLocal:
            try:
                with SessionLocal() as session:
                    row = session.query(ChallengeReport).filter(ChallengeReport.candidate_ref == candidate_id).first()
                    if row:
                        result = {
                            "candidate_id": candidate_id,
                            "decision": row.decision,
                            "confidence": float(row.confidence),
                            "challenge_summary": row.challenge_summary,
                            "risk_flags": [f.strip() for f in row.risk_flags.split(",") if f.strip()] if row.risk_flags else [],
                        }
                        self._memory_challenges[candidate_id] = result
                        return result
            except Exception:
                pass
        return self._memory_challenges.get(candidate_id)

    def save_review(self, output: RiskReviewOutput) -> None:
        payload = {
            "candidate_id": output.candidate_id,
            "outcome": output.outcome,
            "reason": output.reason,
            "size_adjustment": float(output.size_adjustment),
            "paper_trading_only": output.paper_trading_only,
            "live_execution_enabled": output.live_execution_enabled,
        }
        self._memory_reviews[output.candidate_id] = payload

        SessionLocal, _, _, RiskReview, _, _ = self._get_db_handles()
        if not SessionLocal:
            return
        try:
            with SessionLocal() as session:
                row = RiskReview(
                    candidate_ref=output.candidate_id,
                    outcome=output.outcome,
                    reason=output.reason,
                    size_adjustment=Decimal(str(output.size_adjustment)),
                )
                session.add(row)
                session.commit()
        except Exception:
            pass

    def get_review(self, candidate_id: str) -> dict | None:
        SessionLocal, _, _, RiskReview, _, _ = self._get_db_handles()
        if SessionLocal:
            try:
                with SessionLocal() as session:
                    row = session.query(RiskReview).filter(RiskReview.candidate_ref == candidate_id).first()
                    if row:
                        result = {
                            "candidate_id": candidate_id,
                            "outcome": row.outcome,
                            "reason": row.reason,
                            "size_adjustment": float(row.size_adjustment),
                            "paper_trading_only": True,
                            "live_execution_enabled": False,
                        }
                        self._memory_reviews[candidate_id] = result
                        return result
            except Exception:
                pass
        return self._memory_reviews.get(candidate_id)
