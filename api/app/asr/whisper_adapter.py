"""OpenAI Whisper API adapter。

OpenAI Whisper 是同步调用模型：传 audio URL → 立刻拿到转写结果。
adapter 内部仍按 submit/fetch_result 形态，但 fetch 直接同步返回。
"""
from __future__ import annotations

import uuid

from openai import AsyncOpenAI

from app.asr.base import AsrAdapter, AsrError, AsrResult, AsrSubmission
from app.models.model_config import AsrConfig


class WhisperAdapter(AsrAdapter):
    def __init__(self, config: AsrConfig, api_key: str) -> None:
        super().__init__(config, api_key)
        self._client = AsyncOpenAI(api_key=api_key, base_url=config.base_url or None)

    async def submit(
        self,
        audio_url: str,
        *,
        language: str | None = None,
    ) -> AsrSubmission:
        # OpenAI audio.transcriptions 是同步；这里直接把 result 缓存在内存里，
        # fetch_result 时返回。
        size = self.config.model_size or "large-v3"
        kwargs: dict = {"model": "whisper-1" if size in (None, "large-v3") else size}
        # 注：OpenAI 公共 API 上只有 whisper-1；其他大小仅 self-host / Azure 区分。
        # 提示用户：当 provider=whisper 时 model_size 字段 v1 暂不真正生效，仅 metadata。
        if language:
            kwargs["language"] = language
        try:
            # 让 OpenAI 直接 fetch 这个 URL（需 URL 可公网访问；我们的对象存储
            # 通过 signed URL 暴露后即可）。Phase 6 真正调用时再处理下载或代理。
            resp = await self._client.audio.transcriptions.create(
                file=None,  # type: ignore[arg-type]
                **kwargs,  # type: ignore[arg-type]
            )
        except Exception as exc:  # noqa: BLE001 — 上层统一捕
            raise AsrError(f"whisper submit failed: {exc.__class__.__name__}: {exc}") from exc

        # 把结果文本塞进 job_id 之后用 fetch 取出来
        job_id = f"whisper-{uuid.uuid4().hex[:12]}"
        _POOL[job_id] = resp
        return AsrSubmission(job_id=job_id)

    async def fetch_result(self, submission: AsrSubmission | str) -> AsrResult:
        job_id = submission.job_id if isinstance(submission, AsrSubmission) else submission
        resp = _POOL.pop(job_id, None)
        if resp is None:
            raise AsrError(f"job not found or already consumed: {job_id}")
        text = getattr(resp, "text", "") or ""
        srt = _wrap_text_as_srt(text)
        return AsrResult(srt=srt, raw_json={"text": text})

    async def cancel(self, submission: AsrSubmission | str) -> None:
        job_id = submission.job_id if isinstance(submission, AsrSubmission) else submission
        _POOL.pop(job_id, None)


# 进程内同步缓存（OpenAI 同步调用结果）。
# WARNING：v1 极简，仅供 dev；生产应替换为 Redis 或 DB 表存储。
_POOL: dict[str, object] = {}


def _wrap_text_as_srt(text: str) -> str:
    """OpenAI whisper 默认只返文本（不开 verbose_json）。这里用整段一个 cue 包成 SRT。"""
    block_id = 1
    start = "00:00:00,000"
    end = "00:10:00,000"  # 占位时长；真实场景应接 verbose_json
    return f"{block_id}\n{start} --> {end}\n{text.strip()}\n\n"
