"""fetch_network_config for per-platform cookies and proxy."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0015_fetch_network_config"
down_revision: str | None = "0014_default_model_logo"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "fetch_network_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("youtube_cookie_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("bilibili_cookie_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("douyin_cookie_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("proxy_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("proxy_url_enc", sa.Text(), nullable=True),
        sa.Column("proxy_apply_to", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO fetch_network_config "
            "(id, youtube_cookie_enabled, bilibili_cookie_enabled, douyin_cookie_enabled, "
            "proxy_enabled, proxy_url_enc, proxy_apply_to) "
            "VALUES (1, 0, 0, 0, 0, NULL, CAST('[]' AS JSON))"
        )
    )


def downgrade() -> None:
    op.drop_table("fetch_network_config")
