"""douyin parser base url, api key, and host rules."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0034_douyin_parser"
down_revision: str | None = "0033_index_chunk_limits"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "fetch_network_config",
        sa.Column(
            "douyin_parser_base_url",
            sa.String(length=512),
            nullable=False,
            server_default="http://127.0.0.1:8001",
        ),
    )
    op.add_column(
        "fetch_network_config",
        sa.Column("douyin_parser_api_key_enc", sa.Text(), nullable=True),
    )
    op.add_column(
        "fetch_network_config",
        sa.Column(
            "douyin_host_rules",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(
                "JSON_ARRAY('v.douyin.com', 'douyin.com', 'iesdouyin.com')"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("fetch_network_config", "douyin_host_rules")
    op.drop_column("fetch_network_config", "douyin_parser_api_key_enc")
    op.drop_column("fetch_network_config", "douyin_parser_base_url")
