from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete

from app.db.models import (
    AllocationDecision,
    Asset,
    CandidateScore,
    ChallengeReport,
    CompanyStateHistory,
    PaperOrder,
    PodCandidate,
    Portfolio,
    Position,
    ReviewReport,
    RiskReview,
    ServiceHealthCheck,
    StrategyPod,
    TradeManagementEvent,
)
from app.db.session import SessionLocal


def run_seed() -> None:
    session = SessionLocal()
    try:
        session.execute(delete(AllocationDecision))
        session.execute(delete(RiskReview))
        session.execute(delete(ChallengeReport))
        session.execute(delete(CandidateScore))
        session.execute(delete(PodCandidate))
        session.execute(delete(TradeManagementEvent))
        session.execute(delete(Position))
        session.execute(delete(PaperOrder))
        session.execute(delete(ReviewReport))
        session.execute(delete(ServiceHealthCheck))
        session.execute(delete(CompanyStateHistory))
        session.execute(delete(StrategyPod))
        session.execute(delete(Asset))
        session.execute(delete(Portfolio))

        portfolio = Portfolio(name="Main Paper Portfolio", base_currency="USD", initial_cash=Decimal("100000.00"))
        asset = Asset(symbol="AAPL", asset_class="equity", name="Apple Inc.", is_active=True)
        pod = StrategyPod(name="LiquidityReversalPod", status="active", trust_grade="B")
        company_state = CompanyStateHistory(state_label="stable", confidence=Decimal("87.50"))
        service_check = ServiceHealthCheck(service_name="market-data", status="ok", latency_ms=125)

        session.add_all([portfolio, asset, pod, company_state, service_check])
        session.flush()

        candidate = PodCandidate(
            pod_id=pod.id,
            asset_id=asset.id,
            candidate_id="SEED-AAPL-001",
            pod_name="LiquidityReversalPod",
            setup_family="liquidity_reversal",
            asset="AAPL",
            direction="LONG",
            timeframe="4H",
            entry_zone_low=Decimal("174.00"),
            entry_zone_high=Decimal("175.20"),
            hard_stop=Decimal("171.60"),
            target_1=Decimal("178.10"),
            target_2=Decimal("181.50"),
            holding_horizon="2-5 days",
            thesis="Seeded candidate for paper opportunity flow.",
            invalidation="Breakdown below reclaimed liquidity zone.",
            requires_human_review=True,
            discovered_at=datetime.now(tz=timezone.utc),
            status="APPROVED",
            trust_grade="B",
            setup_quality=Decimal("0.78"),
            regime_fit=Decimal("0.71"),
            execution_quality_forecast=Decimal("0.67"),
            data_confidence=Decimal("0.82"),
            side="BUY",
        )
        session.add(candidate)
        session.flush()

        score = CandidateScore(
            candidate_id=candidate.id,
            candidate_ref="SEED-AAPL-001",
            setup_quality=Decimal("0.780"),
            regime_fit=Decimal("0.710"),
            data_confidence=Decimal("0.820"),
            execution_quality=Decimal("0.670"),
            portfolio_fit=Decimal("0.800"),
            historical_expectancy=Decimal("0.650"),
            fragility=Decimal("0.300"),
            final_score=Decimal("0.603"),
            rank_in_batch=1,
        )
        review = RiskReview(candidate_id=candidate.id, candidate_ref="SEED-AAPL-001", outcome="APPROVE", reason="Within paper-risk budget", size_adjustment=Decimal("1.00"))
        challenge = ChallengeReport(
            candidate_id=candidate.id,
            candidate_ref="SEED-AAPL-001",
            decision="PASS",
            confidence=Decimal("0.75"),
            challenge_summary="Seeded challenger pass.",
            risk_flags="",
            report_text="Seeded challenger pass.",
            status="CLOSED",
        )
        allocation = AllocationDecision(
            candidate_id=candidate.id,
            candidate_ref="SEED-AAPL-001",
            approved_size_usd=Decimal("4200.00"),
            decision="ALLOCATE",
            trade_risk_pct=Decimal("0.0042"),
            sizing_multiplier=Decimal("0.8400"),
        )
        position = Position(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            symbol="AAPL",
            direction="LONG",
            pod_name="LiquidityReversalPod",
            quantity=Decimal("10"),
            avg_price=Decimal("175.50"),
            market_value=Decimal("1755.00"),
            status="ACTIVE",
        )
        paper_order = PaperOrder(
            symbol="AAPL",
            asset_class="equity",
            side="BUY",
            quantity=Decimal("10"),
            limit_price=Decimal("175.50"),
            status="FILLED",
            note="Seeded example paper-trade order",
            candidate_ref="SEED-AAPL-001",
        )
        management_event = TradeManagementEvent(event_type="POSITION_ACTIVE", details="Seeded position event")
        report = ReviewReport(
            report_type="daily",
            subject_ref="portfolio:Main Paper Portfolio",
            summary="Paper trading only. Live execution disabled.",
        )

        session.add_all([score, review, challenge, allocation, position, paper_order, management_event, report])
        session.commit()
        print("Seed complete (paper trading data only; live execution disabled).")
    finally:
        session.close()


if __name__ == "__main__":
    run_seed()
