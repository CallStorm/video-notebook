"""overview_settings_config: auto overview after subtitle + prompt."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0020_overview_settings"
down_revision: str | None = "0019_vector_settings_and_index"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "overview_settings_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "auto_generate_after_subtitle",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO overview_settings_config "
            "(id, auto_generate_after_subtitle, prompt_text) "
            "VALUES (1, 1, NULL)"
        )
    )


def downgrade() -> None:
    op.drop_table("overview_settings_config")
