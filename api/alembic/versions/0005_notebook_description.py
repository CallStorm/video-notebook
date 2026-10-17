"""add notebooks.description column

Phase 4.6：新建笔记本弹窗要 name + description。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005_notebook_description"
down_revision: str | None = "0004_notebooks_videos"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "notebooks",
        sa.Column("description", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notebooks", "description")
