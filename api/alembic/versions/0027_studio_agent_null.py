"""Make studio_tasks.agent_id nullable — plugins no longer require agents."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0027_studio_agent_null"
down_revision: str | None = "0026_chat_context_chars"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("studio_tasks") as batch:
        batch.alter_column(
            "agent_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(sa.text("UPDATE studio_tasks SET agent_id = 0 WHERE agent_id IS NULL"))
    with op.batch_alter_table("studio_tasks") as batch:
        batch.alter_column(
            "agent_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
