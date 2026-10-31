"""tags + notebook_tags; migrate collections -> tags."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0031_tags"
down_revision: str | None = "0030_draft_max_tokens"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=True),
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
        sa.UniqueConstraint("owner_id", "name", name="uq_tags_owner_id_name"),
    )
    op.create_index("ix_tags_owner_id", "tags", ["owner_id"])

    op.create_table(
        "notebook_tags",
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("notebook_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tag_id", "notebook_id"),
    )

    # Data migration: collections -> tags (same name); membership -> notebook_tags.
    # Collections tables are kept for compatibility / rollback; UI is retired.
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())
    if "collections" not in tables or "collection_notebooks" not in tables:
        return

    colors = [
        "#2F6B4F",
        "#3B82F6",
        "#8B5CF6",
        "#F59E0B",
        "#EF4444",
        "#06B6D4",
        "#EC4899",
        "#84CC16",
    ]
    collections = conn.execute(
        sa.text(
            "SELECT id, owner_id, name FROM collections ORDER BY owner_id ASC, id ASC"
        )
    ).fetchall()
    # (owner_id, name) -> tag_id
    tag_key_to_id: dict[tuple[int, str], int] = {}
    owner_counts: dict[int, int] = {}
    for cid, owner_id, name in collections:
        cleaned = (name or "").strip()[:64] or f"集合{cid}"
        key = (int(owner_id), cleaned)
        if key in tag_key_to_id:
            continue
        idx = owner_counts.get(int(owner_id), 0)
        owner_counts[int(owner_id)] = idx + 1
        color = colors[idx % len(colors)]
        # skip if tag already exists (idempotent re-run safety)
        existing = conn.execute(
            sa.text(
                "SELECT id FROM tags WHERE owner_id = :oid AND name = :name LIMIT 1"
            ),
            {"oid": int(owner_id), "name": cleaned},
        ).fetchone()
        if existing:
            tag_key_to_id[key] = int(existing[0])
            continue
        conn.execute(
            sa.text(
                "INSERT INTO tags (owner_id, name, color) VALUES (:oid, :name, :color)"
            ),
            {"oid": int(owner_id), "name": cleaned, "color": color},
        )
        new_id = conn.execute(
            sa.text(
                "SELECT id FROM tags WHERE owner_id = :oid AND name = :name LIMIT 1"
            ),
            {"oid": int(owner_id), "name": cleaned},
        ).fetchone()
        if new_id:
            tag_key_to_id[key] = int(new_id[0])

    # Map collection_id -> tag_id
    coll_to_tag: dict[int, int] = {}
    for cid, owner_id, name in collections:
        cleaned = (name or "").strip()[:64] or f"集合{cid}"
        tid = tag_key_to_id.get((int(owner_id), cleaned))
        if tid is not None:
            coll_to_tag[int(cid)] = tid

    members = conn.execute(
        sa.text("SELECT collection_id, notebook_id FROM collection_notebooks")
    ).fetchall()
    for collection_id, notebook_id in members:
        tid = coll_to_tag.get(int(collection_id))
        if tid is None:
            continue
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM notebook_tags WHERE tag_id = :tid AND notebook_id = :nid LIMIT 1"
            ),
            {"tid": tid, "nid": int(notebook_id)},
        ).fetchone()
        if exists:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO notebook_tags (tag_id, notebook_id) VALUES (:tid, :nid)"
            ),
            {"tid": tid, "nid": int(notebook_id)},
        )


def downgrade() -> None:
    op.drop_table("notebook_tags")
    op.drop_index("ix_tags_owner_id", table_name="tags")
    op.drop_table("tags")
