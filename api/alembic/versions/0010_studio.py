"""studio tables and notes.selected_for_chat"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0010_studio"
down_revision: str | None = "0009_notes"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "notes",
        sa.Column(
            "selected_for_chat",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
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
    )

    op.create_table(
        "agents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=32),
            nullable=False,
            server_default="claude_code",
        ),
        sa.Column("skill_id", sa.BigInteger(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.BigInteger(), nullable=False),
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
            ["skill_id"],
            ["skills.id"],
            name="fk_agents_skill_id_skills",
        ),
    )
    op.create_index("ix_agents_skill_id", "agents", ["skill_id"])

    op.create_table(
        "studio_capabilities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("icon", sa.String(length=16), nullable=True),
        sa.Column("format_key", sa.String(length=32), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("form_json", sa.JSON(), nullable=False),
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
            ["agent_id"],
            ["agents.id"],
            name="fk_studio_capabilities_agent_id_agents",
        ),
    )
    op.create_index(
        "ix_studio_capabilities_agent_id", "studio_capabilities", ["agent_id"]
    )

    op.create_table(
        "studio_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("notebook_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("capability_id", sa.BigInteger(), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("format_key", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
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
            name="fk_studio_tasks_notebook_id_notebooks",
        ),
        sa.ForeignKeyConstraint(
            ["capability_id"],
            ["studio_capabilities.id"],
            name="fk_studio_tasks_capability_id_studio_capabilities",
        ),
    )
    op.create_index("ix_studio_tasks_notebook_id", "studio_tasks", ["notebook_id"])
    op.create_index("ix_studio_tasks_owner_id", "studio_tasks", ["owner_id"])
    op.create_index("ix_studio_tasks_capability_id", "studio_tasks", ["capability_id"])

    op.create_table(
        "studio_artifacts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["studio_tasks.id"],
            name="fk_studio_artifacts_task_id_studio_tasks",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_studio_artifacts_task_id", "studio_artifacts", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_studio_artifacts_task_id", table_name="studio_artifacts")
    op.drop_table("studio_artifacts")
    op.drop_index("ix_studio_tasks_capability_id", table_name="studio_tasks")
    op.drop_index("ix_studio_tasks_owner_id", table_name="studio_tasks")
    op.drop_index("ix_studio_tasks_notebook_id", table_name="studio_tasks")
    op.drop_table("studio_tasks")
    op.drop_index("ix_studio_capabilities_agent_id", table_name="studio_capabilities")
    op.drop_table("studio_capabilities")
    op.drop_index("ix_agents_skill_id", table_name="agents")
    op.drop_table("agents")
    op.drop_table("skills")
    op.drop_column("notes", "selected_for_chat")
