"""chat_settings_config: history_limit for notebook chat."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0021_chat_settings"
down_revision: str | None = "0020_overview_settings"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "chat_settings_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "history_limit",
            sa.Integer(),
            nullable=False,
            server_default="8",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO chat_settings_config (id, history_limit) VALUES (1, 8)"
        )
    )


def downgrade() -> None:
    op.drop_table("chat_settings_config")
