"""add expiry and widen short code

Revision ID: 90d5d5e75e8e
Revises: 0697908d60d0
Create Date: 2026-10-19 14:32:49.400501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90d5d5e75e8e'
down_revision: Union[str, None] = '0697908d60d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("urls", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column(
        "urls", "short_code",
        existing_type=sa.String(10), type_=sa.String(32), existing_nullable=False,
    )


def downgrade() -> None:
    # Fails if any short_code longer than 10 characters exists, because narrowing can't keep it.
    op.alter_column(
        "urls", "short_code",
        existing_type=sa.String(32), type_=sa.String(10), existing_nullable=False,
    )
    op.drop_column("urls", "expires_at")