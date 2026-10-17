"""add videos.subtitle_status / subtitle_error

上传后的字幕流水线要用这两列告诉前端：等待、生成中、已就绪、失败。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006_subtitle_status"
down_revision: str | None = "0005_notebook_description"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column(
            "subtitle_status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "videos",
        sa.Column("subtitle_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("videos", "subtitle_error")
    op.drop_column("videos", "subtitle_status")
