"""portfolio and execution brain

Revision ID: 20260412_0004
Revises: 20260412_0003
Create Date: 2026-04-12 04:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260412_0004"
down_revision: Union[str, None] = "20260412_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidate_scores", sa.Column("candidate_ref", sa.String(length=64), nullable=True))
    op.add_column("candidate_scores", sa.Column("setup_quality", sa.Numeric(6, 3), nullable=True))
    op.add_column("candidate_scores", sa.Column("regime_fit", sa.Numeric(6, 3), nullable=True))
    op.add_column("candidate_scores", sa.Column("data_confidence", sa.Numeric(6, 3), nullable=True))
    op.add_column("candidate_scores", sa.Column("execution_quality", sa.Numeric(6, 3), nullable=True))
    op.add_column("candidate_scores", sa.Column("portfolio_fit", sa.Numeric(6, 3), nullable=True))
    op.add_column("candidate_scores", sa.Column("historical_expectancy", sa.Numeric(6, 3), nullable=True))
    op.add_column("candidate_scores", sa.Column("fragility", sa.Numeric(6, 3), nullable=True))
    op.add_column("candidate_scores", sa.Column("final_score", sa.Numeric(6, 3), nullable=True))
    op.add_column("candidate_scores", sa.Column("rank_in_batch", sa.Integer(), nullable=True))
    op.create_index("ix_candidate_scores_candidate_ref", "candidate_scores", ["candidate_ref"])

    op.add_column("allocation_decisions", sa.Column("candidate_ref", sa.String(length=64), nullable=True))
    op.add_column("allocation_decisions", sa.Column("trade_risk_pct", sa.Numeric(6, 4), nullable=False, server_default="0.0050"))
    op.add_column("allocation_decisions", sa.Column("sizing_multiplier", sa.Numeric(6, 4), nullable=False, server_default="1.0000"))
    op.create_index("ix_allocation_decisions_candidate_ref", "allocation_decisions", ["candidate_ref"])

    op.add_column("paper_orders", sa.Column("candidate_ref", sa.String(length=64), nullable=True))

    op.create_table(
        "paper_fills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("paper_orders.id"), nullable=False),
        sa.Column("filled_qty", sa.Numeric(18, 8), nullable=False),
        sa.Column("filled_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("fill_status", sa.String(length=30), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column("positions", sa.Column("symbol", sa.String(length=30), nullable=True))
    op.add_column("positions", sa.Column("direction", sa.String(length=8), nullable=False, server_default="LONG"))
    op.add_column("positions", sa.Column("pod_name", sa.String(length=100), nullable=True))
    op.add_column("positions", sa.Column("status", sa.String(length=30), nullable=False, server_default="ACTIVE"))

    op.create_table(
        "trade_management_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("paper_orders.id"), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("trade_management_events")

    op.drop_column("positions", "status")
    op.drop_column("positions", "pod_name")
    op.drop_column("positions", "direction")
    op.drop_column("positions", "symbol")

    op.drop_table("paper_fills")
    op.drop_column("paper_orders", "candidate_ref")

    op.drop_index("ix_allocation_decisions_candidate_ref", table_name="allocation_decisions")
    op.drop_column("allocation_decisions", "sizing_multiplier")
    op.drop_column("allocation_decisions", "trade_risk_pct")
    op.drop_column("allocation_decisions", "candidate_ref")

    op.drop_index("ix_candidate_scores_candidate_ref", table_name="candidate_scores")
    op.drop_column("candidate_scores", "rank_in_batch")
    op.drop_column("candidate_scores", "final_score")
    op.drop_column("candidate_scores", "fragility")
    op.drop_column("candidate_scores", "historical_expectancy")
    op.drop_column("candidate_scores", "portfolio_fit")
    op.drop_column("candidate_scores", "execution_quality")
    op.drop_column("candidate_scores", "data_confidence")
    op.drop_column("candidate_scores", "regime_fit")
    op.drop_column("candidate_scores", "setup_quality")
    op.drop_column("candidate_scores", "candidate_ref")
