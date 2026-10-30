"""Add cover_image role + cover_settings image mode columns."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0024_cover_image"
down_revision: str | None = "0023_cover_settings"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE default_models MODIFY COLUMN role "
            "ENUM('chat','stt','tts','embedding','logo','cover_image') NOT NULL"
        )
    )
    op.add_column(
        "cover_settings_config",
        sa.Column(
            "mode",
            sa.String(16),
            nullable=False,
            server_default="image",
        ),
    )
    op.add_column(
        "cover_settings_config",
        sa.Column("image_prompt_system", sa.Text(), nullable=True),
    )
    op.add_column(
        "cover_settings_config",
        sa.Column("image_prompt_user", sa.Text(), nullable=True),
    )
    op.add_column(
        "cover_settings_config",
        sa.Column(
            "image_size",
            sa.String(32),
            nullable=False,
            server_default="1024x1024",
        ),
    )


def downgrade() -> None:
    op.drop_column("cover_settings_config", "image_size")
    op.drop_column("cover_settings_config", "image_prompt_user")
    op.drop_column("cover_settings_config", "image_prompt_system")
    op.drop_column("cover_settings_config", "mode")
    op.execute(sa.text("DELETE FROM default_models WHERE role = 'cover_image'"))
    op.execute(
        sa.text(
            "ALTER TABLE default_models MODIFY COLUMN role "
            "ENUM('chat','stt','tts','embedding','logo') NOT NULL"
        )
    )
