"""Backfill llm_traces.notebook_id from chat_threads / notebook_sources."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0025_llm_trace_notebook_backfill"
down_revision: str | None = "0024_cover_image"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # chat: thread → notebook
    op.execute(
        sa.text(
            """
            UPDATE llm_traces t
            INNER JOIN chat_threads ct ON ct.id = t.thread_id
            SET t.notebook_id = ct.notebook_id
            WHERE t.notebook_id IS NULL
              AND t.thread_id IS NOT NULL
              AND t.kind = 'chat'
            """
        )
    )
    # overview: video → first notebook_sources row
    op.execute(
        sa.text(
            """
            UPDATE llm_traces t
            INNER JOIN (
                SELECT video_id, MIN(notebook_id) AS notebook_id
                FROM notebook_sources
                GROUP BY video_id
            ) ns ON ns.video_id = t.video_id
            SET t.notebook_id = ns.notebook_id
            WHERE t.notebook_id IS NULL
              AND t.video_id IS NOT NULL
              AND t.kind = 'overview'
            """
        )
    )


def downgrade() -> None:
    # irreversible data fill
    pass
