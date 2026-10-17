"""baseline

Revision ID: eb8c90d3112a
Revises: 
Create Date: 2026-10-17 13:49:51.342627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb8c90d3112a'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "urls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("short_code", sa.String(10), nullable=False),
        sa.Column("original_url", sa.String(2048), nullable=False),
        sa.Column("click_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_clicked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_urls_id", "urls", ["id"])
    op.create_index("ix_urls_short_code", "urls", ["short_code"], unique=True)

    op.create_table(
        "clicks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url_id", sa.Integer(), sa.ForeignKey("urls.id"), nullable=False),
        sa.Column("clicked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("referrer", sa.String(512), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("ix_clicks_id", "clicks", ["id"])
    op.create_index("ix_clicks_url_id", "clicks", ["url_id"])


def downgrade() -> None:
    op.drop_table("clicks")
    op.drop_table("urls")
