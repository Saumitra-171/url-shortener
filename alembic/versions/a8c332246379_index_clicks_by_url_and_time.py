"""index clicks by url and time

Revision ID: a8c332246379
Revises: 90d5d5e75e8e
Create Date: 2026-10-20 11:28:07.730128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8c332246379'
down_revision: Union[str, None] = '90d5d5e75e8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_clicks_url_id_clicked_at", "clicks", ["url_id", "clicked_at"])


def downgrade() -> None:
    op.drop_index("ix_clicks_url_id_clicked_at", table_name="clicks")