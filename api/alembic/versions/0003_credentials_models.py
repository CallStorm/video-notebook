"""split llm_configs/asr_configs into credentials + models + default_models

Phase 3.5 重构。把旧的「单表嵌密文 + 模型名」拆成 open-notebook 风格的
三表：credentials 装账号密钥，models 装命名模型，default_models 装 role → model_id。

数据迁移：
- 任意已存在的 llm_configs 行 → credentials (1 行) + models (1 行) + default_models.role='chat'
- 任意已存在的 asr_configs 行 → credentials (1 行) + models (1 行) + default_models.role='stt'
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_credentials_models"
down_revision: str | None = "0002_model_configs"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1) 新表三张
    op.create_table(
        "credentials",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("modalities_json", sa.JSON(), nullable=False, server_default=sa.text("JSON_ARRAY()")),
        sa.Column("api_key_enc", sa.String(length=1024), nullable=True),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_credentials_provider", "credentials", ["provider"], unique=False)

    op.create_table(
        "models",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column(
            "type",
            sa.Enum("language", "embedding", "speech_to_text", "text_to_speech", name="model_type"),
            nullable=False,
        ),
        sa.Column("credential_id", sa.BigInteger(), nullable=False),
        sa.Column("is_default_provider", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"], name="fk_models_credential_id_credentials", ondelete="RESTRICT"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "uq_model_provider_name_type",
        "models",
        ["provider", "name", "type"],
        unique=True,
    )

    op.create_table(
        "default_models",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "role",
            sa.Enum("chat", "stt", "tts", "embedding", name="default_model_role"),
            nullable=False,
        ),
        sa.Column("model_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], name="fk_default_models_model_id_models", ondelete="RESTRICT"),
        sa.UniqueConstraint("role", name="uq_default_models_role"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # 2) 旧数据迁移（如果有）
    # llm_configs → chat role
    bind.execute(
        sa.text(
            """
            INSERT INTO credentials (name, provider, modalities_json, api_key_enc, base_url, config, is_builtin, created_at, updated_at)
            SELECT
                CONCAT('LLM-', provider) AS name,
                provider,
                JSON_ARRAY('language') AS modalities_json,
                api_key_enc,
                base_url,
                params_json,
                0 AS is_builtin,
                created_at,
                updated_at
            FROM llm_configs
            """
        )
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO models (name, provider, `type`, credential_id, is_default_provider, created_at, updated_at)
            SELECT
                m.model_name AS name,
                m.provider AS provider,
                'language' AS `type`,
                c.id AS credential_id,
                1 AS is_default_provider,
                m.created_at,
                m.updated_at
            FROM llm_configs m
            JOIN credentials c
              ON c.id = (
                SELECT id FROM credentials
                WHERE provider = m.provider
                ORDER BY id DESC
                LIMIT 1
              )
            """
        )
    )

    # 给每个 chat 模型打 default_models
    bind.execute(
        sa.text(
            """
            INSERT INTO default_models (role, model_id)
            SELECT 'chat' AS role, mo.id AS model_id
            FROM models mo
            JOIN llm_configs lc ON lc.provider = mo.provider AND lc.model_name = mo.name
            WHERE mo.`type` = 'language'
            AND NOT EXISTS (SELECT 1 FROM default_models WHERE role='chat')
            """
        )
    )

    # asr_configs → stt role
    bind.execute(
        sa.text(
            """
            INSERT INTO credentials (name, provider, modalities_json, api_key_enc, base_url, config, is_builtin, created_at, updated_at)
            SELECT
                CONCAT('ASR-', provider) AS name,
                provider,
                JSON_ARRAY('speech_to_text') AS modalities_json,
                api_key_enc,
                NULL AS base_url,
                JSON_OBJECT('model_size', model_size, 'language_policy', language_policy, 'fixed_language', fixed_language) AS config,
                0 AS is_builtin,
                created_at,
                updated_at
            FROM asr_configs
            """
        )
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO models (name, provider, `type`, credential_id, is_default_provider, created_at, updated_at)
            SELECT
                CONCAT('whisper-', ac.model_size) AS name,
                ac.provider AS provider,
                'speech_to_text' AS `type`,
                c.id AS credential_id,
                1 AS is_default_provider,
                ac.created_at,
                ac.updated_at
            FROM asr_configs ac
            JOIN credentials c
              ON c.id = (
                SELECT id FROM credentials
                WHERE provider = ac.provider
                ORDER BY id DESC
                LIMIT 1
              )
            """
        )
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO default_models (role, model_id)
            SELECT 'stt' AS role, mo.id AS model_id
            FROM models mo
            JOIN asr_configs ac ON ac.provider = mo.provider
            WHERE mo.`type` = 'speech_to_text'
            AND NOT EXISTS (SELECT 1 FROM default_models WHERE role='stt')
            """
        )
    )

    # 3) 删旧表
    op.drop_table("asr_configs")
    op.drop_table("llm_configs")


def downgrade() -> None:
    # 撤回到三表分离前的形态
    bind = op.get_bind()

    op.create_table(
        "llm_configs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("api_key_enc", sa.String(length=1024), nullable=True),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "asr_configs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("api_key_enc", sa.String(length=1024), nullable=True),
        sa.Column("model_size", sa.String(length=32), nullable=False, server_default="large-v3"),
        sa.Column(
            "language_policy",
            sa.Enum("auto", "fixed", name="asr_language_policy"),
            nullable=False,
            server_default="auto",
        ),
        sa.Column("fixed_language", sa.String(length=16), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO llm_configs (provider, base_url, api_key_enc, model_name, params_json, is_active, created_at, updated_at)
            SELECT c.provider, c.base_url, c.api_key_enc, m.name AS model_name, c.config, 1, c.created_at, c.updated_at
            FROM credentials c JOIN models m ON m.credential_id = c.id
            WHERE m.`type`='language'
            """
        )
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO asr_configs (provider, api_key_enc, model_size, language_policy, fixed_language, is_active, created_at, updated_at)
            SELECT c.provider, c.api_key_enc,
                   COALESCE(JSON_UNQUOTE(JSON_EXTRACT(c.config, '$.model_size')), 'large-v3') AS model_size,
                   COALESCE(JSON_UNQUOTE(JSON_EXTRACT(c.config, '$.language_policy')), 'auto') AS language_policy,
                   JSON_UNQUOTE(JSON_EXTRACT(c.config, '$.fixed_language')) AS fixed_language,
                   1 AS is_active,
                   c.created_at, c.updated_at
            FROM credentials c JOIN models m ON m.credential_id = c.id
            WHERE m.`type`='speech_to_text'
            """
        )
    )

    op.drop_table("default_models")
    op.drop_table("models")
    op.drop_index("ix_credentials_provider", table_name="credentials")
    op.drop_table("credentials")
