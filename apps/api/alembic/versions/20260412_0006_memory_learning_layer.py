"""memory and learning layer

Revision ID: 20260412_0006
Revises: 20260412_0005
Create Date: 2026-04-12 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260412_0006"
down_revision: Union[str, None] = "20260412_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trade_journal", sa.Column("candidate_ref", sa.String(length=64), nullable=True))
    op.add_column("trade_journal", sa.Column("asset", sa.String(length=30), nullable=True))
    op.add_column("trade_journal", sa.Column("pod_name", sa.String(length=100), nullable=True))
    op.add_column("trade_journal", sa.Column("journal_type", sa.String(length=30), nullable=True))
    op.add_column("trade_journal", sa.Column("summary", sa.Text(), nullable=True))

    op.add_column("review_reports", sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=True))
    op.add_column("review_reports", sa.Column("candidate_ref", sa.String(length=64), nullable=True))
    op.add_column("review_reports", sa.Column("asset", sa.String(length=30), nullable=True))
    op.add_column("review_reports", sa.Column("pod_name", sa.String(length=100), nullable=True))
    op.add_column("review_reports", sa.Column("process_score", sa.Numeric(6, 3), nullable=True))
    op.add_column("review_reports", sa.Column("execution_score", sa.Numeric(6, 3), nullable=True))
    op.add_column("review_reports", sa.Column("outcome_score", sa.Numeric(6, 3), nullable=True))
    op.add_column("review_reports", sa.Column("review_summary", sa.Text(), nullable=True))

    op.create_table(
        "decision_memory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("memory_type", sa.String(length=20), nullable=False),
        sa.Column("asset", sa.String(length=30), nullable=True),
        sa.Column("pod_name", sa.String(length=100), nullable=True),
        sa.Column("regime_label", sa.String(length=50), nullable=True),
        sa.Column("setup_family", sa.String(length=60), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "pod_performance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pod_name", sa.String(length=100), nullable=False),
        sa.Column("regime_label", sa.String(length=50), nullable=True),
        sa.Column("timeframe", sa.String(length=20), nullable=True),
        sa.Column("asset_class", sa.String(length=30), nullable=True),
        sa.Column("trades_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Numeric(6, 3), nullable=False, server_default="0.000"),
        sa.Column("avg_outcome_score", sa.Numeric(6, 3), nullable=False, server_default="0.000"),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pod_performance_pod_name", "pod_performance", ["pod_name"])

    op.create_table(
        "policy_change_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("proposed_by", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("policy_change_queue")

    op.drop_index("ix_pod_performance_pod_name", table_name="pod_performance")
    op.drop_table("pod_performance")

    op.drop_table("decision_memory")

    op.drop_column("review_reports", "review_summary")
    op.drop_column("review_reports", "outcome_score")
    op.drop_column("review_reports", "execution_score")
    op.drop_column("review_reports", "process_score")
    op.drop_column("review_reports", "pod_name")
    op.drop_column("review_reports", "asset")
    op.drop_column("review_reports", "candidate_ref")
    op.drop_column("review_reports", "position_id")

    op.drop_column("trade_journal", "summary")
    op.drop_column("trade_journal", "journal_type")
    op.drop_column("trade_journal", "pod_name")
    op.drop_column("trade_journal", "asset")
    op.drop_column("trade_journal", "candidate_ref")
