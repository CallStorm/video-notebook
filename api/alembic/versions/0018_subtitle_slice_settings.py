"""subtitle_slice_settings_config for ASR silence slicing."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0018_subtitle_slice_settings"
down_revision: str | None = "0017_collection_cover"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "subtitle_slice_settings_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("max_slice_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("min_slice_ms", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("silence_noise_db", sa.Float(), nullable=False, server_default="-32"),
        sa.Column("silence_min_duration_s", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("min_silence_for_cut_ms", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO subtitle_slice_settings_config "
            "(id, max_slice_seconds, min_slice_ms, silence_noise_db, "
            "silence_min_duration_s, min_silence_for_cut_ms) "
            "VALUES (1, 30, 600, -32, 0.3, 200)"
        )
    )


def downgrade() -> None:
    op.drop_table("subtitle_slice_settings_config")
