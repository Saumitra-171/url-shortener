"""cascade delete clicks with url

Revision ID: 62f43d2c3764
Revises: eb8c90d3112a
Create Date: 2026-10-17 13:52:05.058288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62f43d2c3764'
down_revision: Union[str, None] = 'eb8c90d3112a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("clicks_url_id_fkey", "clicks", type_="foreignkey")
    op.create_foreign_key(
        "clicks_url_id_fkey", "clicks", "urls", ["url_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("clicks_url_id_fkey", "clicks", type_="foreignkey")
    op.create_foreign_key("clicks_url_id_fkey", "clicks", "urls", ["url_id"], ["id"])
