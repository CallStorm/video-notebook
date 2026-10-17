"""Aliyun / Volcengine ASR adapter 占位。

Phase 3.3 起仅留接口与异常；Phase 6 引入 yt-dlp 与完整流水线时再实装。
任何调用都报 NotImplementedError，把这条路直接挡住，免得误用。
"""
from __future__ import annotations

from app.asr.base import AsrAdapter, AsrError, AsrResult, AsrSubmission
from app.models.model_config import AsrConfig


class _NotConfigured(AsrAdapter):
    def __init__(self, config: AsrConfig, api_key: str, name: str) -> None:
        super().__init__(config, api_key)
        self._name = name

    async def submit(
        self, audio_url: str, *, language: str | None = None
    ) -> AsrSubmission:
        raise AsrError(
            f"{self._name} ASR adapter 未实装（v1 默认走 OpenAI Whisper）。"
            "请在 Phase 6 接好后使用。"
        )

    async def fetch_result(self, submission: AsrSubmission | str) -> AsrResult:
        raise AsrError(f"{self._name} adapter not configured")

    async def cancel(self, submission: AsrSubmission | str) -> None:
        return None


class AliyunStubAdapter(_NotConfigured):
    def __init__(self, config: AsrConfig, api_key: str) -> None:
        super().__init__(config, api_key, "阿里云语音")


class VolcengineStubAdapter(_NotConfigured):
    def __init__(self, config: AsrConfig, api_key: str) -> None:
        super().__init__(config, api_key, "字节火山引擎")
