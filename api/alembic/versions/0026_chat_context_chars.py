"""chat_settings_config: max_context_chars for notebook chat budget."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0026_chat_context_chars"
down_revision: str | None = "0025_llm_trace_notebook_backfill"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "chat_settings_config",
        sa.Column(
            "max_context_chars",
            sa.Integer(),
            nullable=False,
            server_default="60000",
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_settings_config", "max_context_chars")
