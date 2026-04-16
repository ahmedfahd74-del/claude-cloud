"""drop legacy score columns from candidate_scores

The original candidate_scores table (migration 0002) had signal_score,
risk_score, liquidity_score, and total_score as NOT NULL columns.
Migration 0004 replaced the scoring schema with new columns, but never
dropped these four, causing NOT NULL violations on every INSERT because
the SQLAlchemy model no longer defines them.

Revision ID: 20260417_0008
Revises: 20260417_0007
Create Date: 2026-04-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260417_0008"
down_revision: Union[str, None] = "20260417_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("candidate_scores", "signal_score")
    op.drop_column("candidate_scores", "risk_score")
    op.drop_column("candidate_scores", "liquidity_score")
    op.drop_column("candidate_scores", "total_score")


def downgrade() -> None:
    op.add_column("candidate_scores", sa.Column("total_score", sa.Numeric(6, 3), nullable=False, server_default="0.000"))
    op.add_column("candidate_scores", sa.Column("liquidity_score", sa.Numeric(6, 3), nullable=False, server_default="0.000"))
    op.add_column("candidate_scores", sa.Column("risk_score", sa.Numeric(6, 3), nullable=False, server_default="0.000"))
    op.add_column("candidate_scores", sa.Column("signal_score", sa.Numeric(6, 3), nullable=False, server_default="0.000"))
