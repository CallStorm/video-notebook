"""collections and collection_notebooks"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0013_collections"
down_revision: str | None = "0012"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("icon", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_collections_owner_id", "collections", ["owner_id"])

    op.create_table(
        "collection_notebooks",
        sa.Column("collection_id", sa.BigInteger(), nullable=False),
        sa.Column("notebook_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("collection_id", "notebook_id"),
    )


def downgrade() -> None:
    op.drop_table("collection_notebooks")
    op.drop_index("ix_collections_owner_id", table_name="collections")
    op.drop_table("collections")
