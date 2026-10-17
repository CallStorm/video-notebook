"""create notebooks / videos / subtitles / subtitle_lines / notebook_sources

Phase 4：数据真正流进来的起点。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004_notebooks_videos"
down_revision: str | None = "0003_credentials_models"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notebooks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("icon", sa.String(length=16), nullable=True),
        sa.Column("cover_url", sa.String(length=512), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("share_all", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_notebooks_owner_id", "notebooks", ["owner_id"])
    op.create_index("ix_notebooks_owner_pinned", "notebooks", ["owner_id", "is_pinned"])
    op.create_index("ix_notebooks_share_all", "notebooks", ["share_all"])

    op.create_table(
        "videos",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("upload", "url", name="video_source_type"),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("mime", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("content_hash", sa.CHAR(40), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "probing", "ready", "failed", name="video_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("owner_id", "content_hash", name="uq_videos_owner_hash"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_videos_owner_id", "videos", ["owner_id"])

    op.create_table(
        "subtitles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("embedded", "platform", "asr", name="subtitle_source"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("format", sa.String(length=8), nullable=False, server_default="srt"),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], name="fk_subtitles_video_id_videos", ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "video_id", "source", "language", "version", name="uq_subtitle_video"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_subtitles_video_id", "subtitles", ["video_id"])

    op.create_table(
        "subtitle_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("subtitle_id", sa.BigInteger(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.BigInteger(), nullable=False),
        sa.Column("end_ms", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subtitle_id"],
            ["subtitles.id"],
            name="fk_subtitle_lines_subtitle_id_subtitles",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("subtitle_id", "line_no", name="ix_subtitle_lines_subtitle_line"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_subtitle_lines_subtitle_id", "subtitle_lines", ["subtitle_id"])

    op.create_table(
        "notebook_sources",
        sa.Column("notebook_id", sa.BigInteger(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "selected_for_chat",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.ForeignKeyConstraint(
            ["notebook_id"],
            ["notebooks.id"],
            name="fk_notebook_sources_notebook_id_notebooks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name="fk_notebook_sources_video_id_videos",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notebook_id", "video_id", name="pk_notebook_sources"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "ix_notebook_sources_video", "notebook_sources", ["video_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_notebook_sources_video", table_name="notebook_sources")
    op.drop_table("notebook_sources")
    op.drop_index("ix_subtitle_lines_subtitle_id", table_name="subtitle_lines")
    op.drop_table("subtitle_lines")
    op.drop_index("ix_subtitles_video_id", table_name="subtitles")
    op.drop_table("subtitles")
    op.drop_index("ix_videos_owner_id", table_name="videos")
    op.drop_table("videos")
    op.drop_index("ix_notebooks_share_all", table_name="notebooks")
    op.drop_index("ix_notebooks_owner_pinned", table_name="notebooks")
    op.drop_index("ix_notebooks_owner_id", table_name="notebooks")
    op.drop_table("notebooks")
