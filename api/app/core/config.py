"""全局配置：仅依赖环境变量，不读 DB。

所有 Service 层需要的设置从 `get_settings()` 单例取；测试可用 `get_settings.cache_clear()` + monkeypatch env。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import find_dotenv
from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 找最近的 .env：从本文件位置向上搜索。开发期直接 `make api` 即可生效，
# 不必把 .env 复制到 api/ 目录里。
_DOTENV_PATH = find_dotenv(filename=".env", usecwd=False) or ".env"

# api/app/core/config.py → 仓库根。相对路径一律相对这里解析，避免 cwd 在 api/ 时写偏。
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_DOTENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── 应用 ─────────────────────────────────────────────────────────────
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "video-notebook-api"
    debug: bool = True
    log_level: str = "INFO"
    api_prefix: str = "/api"

    # ─── 服务端 ──────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 2

    # ─── 数据库 ──────────────────────────────────────────────────────────
    # 默认走 127.0.0.1（开发期：compose.middleware.yml 把 mysql 绑到 localhost）。
    # 部署到容器内部时设 MYSQL_HOST=db 即可。
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "vnb"
    mysql_password: str = "changeme-vnb"
    mysql_database: str = "video_notebook"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"mysql+asyncmy://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_sync_url(self) -> str:
        """Alembic 同步 URL（migration 用）。"""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )

    # ─── Redis / Celery ──────────────────────────────────────────────────
    # 同理：开发期默认 127.0.0.1；容器内部署把 host 改为 redis。
    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"

    # ─── 安全 ─────────────────────────────────────────────────────────────
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 7200       # 2 h
    jwt_refresh_ttl_seconds: int = 604800    # 7 d

    # 全局 AES-GCM 主密钥（用于 DB 内 api_key_enc 解密）
    master_secret: str = "change-me-master"

    # ─── 存储 ─────────────────────────────────────────────────────────────
    # 开发期默认写仓库目录（macOS 上 /data 不可创建）。
    # 容器部署再覆盖：STORAGE_ROOT=/data/video-notebook  SKILLS_ROOT=/data/skills
    storage_root: Path = _REPO_ROOT / "storage"
    skills_root: Path = _REPO_ROOT / "skills"

    @field_validator("storage_root", "skills_root", mode="before")
    @classmethod
    def _anchor_data_dir(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = (_REPO_ROOT / path).resolve()
        return path

    # ─── 第三方服务（先放环境变量；Phase 3 起从 DB 读 model_configs） ──────
    llm_provider: str = "minimax"
    llm_base_url: str | None = None   # Anthropic-兼容 base_url
    llm_api_key: str | None = None
    llm_model_name: str | None = None

    asr_provider: str = "whisper"
    asr_api_key: str | None = None
    asr_model_size: str = "large-v3"
    asr_language_policy: Literal["auto", "fixed"] = "auto"

    # Claude Code
    anthropic_api_key: str | None = None
    claude_cli_path: str = "claude"  # override with CLAUDE_CLI_PATH absolute path on Windows

    # ─── 首个管理员 seed ────────────────────────────────────────────────
    seed_admin_phone: str | None = None
    seed_admin_password: str | None = None

    # Cookie / 代理改由后台「抓取与网络」配置，不再读 YTDLP_COOKIES_*。

    # ffmpeg 目录或可执行文件路径（可选）。未设时会探测 PATH / WinGet / scoop。
    # Celery media-worker 常缺交互终端的 PATH，建议显式配置或依赖自动探测。
    ffmpeg_location: str | None = None

    # ─── LLM 调用护栏 ────────────────────────────────────────────────────
    max_context_tokens: int = 60000

    # ─── 对话 ─────────────────────────────────────────────────────────────
    # 最近 N 轮（用户+助手成对）。可被管理后台 chat_settings_config 覆盖。
    chat_history_limit: int = 8


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
