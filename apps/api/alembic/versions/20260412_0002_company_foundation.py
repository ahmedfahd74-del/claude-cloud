"""company foundation tables

Revision ID: 20260412_0002
Revises: 20260412_0001
Create Date: 2026-04-12 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260412_0002"
down_revision: Union[str, None] = "20260412_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=30), nullable=False, unique=True),
        sa.Column("asset_class", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "strategy_pods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("trust_grade", sa.String(length=10), nullable=False),
    )

    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("pod_id", sa.Integer(), sa.ForeignKey("strategy_pods.id"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
    )

    op.create_table(
        "company_state_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state_label", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "service_health_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "pod_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pod_id", sa.Integer(), sa.ForeignKey("strategy_pods.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "candidate_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("pod_candidates.id"), nullable=False),
        sa.Column("signal_score", sa.Numeric(6, 3), nullable=False),
        sa.Column("risk_score", sa.Numeric(6, 3), nullable=False),
        sa.Column("liquidity_score", sa.Numeric(6, 3), nullable=False),
        sa.Column("total_score", sa.Numeric(6, 3), nullable=False),
    )

    op.create_table(
        "challenge_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("pod_candidates.id"), nullable=False),
        sa.Column("report_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
    )

    op.create_table(
        "risk_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("pod_candidates.id"), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "allocation_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("pod_candidates.id"), nullable=False),
        sa.Column("approved_size_usd", sa.Numeric(18, 2), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("avg_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("market_value", sa.Numeric(18, 2), nullable=False),
    )

    op.create_table(
        "trade_journal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=True),
        sa.Column("paper_order_id", sa.Integer(), sa.ForeignKey("paper_orders.id"), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "review_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("subject_ref", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("review_reports")
    op.drop_table("trade_journal")
    op.drop_table("positions")
    op.drop_table("allocation_decisions")
    op.drop_table("risk_reviews")
    op.drop_table("challenge_reports")
    op.drop_table("candidate_scores")
    op.drop_table("pod_candidates")
    op.drop_table("service_health_checks")
    op.drop_table("company_state_history")
    op.drop_table("model_registry")
    op.drop_table("strategy_pods")
    op.drop_table("assets")
