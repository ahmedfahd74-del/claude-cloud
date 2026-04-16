"""add status column to pod_candidates

Revision ID: 20260417_0007
Revises: 20260412_0006
Create Date: 2026-04-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260417_0007"
down_revision: Union[str, None] = "20260412_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pod_candidates",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="NEW"),
    )


def downgrade() -> None:
    op.drop_column("pod_candidates", "status")
