"""observability: pipeline runs + llm traces + settings."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0022_observability"
down_revision: str | None = "0021_chat_settings"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "observability_settings_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "pipeline_logs_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "llm_traces_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column(
            "success_sample_rate", sa.Float(), nullable=False, server_default="1"
        ),
        sa.Column(
            "llm_record_full", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "llm_truncate_chars", sa.Integer(), nullable=False, server_default="4096"
        ),
        sa.Column(
            "max_pipeline_run_rows",
            sa.Integer(),
            nullable=False,
            server_default="50000",
        ),
        sa.Column(
            "max_llm_trace_rows",
            sa.Integer(),
            nullable=False,
            server_default="20000",
        ),
        sa.Column(
            "langfuse_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO observability_settings_config "
            "(id, pipeline_logs_enabled, llm_traces_enabled, retention_days, "
            "success_sample_rate, llm_record_full, llm_truncate_chars, "
            "max_pipeline_run_rows, max_llm_trace_rows, langfuse_enabled) "
            "VALUES (1, 0, 0, 7, 1, 0, 4096, 50000, 20000, 0)"
        )
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=True),
        sa.Column("notebook_id", sa.Integer(), nullable=True),
        sa.Column("stage", sa.String(32), nullable=False, server_default="full"),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("force", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "record_success", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("celery_task_id", sa.String(64), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.UniqueConstraint("run_id", name="uq_pipeline_runs_run_id"),
    )
    op.create_index("ix_pipeline_runs_video_id", "pipeline_runs", ["video_id"])
    op.create_index(
        "ix_pipeline_runs_video_started", "pipeline_runs", ["video_id", "started_at"]
    )
    op.create_index(
        "ix_pipeline_runs_status_started", "pipeline_runs", ["status", "started_at"]
    )
    op.create_index("ix_pipeline_runs_started", "pipeline_runs", ["started_at"])

    op.create_table(
        "pipeline_run_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary", sa.String(512), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_pipeline_run_events_run_id", "pipeline_run_events", ["run_id"])
    op.create_index(
        "ix_pipeline_run_events_run_seq", "pipeline_run_events", ["run_id", "seq"]
    )
    op.create_index(
        "ix_pipeline_run_events_stage_started",
        "pipeline_run_events",
        ["stage", "started_at"],
    )

    op.create_table(
        "llm_traces",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("notebook_id", sa.Integer(), nullable=True),
        sa.Column("video_id", sa.Integer(), nullable=True),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("trace_id", name="uq_llm_traces_trace_id"),
    )
    op.create_index("ix_llm_traces_notebook_id", "llm_traces", ["notebook_id"])
    op.create_index("ix_llm_traces_video_id", "llm_traces", ["video_id"])
    op.create_index("ix_llm_traces_kind_started", "llm_traces", ["kind", "started_at"])
    op.create_index(
        "ix_llm_traces_status_started", "llm_traces", ["status", "started_at"]
    )
    op.create_index("ix_llm_traces_started", "llm_traces", ["started_at"])

    op.create_table(
        "llm_spans",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("role", sa.String(32), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_llm_spans_trace_id", "llm_spans", ["trace_id"])
    op.create_index("ix_llm_spans_trace_seq", "llm_spans", ["trace_id", "seq"])


def downgrade() -> None:
    op.drop_table("llm_spans")
    op.drop_table("llm_traces")
    op.drop_table("pipeline_run_events")
    op.drop_table("pipeline_runs")
    op.drop_table("observability_settings_config")
