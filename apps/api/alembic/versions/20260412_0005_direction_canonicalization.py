"""direction canonicalization

Revision ID: 20260412_0005
Revises: 20260412_0004
Create Date: 2026-04-12 05:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260412_0005"
down_revision: Union[str, None] = "20260412_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("paper_orders", sa.Column("direction", sa.String(length=8), nullable=False, server_default="LONG"))


def downgrade() -> None:
    op.drop_column("paper_orders", "direction")
