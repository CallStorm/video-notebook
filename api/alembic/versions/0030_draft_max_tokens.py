"""draft_strategy_settings: max_tokens for knowledge draft generation."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0030_draft_max_tokens"
down_revision: str | None = "0029_knowledge_drafts"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "draft_strategy_settings",
        sa.Column(
            "max_tokens",
            sa.Integer(),
            nullable=False,
            server_default="200000",
        ),
    )


def downgrade() -> None:
    op.drop_column("draft_strategy_settings", "max_tokens")
