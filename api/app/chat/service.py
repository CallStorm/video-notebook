"""笔记本对话：每轮全量勾选字幕 + 最近 N 轮历史，流式写回并保存引用。"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.context import (
    MAX_CONTEXT_CHARS,
    BuiltContext,
    build_context,
    parse_citations,
    strip_citations,
)
from app.core.errors import BadRequestError, NotFoundError
from app.db.session import get_sessionmaker
from app.llm.config_service import LlmResolved, get_active_llm
from app.llm.providers import make_provider
from app.models.notebook import ChatMessage, ChatThread, Note, NotebookSource
from app.services.chat_settings import get_history_limit
from app.services.notebooks import get_notebook, get_notebook_readable

logger = logging.getLogger(__name__)

_SYSTEM = (
    "你是视频笔记助手。只能根据这次给出的字幕回答，不要编造字幕里没有的事实。"
    "依据某句字幕时，在句末用它前面的编号引用，例如 [1]。"
    "编号必须来自这次字幕，不要沿用历史回答里的编号，也不要自己发明。"
    "用中文回答。"
)
_SYSTEM_WITH_NOTES = (
    "你是视频笔记助手。可以根据这次给出的字幕和笔记回答，不要编造两者里都没有的事实。"
    "依据某句字幕时，在句末用它前面的编号引用，例如 [1]。"
    "编号必须来自这次字幕，不要沿用历史回答里的编号，也不要自己发明。"
    "笔记没有编号，不要给笔记编造 [n]。"
    "用中文回答。"
)

_SOURCES_TOO_LARGE = (
    "勾选来源的字幕全文已超过上下文上限（{chars}/{limit} 字符）。"
    "请减少勾选的来源后再提问；当前策略不会截断勾选全文。"
)


@dataclass
class PreparedChat:
    thread_id: int
    prompt: str
    history: list[dict[str, str]]
    context: BuiltContext
    llm: LlmResolved
    system: str = _SYSTEM
    history_trimmed: bool = False


def message_dict(message: ChatMessage, *, note_id: int | None = None) -> dict:
    created = message.created_at
    return {
        "id": message.id,
        "role": message.role,
        "content_text": message.content_text,
        "citations": message.citations_json or [],
        "source_ids": message.source_ids or [],
        "note_id": note_id,
        "created_at": created.isoformat() if created else None,
    }


async def list_messages(
    session: AsyncSession, *, owner_id: int, notebook_id: int
) -> list[dict]:
    # 分享访客可读对话历史；发消息仍走 prepare_chat 的主人校验
    await get_notebook_readable(session, viewer_id=owner_id, notebook_id=notebook_id)
    thread = await _find_thread(session, notebook_id)
    if thread is None:
        return []
    rows = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread.id)
            .order_by(ChatMessage.id)
        )
    ).scalars().all()
    from app.services.notes import note_ids_for_messages

    saved = await note_ids_for_messages(session, [row.id for row in rows])
    return [message_dict(row, note_id=saved.get(row.id)) for row in rows]


async def set_selected(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    selected: bool,
    video_id: int | None = None,
) -> None:
    from app.core.errors import NotFoundError

    await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    stmt = select(NotebookSource).where(NotebookSource.notebook_id == notebook_id)
    if video_id is not None:
        stmt = stmt.where(NotebookSource.video_id == video_id)
    rows = (await session.execute(stmt)).scalars().all()
    if video_id is not None and not rows:
        raise NotFoundError("来源不在这个笔记本里")
    for row in rows:
        row.selected_for_chat = selected
        session.add(row)
    await session.commit()


async def prepare_chat(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    message: str,
    source_ids: list[int] | None,
    note_ids: list[int] | None = None,
) -> PreparedChat:
    await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    ids = await _source_ids(session, notebook_id, source_ids)
    notes = await _notes(session, notebook_id, note_ids)
    if not ids and not notes:
        raise BadRequestError("请先勾选至少一个来源")
    context = await build_context(session, notebook_id=notebook_id, source_ids=ids)
    if not context.lines and not notes:
        raise BadRequestError("勾选的来源还没有可用字幕")

    notes_block = _notes_block(notes)
    question = message.strip()
    # 固定开销：字幕全文 + 笔记 + 问题；超限则直接报错，绝不截断勾选全文。
    body = f"字幕：\n{context.text}" if context.text else "字幕：（无）"
    if notes_block:
        body = f"{body}\n\n{notes_block}"
    prompt_core = f"{body}\n\n问题：{question}"
    system = _SYSTEM_WITH_NOTES if notes else _SYSTEM
    fixed_chars = len(system) + len(prompt_core)
    if context.chars > MAX_CONTEXT_CHARS or fixed_chars > MAX_CONTEXT_CHARS:
        raise BadRequestError(
            _SOURCES_TOO_LARGE.format(chars=max(context.chars, fixed_chars), limit=MAX_CONTEXT_CHARS)
        )

    llm = await get_active_llm(session)
    thread = await _get_thread(session, notebook_id=notebook_id, owner_id=owner_id)
    history_limit = await get_history_limit(session)
    history = await _history(session, thread.id, turn_limit=history_limit)
    history, history_trimmed = _trim_history_to_budget(
        history, fixed_chars=fixed_chars, max_chars=MAX_CONTEXT_CHARS
    )

    user = ChatMessage(
        thread_id=thread.id,
        role="user",
        content_text=question,
        citations_json=[],
        source_ids=context.source_ids,
    )
    session.add(user)
    thread.last_message_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(thread)
    await session.commit()

    return PreparedChat(
        thread_id=thread.id,
        prompt=prompt_core,
        history=history,
        context=context,
        llm=llm,
        system=system,
        history_trimmed=history_trimmed,
    )


async def stream_answer(prepared: PreparedChat) -> AsyncIterator[dict]:
    if prepared.history_trimmed:
        yield {
            "type": "warning",
            "code": "history_trimmed",
            "chars": prepared.context.chars,
        }
    provider = make_provider(
        provider_name=prepared.llm.provider,
        api_key=prepared.llm.api_key,
        base_url=prepared.llm.base_url,
        model_name=prepared.llm.model_name,
        params_json=prepared.llm.params_json,
    )
    parts: list[str] = []
    try:
        async for token in provider.stream_chat(
            prepared.prompt,
            system=prepared.system,
            history=prepared.history,
            max_tokens=2048,
        ):
            parts.append(token)
            yield {"type": "token", "t": token}
    except Exception as exc:  # noqa: BLE001 — 流里的失败要写成一条事件，不能把连接直接掐断
        logger.warning("chat stream failed thread_id=%s: %s", prepared.thread_id, exc)
        yield {"type": "error", "message": str(exc)[:500]}
    text = "".join(parts).strip()
    citations = parse_citations(text, prepared.context.lines) if text else []
    message_id = None
    if text:
        message_id = await _save_assistant(prepared, text, citations)
    yield {"type": "done", "message_id": message_id, "citations": citations}


def _notes_block(notes: list[Note]) -> str:
    return "\n\n".join(f"笔记：{item.title}\n{item.content_text}" for item in notes)


def _history_chars(history: list[dict[str, str]]) -> int:
    return sum(len(item.get("content") or "") + 8 for item in history)


def _trim_history_to_budget(
    history: list[dict[str, str]],
    *,
    fixed_chars: int,
    max_chars: int,
) -> tuple[list[dict[str, str]], bool]:
    """超预算时从最旧的一轮（user+assistant）开始丢，绝不碰固定开销（字幕/笔记/问题）。"""
    if fixed_chars + _history_chars(history) <= max_chars:
        return history, False
    trimmed = False
    out = list(history)
    while out and fixed_chars + _history_chars(out) > max_chars:
        # 丢掉最旧的一条；若下一条同属一轮助手/用户，也尽量成对丢掉
        out.pop(0)
        trimmed = True
        if out and out[0]["role"] == "assistant":
            out.pop(0)
    return out, trimmed


async def _notes(
    session: AsyncSession, notebook_id: int, note_ids: list[int] | None
) -> list[Note]:
    if not note_ids:
        return []
    rows = (
        await session.execute(
            select(Note).where(
                Note.id.in_(note_ids),
                Note.notebook_id == notebook_id,
                Note.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    ordered: list[Note] = []
    for note_id in note_ids:
        item = by_id.get(note_id)
        if item is None:
            raise NotFoundError("笔记不在这个笔记本里")
        ordered.append(item)
    return ordered


async def _source_ids(
    session: AsyncSession, notebook_id: int, source_ids: list[int] | None
) -> list[int]:
    stmt = select(NotebookSource.video_id).where(NotebookSource.notebook_id == notebook_id)
    if source_ids is None:
        stmt = stmt.where(NotebookSource.selected_for_chat.is_(True))
        rows = (await session.execute(stmt)).scalars().all()
        return list(rows)
    wanted = set(source_ids)
    rows = (await session.execute(stmt)).scalars().all()
    return [video_id for video_id in rows if video_id in wanted]


async def _find_thread(session: AsyncSession, notebook_id: int) -> ChatThread | None:
    return (
        await session.execute(select(ChatThread).where(ChatThread.notebook_id == notebook_id))
    ).scalar_one_or_none()


async def _get_thread(
    session: AsyncSession, *, notebook_id: int, owner_id: int
) -> ChatThread:
    thread = await _find_thread(session, notebook_id)
    if thread is not None:
        return thread
    thread = ChatThread(notebook_id=notebook_id, owner_id=owner_id)
    session.add(thread)
    await session.flush()
    return thread


async def _history(
    session: AsyncSession, thread_id: int, *, turn_limit: int
) -> list[dict[str, str]]:
    """取最近 turn_limit 轮（用户+助手成对）。多取一些消息再截成对。"""
    message_cap = max(2, turn_limit * 2)
    rows = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.id.desc())
            .limit(message_cap)
        )
    ).scalars().all()
    history: list[dict[str, str]] = []
    for row in reversed(rows):
        if row.role not in ("user", "assistant"):
            continue
        content = strip_citations(row.content_text) if row.role == "assistant" else row.content_text
        if content:
            history.append({"role": row.role, "content": content})
    # 按轮截断：从末尾数 turn_limit 个 user 起手的片段
    return _last_n_turns(history, turn_limit)


def _last_n_turns(history: list[dict[str, str]], turn_limit: int) -> list[dict[str, str]]:
    if turn_limit <= 0 or not history:
        return []
    turns: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    for item in history:
        if item["role"] == "user" and current and current[0]["role"] == "user":
            turns.append(current)
            current = [item]
        else:
            current.append(item)
    if current:
        turns.append(current)
    kept = turns[-turn_limit:]
    out: list[dict[str, str]] = []
    for turn in kept:
        out.extend(turn)
    return out


async def _save_assistant(
    prepared: PreparedChat, text: str, citations: list[dict]
) -> int:
    async with get_sessionmaker()() as session:
        message = ChatMessage(
            thread_id=prepared.thread_id,
            role="assistant",
            content_text=text,
            citations_json=citations,
            source_ids=prepared.context.source_ids,
        )
        session.add(message)
        thread = await session.get(ChatThread, prepared.thread_id)
        if thread is not None:
            thread.last_message_at = datetime.now(UTC).replace(tzinfo=None)
            session.add(thread)
        await session.commit()
        await session.refresh(message)
        return message.id
