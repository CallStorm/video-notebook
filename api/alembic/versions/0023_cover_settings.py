"""cover_settings_config: prompts + temperature for SVG cover generation."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0023_cover_settings"
down_revision: str | None = "0022_observability"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "cover_settings_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("prompt_system", sa.Text(), nullable=True),
        sa.Column("prompt_user", sa.Text(), nullable=True),
        sa.Column(
            "temperature",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
        sa.Column(
            "force_keyword_motif",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "fallback_on_error",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO cover_settings_config "
            "(id, prompt_system, prompt_user, temperature, force_keyword_motif, fallback_on_error) "
            "VALUES (1, NULL, NULL, 0.5, 1, 0)"
        )
    )


def downgrade() -> None:
    op.drop_table("cover_settings_config")
