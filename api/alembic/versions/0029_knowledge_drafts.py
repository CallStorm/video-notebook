"""notebook knowledge drafts table."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0029_knowledge_drafts"
down_revision: str | None = "0028_draft_strategies"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notebook_knowledge_drafts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("notebook_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("strategy_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ready"),
        sa.Column("language", sa.String(length=32), nullable=False, server_default="zh"),
        sa.Column("model_ref", sa.String(length=32), nullable=False, server_default="inherit"),
        sa.Column("model_used", sa.String(length=255), nullable=True),
        # MySQL: TEXT/JSON cannot take DEFAULT ''
        sa.Column("conclusion", sa.Text(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False, server_default=sa.text("JSON_OBJECT()")),
        sa.Column("source_video_ids", sa.JSON(), nullable=False, server_default=sa.text("JSON_ARRAY()")),
        sa.Column("source_note_ids", sa.JSON(), nullable=False, server_default=sa.text("JSON_ARRAY()")),
        sa.Column("focus", sa.Text(), nullable=True),
        sa.Column("extra_constraints", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["draft_strategies.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("notebook_id", name="uq_notebook_knowledge_drafts_notebook_id"),
    )
    op.create_index(
        "ix_notebook_knowledge_drafts_owner_id",
        "notebook_knowledge_drafts",
        ["owner_id"],
    )
    op.create_index(
        "ix_notebook_knowledge_drafts_notebook_id",
        "notebook_knowledge_drafts",
        ["notebook_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notebook_knowledge_drafts_notebook_id",
        table_name="notebook_knowledge_drafts",
    )
    op.drop_index(
        "ix_notebook_knowledge_drafts_owner_id",
        table_name="notebook_knowledge_drafts",
    )
    op.drop_table("notebook_knowledge_drafts")
