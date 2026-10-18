"""claude code connection settings; drop per-agent model name"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "claude_code_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_key_enc", sa.Text(), nullable=True),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.drop_column("agents", "model_name")


def downgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("model_name", sa.String(length=128), nullable=False, server_default=""),
    )
    op.drop_table("claude_code_config")
