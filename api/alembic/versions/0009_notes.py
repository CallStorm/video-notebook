"""notes saved from chat answers"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0009_notes"
down_revision: str | None = "0008_chat"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("notebook_id", sa.BigInteger(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["notebook_id"],
            ["notebooks.id"],
            name="fk_notes_notebook_id_notebooks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name="fk_notes_message_id_chat_messages",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("message_id", name="uq_notes_message"),
    )
    op.create_index("ix_notes_notebook_id", "notes", ["notebook_id"])


def downgrade() -> None:
    op.drop_index("ix_notes_notebook_id", table_name="notes")
    op.drop_table("notes")
