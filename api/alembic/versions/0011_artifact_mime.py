"""widen studio_artifacts.mime so office document types fit"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010_studio"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "studio_artifacts",
        "mime",
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "studio_artifacts",
        "mime",
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
