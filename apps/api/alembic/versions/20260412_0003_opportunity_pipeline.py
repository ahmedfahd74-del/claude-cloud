"""opportunity pipeline fields

Revision ID: 20260412_0003
Revises: 20260412_0002
Create Date: 2026-04-12 03:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260412_0003"
down_revision: Union[str, None] = "20260412_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pod_candidates", sa.Column("candidate_id", sa.String(length=64), nullable=True))
    op.add_column("pod_candidates", sa.Column("pod_name", sa.String(length=100), nullable=True))
    op.add_column("pod_candidates", sa.Column("setup_family", sa.String(length=60), nullable=True))
    op.add_column("pod_candidates", sa.Column("asset", sa.String(length=30), nullable=True))
    op.add_column("pod_candidates", sa.Column("direction", sa.String(length=10), nullable=True))
    op.add_column("pod_candidates", sa.Column("timeframe", sa.String(length=10), nullable=True))
    op.add_column("pod_candidates", sa.Column("entry_zone_low", sa.Numeric(18, 8), nullable=True))
    op.add_column("pod_candidates", sa.Column("entry_zone_high", sa.Numeric(18, 8), nullable=True))
    op.add_column("pod_candidates", sa.Column("hard_stop", sa.Numeric(18, 8), nullable=True))
    op.add_column("pod_candidates", sa.Column("target_1", sa.Numeric(18, 8), nullable=True))
    op.add_column("pod_candidates", sa.Column("target_2", sa.Numeric(18, 8), nullable=True))
    op.add_column("pod_candidates", sa.Column("holding_horizon", sa.String(length=30), nullable=True))
    op.add_column("pod_candidates", sa.Column("invalidation", sa.Text(), nullable=True))
    op.add_column("pod_candidates", sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("pod_candidates", sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("pod_candidates", sa.Column("trust_grade", sa.String(length=4), nullable=False, server_default="B"))
    op.add_column("pod_candidates", sa.Column("setup_quality", sa.Numeric(5, 3), nullable=False, server_default="0.500"))
    op.add_column("pod_candidates", sa.Column("regime_fit", sa.Numeric(5, 3), nullable=False, server_default="0.500"))
    op.add_column("pod_candidates", sa.Column("execution_quality_forecast", sa.Numeric(5, 3), nullable=False, server_default="0.500"))
    op.add_column("pod_candidates", sa.Column("data_confidence", sa.Numeric(5, 3), nullable=False, server_default="0.500"))

    op.create_index("ix_pod_candidates_candidate_id", "pod_candidates", ["candidate_id"], unique=True)

    op.add_column("challenge_reports", sa.Column("candidate_ref", sa.String(length=64), nullable=True))
    op.add_column("challenge_reports", sa.Column("decision", sa.String(length=20), nullable=True))
    op.add_column("challenge_reports", sa.Column("confidence", sa.Numeric(5, 3), nullable=True))
    op.add_column("challenge_reports", sa.Column("challenge_summary", sa.Text(), nullable=True))
    op.add_column("challenge_reports", sa.Column("risk_flags", sa.Text(), nullable=True))
    op.create_index("ix_challenge_reports_candidate_ref", "challenge_reports", ["candidate_ref"])

    op.add_column("risk_reviews", sa.Column("candidate_ref", sa.String(length=64), nullable=True))
    op.add_column("risk_reviews", sa.Column("size_adjustment", sa.Numeric(5, 2), nullable=False, server_default="1.00"))
    op.create_index("ix_risk_reviews_candidate_ref", "risk_reviews", ["candidate_ref"])


def downgrade() -> None:
    op.drop_index("ix_risk_reviews_candidate_ref", table_name="risk_reviews")
    op.drop_column("risk_reviews", "size_adjustment")
    op.drop_column("risk_reviews", "candidate_ref")

    op.drop_index("ix_challenge_reports_candidate_ref", table_name="challenge_reports")
    op.drop_column("challenge_reports", "risk_flags")
    op.drop_column("challenge_reports", "challenge_summary")
    op.drop_column("challenge_reports", "confidence")
    op.drop_column("challenge_reports", "decision")
    op.drop_column("challenge_reports", "candidate_ref")

    op.drop_index("ix_pod_candidates_candidate_id", table_name="pod_candidates")
    op.drop_column("pod_candidates", "data_confidence")
    op.drop_column("pod_candidates", "execution_quality_forecast")
    op.drop_column("pod_candidates", "regime_fit")
    op.drop_column("pod_candidates", "setup_quality")
    op.drop_column("pod_candidates", "trust_grade")
    op.drop_column("pod_candidates", "discovered_at")
    op.drop_column("pod_candidates", "requires_human_review")
    op.drop_column("pod_candidates", "invalidation")
    op.drop_column("pod_candidates", "holding_horizon")
    op.drop_column("pod_candidates", "target_2")
    op.drop_column("pod_candidates", "target_1")
    op.drop_column("pod_candidates", "hard_stop")
    op.drop_column("pod_candidates", "entry_zone_high")
    op.drop_column("pod_candidates", "entry_zone_low")
    op.drop_column("pod_candidates", "timeframe")
    op.drop_column("pod_candidates", "direction")
    op.drop_column("pod_candidates", "asset")
    op.drop_column("pod_candidates", "setup_family")
    op.drop_column("pod_candidates", "pod_name")
    op.drop_column("pod_candidates", "candidate_id")
