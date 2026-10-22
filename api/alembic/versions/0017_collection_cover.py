"""Add cover_url to collections."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0017_collection_cover"
down_revision: str | None = "0016_fetch_settings_config"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "collections",
        sa.Column("cover_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("collections", "cover_url")
