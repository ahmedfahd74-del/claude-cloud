from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="LONG")
    side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_ENTRY")
    note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    candidate_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperFill(Base):
    __tablename__ = "paper_fills"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("paper_orders.id"), nullable=False)
    filled_qty: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    filled_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    fill_status: Mapped[str] = mapped_column(String(30), nullable=False, default="FILLED")
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)


class StrategyPod(Base):
    __tablename__ = "strategy_pods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    trust_grade: Mapped[str] = mapped_column(String(10), nullable=False, default="B")


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    pod_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_pods.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="registered")


class CompanyStateHistory(Base):
    __tablename__ = "company_state_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    state_label: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceHealthCheck(Base):
    __tablename__ = "service_health_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PodCandidate(Base):
    __tablename__ = "pod_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    pod_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_pods.id"), nullable=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True)

    candidate_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    pod_name: Mapped[str] = mapped_column(String(100), nullable=False)
    setup_family: Mapped[str] = mapped_column(String(60), nullable=False)
    asset: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_zone_low: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    entry_zone_high: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    hard_stop: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    target_1: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    target_2: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    holding_horizon: Mapped[str] = mapped_column(String(30), nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    invalidation: Mapped[str] = mapped_column(Text, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="NEW")
    trust_grade: Mapped[str] = mapped_column(String(4), nullable=False, default="B")

    setup_quality: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    regime_fit: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    execution_quality_forecast: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    data_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)

    side: Mapped[str | None] = mapped_column(String(4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateScore(Base):
    __tablename__ = "candidate_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("pod_candidates.id"), nullable=True)
    candidate_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    setup_quality: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    regime_fit: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    data_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    execution_quality: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    portfolio_fit: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    historical_expectancy: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    fragility: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    final_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    rank_in_batch: Mapped[int] = mapped_column(Integer, nullable=False)


class ChallengeReport(Base):
    __tablename__ = "challenge_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("pod_candidates.id"), nullable=True)
    candidate_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    challenge_summary: Mapped[str] = mapped_column(Text(), nullable=False)
    risk_flags: Mapped[str] = mapped_column(Text(), nullable=False)
    report_text: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN")


class RiskReview(Base):
    __tablename__ = "risk_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("pod_candidates.id"), nullable=True)
    candidate_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_adjustment: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("1.00"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AllocationDecision(Base):
    __tablename__ = "allocation_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("pod_candidates.id"), nullable=True)
    candidate_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    approved_size_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_risk_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    sizing_multiplier: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="LONG")
    pod_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")


class TradeManagementEvent(Base):
    __tablename__ = "trade_management_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"), nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("paper_orders.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TradeJournal(Base):
    __tablename__ = "trade_journal"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"), nullable=True)
    paper_order_id: Mapped[int | None] = mapped_column(ForeignKey("paper_orders.id"), nullable=True)
    candidate_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    asset: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pod_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    journal_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewReport(Base):
    __tablename__ = "review_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"), nullable=True)
    candidate_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    asset: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pod_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    report_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    process_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    execution_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    outcome_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    review_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionMemory(Base):
    __tablename__ = "decision_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    memory_type: Mapped[str] = mapped_column(String(20), nullable=False)
    asset: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pod_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    regime_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    setup_family: Mapped[str | None] = mapped_column(String(60), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PodPerformance(Base):
    __tablename__ = "pod_performance"

    id: Mapped[int] = mapped_column(primary_key=True)
    pod_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    regime_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(20), nullable=True)
    asset_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trades_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=Decimal("0.000"))
    avg_outcome_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=Decimal("0.000"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyChangeQueue(Base):
    __tablename__ = "policy_change_queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING_REVIEW")
    proposed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
