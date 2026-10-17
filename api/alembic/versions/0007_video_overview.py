"""add videos overview columns

重新生成来源时，字幕完成后用聊天模型写一段概览。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007_video_overview"
down_revision: str | None = "0006_subtitle_status"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column(
            "overview_status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("videos", sa.Column("overview_text", sa.Text(), nullable=True))
    op.add_column("videos", sa.Column("overview_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "overview_error")
    op.drop_column("videos", "overview_text")
    op.drop_column("videos", "overview_status")
