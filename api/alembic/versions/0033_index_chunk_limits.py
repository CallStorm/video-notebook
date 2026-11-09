"""per-part index chunk size and overlap."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0033_index_chunk_limits"
down_revision: str | None = "0032_index_field_defaults"
branch_labels: str | None = None
depends_on: str | None = None

_CHUNK_COLUMNS = (
    "chunk_card_chars",
    "chunk_subtitles_chars",
    "chunk_notes_chars",
    "chunk_conclusions_chars",
    "chunk_draft_chars",
)


def upgrade() -> None:
    for name in _CHUNK_COLUMNS:
        op.add_column(
            "vector_settings_config",
            sa.Column(name, sa.Integer(), nullable=False, server_default="6000"),
        )
    op.add_column(
        "vector_settings_config",
        sa.Column(
            "chunk_overlap_chars",
            sa.Integer(),
            nullable=False,
            server_default="200",
        ),
    )


def downgrade() -> None:
    op.drop_column("vector_settings_config", "chunk_overlap_chars")
    for name in reversed(_CHUNK_COLUMNS):
        op.drop_column("vector_settings_config", name)
