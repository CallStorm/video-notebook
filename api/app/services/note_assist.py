"""选区帮写、翻译、解读。不写入对话，结果里不保留引用编号。"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.context import build_context, strip_citations
from app.core.errors import BadRequestError
from app.llm.config_service import LlmResolved, get_active_llm
from app.llm.providers import make_provider
from app.models.notebook import Note
from app.observability.llm_trace import end_llm_trace, llm_span, start_llm_trace
from app.services.chat_settings import get_max_context_chars
from app.services.notebooks import get_notebook

logger = logging.getLogger(__name__)

_MARK = re.compile(r"\[\d+\]")
_OPEN = re.compile(r"\[\d*$")
_NUMBERED = re.compile(r"\[\d+\] ")

_WRITE = (
    "你是笔记助手。根据要求改写用户选中的文字。"
    "没有额外要求时，把这段话写顺，保留原意。"
    "只输出改写结果，不要解释，不要使用方括号编号。"
)
_TRANSLATE = (
    "你是笔记助手。翻译用户选中的文字。"
    "没有额外要求时，中文译成英文，英文译成中文。"
    "只输出译文，不要解释，不要使用方括号编号。"
)
_EXPLAIN = (
    "你是笔记助手。用中文解释用户选中的这段文字。"
    "只能根据给出的材料和选中文字，不要编造材料里没有的事实。"
    "没有材料时，只根据选中文字本身解释。"
    "用连贯的段落说明，不要使用方括号编号。"
)


class CitePeeler:
    """流式去掉完整的 [n]，并扣住末尾还没写完的编号。"""

    def __init__(self) -> None:
        self._hold = ""

    def push(self, token: str) -> str:
        self._hold += token
        match = _OPEN.search(self._hold)
        if match:
            head = self._hold[: match.start()]
            self._hold = self._hold[match.start() :]
        else:
            head = self._hold
            self._hold = ""
        return _MARK.sub("", head)

    def flush(self) -> str:
        text = _OPEN.sub("", _MARK.sub("", self._hold))
        self._hold = ""
        return text


async def prepare_note_assist(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    action: str,
    selection: str,
    instruction: str | None,
    prior: str | None,
    source_ids: list[int] | None,
    note_ids: list[int] | None,
) -> tuple[LlmResolved, str, str]:
    await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    picked = selection.strip()
    if not picked:
        raise BadRequestError("请先选中一段文字")
    materials = ""
    if action == "explain":
        materials = await _materials(
            session,
            notebook_id=notebook_id,
            source_ids=source_ids or [],
            note_ids=note_ids or [],
        )
    system = {"write": _WRITE, "translate": _TRANSLATE, "explain": _EXPLAIN}[action]
    prompt = _prompt(picked, instruction, prior, materials if action == "explain" else "")
    llm = await get_active_llm(session)
    return llm, system, prompt


async def stream_note_assist(
    llm: LlmResolved, *, notebook_id: int, system: str, prompt: str
) -> AsyncIterator[dict]:
    async for event in _stream(llm, notebook_id=notebook_id, system=system, prompt=prompt):
        yield event


async def _materials(
    session: AsyncSession,
    *,
    notebook_id: int,
    source_ids: list[int],
    note_ids: list[int],
) -> str:
    blocks: list[str] = []
    if source_ids:
        await _require_sources(session, notebook_id, source_ids)
        context = await build_context(session, notebook_id=notebook_id, source_ids=source_ids)
        plain = _NUMBERED.sub("", context.text).strip()
        if plain:
            blocks.append(plain)
    if note_ids:
        notes = await _require_notes(session, notebook_id, note_ids)
        for note in notes:
            body = strip_citations(note.content_text).strip()
            if body:
                blocks.append(f"笔记：{note.title}\n{body}")
    text = "\n\n".join(blocks)
    limit = await get_max_context_chars(session)
    if len(text) > limit:
        raise BadRequestError(
            f"勾选材料已超过上下文上限（{len(text)}/{limit} 字符）。请减少勾选后再解读。"
        )
    return text


def _prompt(selection: str, instruction: str | None, prior: str | None, materials: str) -> str:
    parts: list[str] = []
    if materials:
        parts.append(f"材料：\n{materials}")
    parts.append(f"选中文字：\n{selection}")
    extra = (instruction or "").strip()
    if extra:
        parts.append(f"额外要求：{extra}")
    previous = (prior or "").strip()
    if previous:
        parts.append(f"上一版结果：\n{previous}\n请按新的要求给出下一版，只输出下一版。")
    return "\n\n".join(parts)


async def _require_sources(session: AsyncSession, notebook_id: int, source_ids: list[int]) -> None:
    from app.models.notebook import NotebookSource

    found = set(
        (
            await session.execute(
                select(NotebookSource.video_id).where(
                    NotebookSource.notebook_id == notebook_id,
                    NotebookSource.video_id.in_(source_ids),
                )
            )
        ).scalars().all()
    )
    if found != set(source_ids):
        raise BadRequestError("来源不属于该笔记本")


async def _require_notes(session: AsyncSession, notebook_id: int, note_ids: list[int]) -> list[Note]:
    rows = (
        await session.execute(
            select(Note).where(
                Note.notebook_id == notebook_id,
                Note.deleted_at.is_(None),
                Note.id.in_(note_ids),
            )
        )
    ).scalars().all()
    if {row.id for row in rows} != set(note_ids):
        raise BadRequestError("笔记不属于该笔记本")
    return list(rows)


async def _stream(
    llm: LlmResolved, *, notebook_id: int, system: str, prompt: str
) -> AsyncIterator[dict]:
    provider = make_provider(
        provider_name=llm.provider,
        api_key=llm.api_key,
        base_url=llm.base_url,
        model_name=llm.model_name,
        params_json=llm.params_json,
    )
    trace_id = start_llm_trace(
        kind="note_assist",
        notebook_id=notebook_id,
        provider=llm.provider,
        model_name=llm.model_name,
    )
    llm_span(trace_id, "system", content=system, role="system")
    llm_span(trace_id, "user", content=prompt, role="user")
    peeler = CitePeeler()
    raw: list[str] = []
    t0 = time.perf_counter()
    stream_error: str | None = None
    try:
        async for token in provider.stream_chat(prompt, system=system, history=None, max_tokens=2048):
            raw.append(token)
            visible = peeler.push(token)
            if visible:
                yield {"type": "token", "t": visible}
        tail = peeler.flush()
        if tail:
            yield {"type": "token", "t": tail}
    except Exception as exc:  # noqa: BLE001 — 流里的失败要写成一条事件
        logger.warning("note assist failed notebook_id=%s: %s", notebook_id, exc)
        stream_error = str(exc)[:500]
        yield {"type": "error", "message": stream_error}
    text = strip_citations("".join(raw))
    if trace_id:
        if text:
            llm_span(trace_id, "generation", content=text, role="assistant")
        usage = getattr(provider, "last_usage", None)
        end_llm_trace(
            trace_id,
            status="failed" if stream_error else "ok",
            error_text=stream_error,
            t0=t0,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )
    yield {"type": "done", "text": text}
