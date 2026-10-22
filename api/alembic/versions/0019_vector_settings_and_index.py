"""vector_settings_config + notebook_index_states; restore embedding role in app.

MySQL ENUM for default_models.role already includes embedding (see 0014).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0019_vector_settings_and_index"
down_revision: str | None = "0018_subtitle_slice_settings"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "vector_settings_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("vector_backend", sa.String(32), nullable=False, server_default="qdrant"),
        sa.Column(
            "qdrant_url",
            sa.String(512),
            nullable=False,
            server_default="http://127.0.0.1:6333",
        ),
        sa.Column("qdrant_api_key", sa.String(512), nullable=True),
        sa.Column(
            "qdrant_collection",
            sa.String(128),
            nullable=False,
            server_default="notebooks",
        ),
        sa.Column("index_title", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "index_description", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "index_overview", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "index_subtitles", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("index_notes", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO vector_settings_config "
            "(id, vector_backend, qdrant_url, qdrant_collection, "
            "index_title, index_description, index_overview, index_subtitles, index_notes) "
            "VALUES (1, 'qdrant', 'http://127.0.0.1:6333', 'notebooks', 1, 1, 1, 0, 0)"
        )
    )

    op.create_table(
        "notebook_index_states",
        sa.Column("notebook_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("vector_dim", sa.Integer(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notebook_id"],
            ["notebooks.id"],
            name="fk_notebook_index_states_notebook_id_notebooks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notebook_id"),
    )

    # Ensure ENUM still lists embedding (idempotent for DBs that already have it)
    op.execute(
        sa.text(
            "ALTER TABLE default_models MODIFY COLUMN role "
            "ENUM('chat','stt','tts','embedding','logo') NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_table("notebook_index_states")
    op.drop_table("vector_settings_config")
