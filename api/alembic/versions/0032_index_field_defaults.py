"""index conclusions + draft; default every index field on."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0032_index_field_defaults"
down_revision: str | None = "0031_tags"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "vector_settings_config",
        sa.Column(
            "index_conclusions",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "vector_settings_config",
        sa.Column(
            "index_draft",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.alter_column(
        "vector_settings_config",
        "index_subtitles",
        server_default=sa.text("1"),
    )
    op.alter_column(
        "vector_settings_config",
        "index_notes",
        server_default=sa.text("1"),
    )
    op.execute(
        "UPDATE vector_settings_config SET "
        "index_title=1, index_description=1, index_overview=1, "
        "index_subtitles=1, index_notes=1, index_conclusions=1, index_draft=1"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE vector_settings_config SET index_subtitles=0, index_notes=0"
    )
    op.alter_column(
        "vector_settings_config",
        "index_notes",
        server_default=sa.text("0"),
    )
    op.alter_column(
        "vector_settings_config",
        "index_subtitles",
        server_default=sa.text("0"),
    )
    op.drop_column("vector_settings_config", "index_draft")
    op.drop_column("vector_settings_config", "index_conclusions")
