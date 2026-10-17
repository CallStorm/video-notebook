"""ASR adapter 接口。

设计 §3.2 与 §7.2 描述了视频字幕的 ASR 流水线。
本接口的最小集：异步提交 → 拉取 SRT/JSON 结果。

不同厂商的调用形态差异很大（OpenAI 同步、阿里云异步轮询、字节类似）；
v1 默认实现是 OpenAI Whisper API（同步转写完成），adapter 通过
`asyncmy` 把同步调用包成 async。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.model_config import AsrConfig


@dataclass
class AsrSubmission:
    job_id: str
    """adapter 内部分配的 job id；后续用 fetch_result(job_id) 拿结果。"""


@dataclass
class AsrResult:
    srt: str            # 行级时间戳 + 文本
    raw_json: dict      # 厂商原始 JSON，便于后续做行号索引（设计 §5.2 字幕表）


class AsrError(Exception):
    """adapter 调用错误。"""


class AsrAdapter(ABC):
    config: AsrConfig
    api_key: str

    def __init__(self, config: AsrConfig, api_key: str) -> None:
        self.config = config
        self.api_key = api_key

    @abstractmethod
    async def submit(
        self,
        audio_url: str,
        *,
        language: str | None = None,
    ) -> AsrSubmission:
        """提交一段可访问的音频 / 视频 URL；返回 job id。"""

    @abstractmethod
    async def fetch_result(self, submission: AsrSubmission | str) -> AsrResult:
        """拉已完成的 SRT + JSON。job_id 跟 submit 返回一致。"""

    @abstractmethod
    async def cancel(self, submission: AsrSubmission | str) -> None:
        """取消任务（若厂商支持）。"""


def make_adapter(config: AsrConfig, api_key: str) -> AsrAdapter:
    """统一工厂：依据 provider 选择具体实现。"""
    if config.provider == "whisper":
        from app.asr.whisper_adapter import WhisperAdapter

        return WhisperAdapter(config, api_key)
    if config.provider == "aliyun":
        from app.asr.stubs import AliyunStubAdapter

        return AliyunStubAdapter(config, api_key)
    if config.provider == "volcengine":
        from app.asr.stubs import VolcengineStubAdapter

        return VolcengineStubAdapter(config, api_key)
    raise AsrError(f"unknown provider: {config.provider}")
