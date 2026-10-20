"""fetch_settings_config for concurrency, timeout, chunked download."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0016_fetch_settings_config"
down_revision: str | None = "0015_fetch_network_config"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "fetch_settings_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("max_concurrent", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("task_timeout_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("chunk_parallel_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("chunk_min_mb", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO fetch_settings_config "
            "(id, max_concurrent, task_timeout_minutes, chunk_parallel_enabled, "
            "chunk_count, chunk_min_mb) "
            "VALUES (1, 2, 30, 1, 4, 20)"
        )
    )


def downgrade() -> None:
    op.drop_table("fetch_settings_config")
