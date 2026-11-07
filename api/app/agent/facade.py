"""Agent 工具：名字与 MCP / REST 一致，内部只调用现有服务。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.urls import absolute_url
from app.core.errors import BadRequestError, ForbiddenError, NotFoundError
from app.models.agent_token import AgentToken
from app.models.notebook import Notebook, NotebookSource
from app.models.studio import StudioArtifact, StudioTask
from app.models.user import User
from app.schemas.search import SearchRequest
from app.services import notebooks as notebooks_svc
from app.services import sources as sources_svc
from app.services.agent_jobs import enqueue_job, present_job
from app.services.cover_url import expand_cover_url
from app.storage import get_storage

SIGNED_SECONDS = 3600
_HIDDEN_VIDEO_KEYS = {"storage_key", "content_hash"}


@dataclass
class AgentContext:
    user: User
    token: AgentToken
    scopes: set[str]
    origin: str


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    platforms: list[str] | None = None
    limit_per_platform: int = Field(default=8, ge=1, le=20)


class ListNotebooksArgs(BaseModel):
    search: str | None = Field(default=None, max_length=200)
    q: str | None = Field(default=None, max_length=200)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=50)


class NotebookIdArgs(BaseModel):
    notebook_id: int


class CreateNotebookArgs(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_name(self) -> CreateNotebookArgs:
        cleaned = (self.name or self.title or "").strip()
        if not cleaned:
            raise ValueError("需要 name")
        self.name = cleaned
        return self


class GenerateCoverArgs(BaseModel):
    notebook_id: int
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class AddUrlArgs(BaseModel):
    notebook_id: int
    url: str = Field(min_length=1, max_length=1024)


class VideoIdArgs(BaseModel):
    video_id: int


class GenerateDraftArgs(BaseModel):
    notebook_id: int
    strategy_id: int | None = None
    video_ids: list[int] | None = None
    note_ids: list[int] | None = None
    language: str = "中文"
    focus: str | None = Field(default=None, max_length=2000)
    extra_constraints: str | None = Field(default=None, max_length=5000)


class JobIdArgs(BaseModel):
    job_id: int


class ArtifactIdArgs(BaseModel):
    artifact_id: int


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    scopes: tuple[str, ...] | None
    model: type[BaseModel]
    handler: Any


def _validation_message(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(item) for item in err.get("loc", []))
        parts.append(f"{loc}: {err.get('msg')}")
    if not parts:
        return "参数不正确"
    return "参数不正确（" + "；".join(parts) + "）"


def public_video(data: dict) -> dict:
    out = {key: value for key, value in data.items() if key not in _HIDDEN_VIDEO_KEYS}
    out["video_id"] = out.get("id")
    return out


def _cover(origin: str, cover_url: str | None) -> str | None:
    return absolute_url(origin, expand_cover_url(cover_url))


def notebook_brief(data: dict, *, origin: str) -> dict:
    return {
        "notebook_id": data["id"],
        "name": data["title"],
        "description": data.get("description"),
        "cover_url": _cover(origin, data.get("cover_url")),
        "source_count": data.get("source_count", 0),
        "note_count": data.get("note_count", 0),
        "subtitle_ready": data.get("subtitle_ready", 0),
        "subtitle_total": data.get("subtitle_total", 0),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def _readiness(notebook_id: int, sources: list) -> dict:
    items = []
    for source in sources:
        video = source.video
        items.append(
            {
                "video_id": source.video_id,
                "title": video.title,
                "fetch_status": video.status,
                "subtitle_status": video.subtitle_status,
                "subtitle_error": video.subtitle_error,
                "overview_status": video.overview_status,
            }
        )
    total = len(items)
    subtitle_ready = sum(1 for item in items if item["subtitle_status"] == "ready")
    fetch_ready = sum(1 for item in items if item["fetch_status"] == "ready")
    return {
        "notebook_id": notebook_id,
        "source_count": total,
        "fetch_ready_count": fetch_ready,
        "subtitle_ready_count": subtitle_ready,
        "ready_for_draft": total > 0 and subtitle_ready == total,
        "sources": items,
    }


def _is_text_mime(mime: str | None) -> bool:
    value = (mime or "").lower()
    if value.startswith("text/"):
        return True
    return value in {"application/json", "application/xml"}


def _signed_download(origin: str, key: str) -> tuple[str, str]:
    from datetime import UTC, datetime, timedelta

    url = absolute_url(origin, get_storage().signed_url(key, expires_seconds=SIGNED_SECONDS))
    expires_at = (datetime.now(UTC) + timedelta(seconds=SIGNED_SECONDS)).isoformat()
    assert url is not None
    return url, expires_at


async def _search(session: AsyncSession, ctx: AgentContext, args: SearchArgs) -> dict:
    del session
    from app.schemas.search import Platform
    from app.search.service import run_search

    platforms: list[Platform] | None = None
    if args.platforms:
        allowed = {"youtube", "bilibili"}
        unknown = [item for item in args.platforms if item not in allowed]
        if unknown:
            raise BadRequestError("platforms 只支持 youtube 与 bilibili")
        platforms = [item for item in args.platforms if item in allowed]  # type: ignore[misc]
    body = SearchRequest(
        query=args.query,
        platforms=platforms,
        limit_per_platform=args.limit_per_platform,
    )
    result = await run_search(body)
    return result.model_dump(mode="json")


async def _list_notebooks(
    session: AsyncSession, ctx: AgentContext, args: ListNotebooksArgs
) -> dict:
    items, total = await notebooks_svc.list_notebooks(
        session,
        owner_id=ctx.user.id,
        search=(args.search or args.q),
        page=args.page,
        size=args.size,
    )
    reads = await notebooks_svc.to_read_many(session, items, viewer_id=ctx.user.id)
    return {
        "items": [notebook_brief(item, origin=ctx.origin) for item in reads],
        "total": total,
        "page": args.page,
        "size": args.size,
    }


async def _get_notebook(
    session: AsyncSession, ctx: AgentContext, args: NotebookIdArgs
) -> dict:
    notebook = await notebooks_svc.get_notebook(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id
    )
    data = await notebooks_svc.to_read(session, notebook, viewer_id=ctx.user.id)
    sources = await notebooks_svc.list_sources(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id
    )
    brief = notebook_brief(data, origin=ctx.origin)
    brief["sources"] = [
        {
            "notebook_id": source.notebook_id,
            "video_id": source.video_id,
            "sort": source.sort,
            "selected_for_chat": source.selected_for_chat,
            "video": public_video(source.video.model_dump()),
        }
        for source in sources
    ]
    brief["readiness"] = _readiness(args.notebook_id, sources)
    return brief


async def _load_owned_video(session: AsyncSession, ctx: AgentContext, video_id: int):
    return await sources_svc.get_video(session, owner_id=ctx.user.id, video_id=video_id)


async def _get_video(session: AsyncSession, ctx: AgentContext, args: VideoIdArgs) -> dict:
    video = await _load_owned_video(session, ctx, args.video_id)
    return public_video(sources_svc._video_to_dict(video))


async def _get_source(session: AsyncSession, ctx: AgentContext, args: VideoIdArgs) -> dict:
    video = await _load_owned_video(session, ctx, args.video_id)
    rows = (
        await session.execute(
            select(NotebookSource, Notebook)
            .join(Notebook, Notebook.id == NotebookSource.notebook_id)
            .where(
                NotebookSource.video_id == video.id,
                Notebook.owner_id == ctx.user.id,
                Notebook.deleted_at.is_(None),
            )
            .order_by(NotebookSource.sort, Notebook.id)
        )
    ).all()
    return {
        "video_id": int(video.id),
        "video": public_video(sources_svc._video_to_dict(video)),
        "notebooks": [
            {
                "notebook_id": int(notebook.id),
                "name": notebook.title,
                "sort": link.sort,
                "selected_for_chat": link.selected_for_chat,
            }
            for link, notebook in rows
        ],
    }


async def _download_video(
    session: AsyncSession, ctx: AgentContext, args: VideoIdArgs
) -> dict:
    video = await _load_owned_video(session, ctx, args.video_id)
    if not video.storage_key:
        raise NotFoundError("视频尚未完成存储")
    url, expires_at = _signed_download(ctx.origin, video.storage_key)
    return {
        "video_id": int(video.id),
        "filename": video.title,
        "mime": video.mime,
        "download_url": url,
        "expires_at": expires_at,
    }


async def _get_subtitle(session: AsyncSession, ctx: AgentContext, args: VideoIdArgs) -> dict:
    from app.subtitles.pipeline import read_subtitle_for_owner

    return await read_subtitle_for_owner(
        session, owner_id=ctx.user.id, video_id=args.video_id
    )


async def _get_draft(session: AsyncSession, ctx: AgentContext, args: NotebookIdArgs) -> dict:
    from app.services import knowledge_draft as draft_svc

    draft = await draft_svc.get_draft(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id
    )
    payload = draft.model_dump(mode="json") if draft is not None else None
    return {"notebook_id": args.notebook_id, "draft": payload}


async def _list_artifacts(
    session: AsyncSession, ctx: AgentContext, args: NotebookIdArgs
) -> dict:
    """产物列表：与网页「产物」同源（StudioTask），含知识底稿任务；正文仍用 get_draft。"""
    from app.services import knowledge_draft as draft_svc

    await notebooks_svc.get_notebook(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id
    )
    tasks = (
        await session.execute(
            select(StudioTask)
            .where(
                StudioTask.notebook_id == args.notebook_id,
                StudioTask.owner_id == ctx.user.id,
                StudioTask.deleted_at.is_(None),
            )
            .order_by(StudioTask.id.desc())
        )
    ).scalars().all()
    artifact_rows = (
        await session.execute(
            select(StudioArtifact, StudioTask)
            .join(StudioTask, StudioTask.id == StudioArtifact.task_id)
            .where(
                StudioTask.notebook_id == args.notebook_id,
                StudioTask.owner_id == ctx.user.id,
                StudioTask.deleted_at.is_(None),
            )
            .order_by(StudioArtifact.id.desc())
        )
    ).all()
    artifacts_by_task: dict[int, list] = {}
    for artifact, task in artifact_rows:
        artifacts_by_task.setdefault(int(task.id), []).append(artifact)

    items = []
    for task in tasks:
        tid = int(task.id)
        arts = artifacts_by_task.get(tid) or []
        if task.format_key == "knowledge_draft":
            items.append(
                {
                    "artifact_id": int(arts[0].id) if arts else None,
                    "task_id": tid,
                    "format_key": "knowledge_draft",
                    "title": task.title,
                    "status": task.status,
                    "role": "draft_task",
                    "filename": arts[0].filename if arts else None,
                    "mime": arts[0].mime if arts else None,
                    "error": task.error_message,
                    "has_download": bool(arts and arts[0].storage_key),
                    "has_text": False,
                    "read_content_with": "get_draft",
                    "note": "底稿任务（与网页产物页相同）。进行中/失败看 status；正文请 get_draft。",
                }
            )
            continue
        for artifact in arts:
            items.append(
                {
                    "artifact_id": int(artifact.id),
                    "task_id": tid,
                    "format_key": task.format_key,
                    "title": task.title,
                    "status": task.status,
                    "role": artifact.role,
                    "filename": artifact.filename,
                    "mime": artifact.mime,
                    "error": task.error_message,
                    "has_download": bool(artifact.storage_key),
                    "has_text": _is_text_mime(artifact.mime) and bool(artifact.text_content),
                }
            )
        if not arts:
            items.append(
                {
                    "artifact_id": None,
                    "task_id": tid,
                    "format_key": task.format_key,
                    "title": task.title,
                    "status": task.status,
                    "role": "task",
                    "filename": None,
                    "mime": None,
                    "error": task.error_message,
                    "has_download": False,
                    "has_text": False,
                }
            )

    draft = await draft_svc.get_draft(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id
    )
    if draft is None:
        draft_hint = {
            "available": False,
            "status": None,
            "theme": None,
            "read_with": "get_draft",
            "note": "尚无知识底稿正文。generate_draft 会在产物里创建底稿任务；成功后用 get_draft 读全文。",
        }
    else:
        theme = None
        content = getattr(draft, "content", None)
        if content is not None:
            theme = getattr(content, "theme", None)
        draft_hint = {
            "available": True,
            "status": draft.status,
            "theme": theme,
            "model_used": draft.model_used,
            "read_with": "get_draft",
            "note": "知识底稿正文请用 get_draft；产物列表里的 knowledge_draft 是任务卡片，不是正文。",
        }
    return {"notebook_id": args.notebook_id, "items": items, "draft": draft_hint}


async def _get_artifact(
    session: AsyncSession, ctx: AgentContext, args: ArtifactIdArgs
) -> dict:
    artifact = await session.get(StudioArtifact, args.artifact_id)
    if artifact is None:
        raise NotFoundError("产物不存在")
    task = await session.get(StudioTask, artifact.task_id)
    if task is None or task.deleted_at is not None or task.owner_id != ctx.user.id:
        raise NotFoundError("产物不存在")
    body: dict[str, Any] = {
        "artifact_id": int(artifact.id),
        "task_id": int(task.id),
        "notebook_id": int(task.notebook_id),
        "format_key": task.format_key,
        "filename": artifact.filename,
        "mime": artifact.mime,
        "download_url": None,
        "expires_at": None,
        "text": None,
    }
    if artifact.storage_key:
        url, expires_at = _signed_download(ctx.origin, artifact.storage_key)
        body["download_url"] = url
        body["expires_at"] = expires_at
    if _is_text_mime(artifact.mime) and artifact.text_content:
        body["text"] = artifact.text_content[:80_000]
    return body


async def _create_notebook(
    session: AsyncSession, ctx: AgentContext, args: CreateNotebookArgs
) -> dict:
    created = await notebooks_svc.create_notebook(
        session,
        owner_id=ctx.user.id,
        title=args.name or "",
        description=args.description,
    )
    job = await enqueue_job(
        session,
        owner_id=ctx.user.id,
        kind="generate_cover",
        notebook_id=int(created["id"]),
        payload={
            "notebook_id": int(created["id"]),
            "title": created["title"],
            "description": created.get("description"),
        },
    )
    return {
        "notebook_id": int(created["id"]),
        "name": created["title"],
        "description": created.get("description"),
        "cover_url": _cover(ctx.origin, created.get("cover_url")),
        "cover_job_id": int(job.id),
    }


async def _generate_cover(
    session: AsyncSession, ctx: AgentContext, args: GenerateCoverArgs
) -> dict:
    notebook = await notebooks_svc.get_notebook(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id
    )
    job = await enqueue_job(
        session,
        owner_id=ctx.user.id,
        kind="generate_cover",
        notebook_id=int(notebook.id),
        payload={
            "notebook_id": int(notebook.id),
            "title": args.title or notebook.title,
            "description": args.description if args.description is not None else notebook.description,
        },
    )
    return {"job_id": int(job.id), "status": job.status, "kind": job.kind}


async def _add_url(session: AsyncSession, ctx: AgentContext, args: AddUrlArgs) -> dict:
    created = await sources_svc.fetch_url(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id, url=args.url
    )
    return {
        "notebook_id": args.notebook_id,
        "video": public_video(created),
    }


async def _get_readiness(
    session: AsyncSession, ctx: AgentContext, args: NotebookIdArgs
) -> dict:
    sources = await notebooks_svc.list_sources(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id
    )
    return _readiness(args.notebook_id, sources)


async def _generate_draft(
    session: AsyncSession, ctx: AgentContext, args: GenerateDraftArgs
) -> dict:
    """与网页「生成底稿」相同：创建 StudioTask(format_key=knowledge_draft)，产物页可见。"""
    from app.schemas.studio import TaskCreate
    from app.services import studio_tasks as studio_tasks_svc
    from app.services.agent_tokens import iso

    await notebooks_svc.get_notebook(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id
    )

    video_ids = args.video_ids
    note_ids = args.note_ids
    if video_ids is None and note_ids is None:
        sources = await notebooks_svc.list_sources(
            session, owner_id=ctx.user.id, notebook_id=args.notebook_id
        )
        ready = [item.video_id for item in sources if item.video.subtitle_status == "ready"]
        video_ids = ready or [item.video_id for item in sources]
        note_ids = []
    else:
        video_ids = list(video_ids or [])
        note_ids = list(note_ids or [])
    if not video_ids and not note_ids:
        raise BadRequestError("请先选择来源")

    caps = await studio_tasks_svc.list_enabled_capabilities(
        session, owner_id=ctx.user.id, notebook_id=args.notebook_id
    )
    cap = next((c for c in caps if c.format_key == "knowledge_draft"), None)
    if cap is None:
        raise BadRequestError("底稿生成暂不可用，请稍后重试或联系管理员")

    focus_parts: list[str] = []
    if args.focus and str(args.focus).strip():
        focus_parts.append(str(args.focus).strip())
    if args.extra_constraints and str(args.extra_constraints).strip():
        focus_parts.append(str(args.extra_constraints).strip())
    # strategy_id / language：网页底稿 Studio 表单无这两项；有需要时并入 focus 备注
    if args.strategy_id is not None:
        focus_parts.append(f"[strategy_id={int(args.strategy_id)}]")
    if args.language and args.language != "中文":
        focus_parts.append(f"[language={args.language}]")
    fields: dict[str, str] = {}
    if focus_parts:
        fields["focus"] = "\n".join(focus_parts)

    task = await studio_tasks_svc.create_task(
        session,
        owner_id=ctx.user.id,
        notebook_id=args.notebook_id,
        body=TaskCreate(
            capability_id=int(cap.id),
            video_ids=[int(v) for v in video_ids],
            note_ids=[int(n) for n in note_ids],
            fields=fields,
        ),
    )
    return {
        "job_id": int(task.id),
        "task_id": int(task.id),
        "status": task.status,
        "kind": "generate_draft",
        "format_key": "knowledge_draft",
        "created_at": iso(task.created_at),
        "note": "已创建与网页相同的底稿任务，产物页可见；用 get_job 轮询，成功后 get_draft 读正文。",
    }


def _present_studio_draft_job(task: StudioTask) -> dict:
    from app.services.agent_tokens import iso

    status = task.status
    next_step = None
    if status == "succeeded":
        next_step = "调用 get_draft(notebook_id) 读取知识底稿全文；产物列表里也能看到该底稿任务。"
    elif status == "failed":
        next_step = "可再调 generate_draft；成功后用 get_draft 读正文。"
    elif status in {"queued", "running"}:
        next_step = "继续 get_job 轮询；网页「产物」页同步显示进度。"
    return {
        "job_id": int(task.id),
        "task_id": int(task.id),
        "kind": "generate_draft",
        "status": status,
        "notebook_id": int(task.notebook_id),
        "format_key": task.format_key,
        "result": {"notebook_id": int(task.notebook_id)} if status == "succeeded" else None,
        "error": task.error_message,
        "next_step": next_step,
        "created_at": iso(task.created_at),
        "finished_at": iso(task.finished_at),
    }


async def _get_job(session: AsyncSession, ctx: AgentContext, args: JobIdArgs) -> dict:
    from app.models.agent_token import AgentJob

    job = await session.get(AgentJob, args.job_id)
    task = await session.get(StudioTask, args.job_id)
    # AgentJob 与 StudioTask 分表自增，id 可能撞号。
    # 旧版 generate_draft 写 AgentJob；新版写 StudioTask(knowledge_draft)。
    if (
        job is not None
        and job.owner_id == ctx.user.id
        and job.kind == "generate_draft"
    ):
        return present_job(job, origin=ctx.origin)
    if (
        task is not None
        and task.deleted_at is None
        and task.owner_id == ctx.user.id
        and task.format_key == "knowledge_draft"
    ):
        return _present_studio_draft_job(task)
    if job is not None and job.owner_id == ctx.user.id:
        return present_job(job, origin=ctx.origin)

    raise NotFoundError("任务不存在")


TOOLS: list[Tool] = [
    Tool("search", "在 YouTube / Bilibili 搜索视频，返回可粘贴的链接。", ("read",), SearchArgs, _search),
    Tool("list_notebooks", "列出当前用户的笔记本。", ("read",), ListNotebooksArgs, _list_notebooks),
    Tool("get_notebook", "读取笔记本详情、来源和就绪情况。", ("read",), NotebookIdArgs, _get_notebook),
    Tool("get_source", "读取一条来源（视频）以及它挂在哪些笔记本上。", ("read",), VideoIdArgs, _get_source),
    Tool("get_video", "读取视频元数据，不含文件内容。", ("read",), VideoIdArgs, _get_video),
    Tool(
        "download_video",
        "返回视频的签名 download_url 与 expires_at，不返回二进制。",
        ("read",),
        VideoIdArgs,
        _download_video,
    ),
    Tool("get_subtitle", "读取视频字幕文本。", ("read",), VideoIdArgs, _get_subtitle),
    Tool(
        "get_draft",
        "读取笔记本的知识底稿正文（网页「知识」页）。产物页的 knowledge_draft 是任务卡片；正文请用本工具。",
        ("read",),
        NotebookIdArgs,
        _get_draft,
    ),
    Tool(
        "list_artifacts",
        "列出网页「产物」页任务（含知识底稿任务 knowledge_draft，以及思维导图/幻灯片等）。底稿正文仍用 get_draft；draft 字段提示是否已有正文。",
        ("read",),
        NotebookIdArgs,
        _list_artifacts,
    ),
    Tool(
        "get_artifact",
        "读取产物：文本直接返回，二进制只给签名 download_url。",
        ("read",),
        ArtifactIdArgs,
        _get_artifact,
    ),
    Tool(
        "create_notebook",
        "创建笔记本，同步返回 notebook_id、name、description、cover_url（封面未完成时为 null），并排队生成封面。",
        ("write_notebook",),
        CreateNotebookArgs,
        _create_notebook,
    ),
    Tool(
        "generate_cover",
        "按笔记本名称和描述排队生成封面，返回 job_id。",
        ("write_generate",),
        GenerateCoverArgs,
        _generate_cover,
    ),
    Tool("add_url", "把视频 URL 加进笔记本并开始抓取。", ("write_notebook",), AddUrlArgs, _add_url),
    Tool(
        "get_readiness",
        "查看抓取与字幕是否就绪。ready_for_draft 为真后再 generate_draft。",
        ("read", "write_notebook"),
        NotebookIdArgs,
        _get_readiness,
    ),
    Tool(
        "generate_draft",
        "与网页「生成底稿」相同：创建 Studio 底稿任务（产物页可见），立刻返回 job_id(=task_id)。用 get_job 轮询；成功后 get_draft 读正文。来源省略时用本内已就绪字幕。",
        ("write_generate",),
        GenerateDraftArgs,
        _generate_draft,
    ),
    Tool(
        "get_job",
        "查询 generate_cover（AgentJob）或 generate_draft（Studio 底稿任务）状态。底稿成功后请再调 get_draft 读全文。",
        None,
        JobIdArgs,
        _get_job,
    ),
]

_BY_NAME = {tool.name: tool for tool in TOOLS}


def tool_allowed(tool: Tool, scopes: set[str]) -> bool:
    if not tool.scopes:
        return True
    return any(scope in scopes for scope in tool.scopes)


def tool_catalog(scopes: set[str] | None = None) -> list[dict]:
    items = []
    for tool in TOOLS:
        items.append(
            {
                "name": tool.name,
                "description": tool.description,
                "scopes": list(tool.scopes or []),
                "allowed": True if scopes is None else tool_allowed(tool, scopes),
                "input_schema": tool.model.model_json_schema(),
            }
        )
    return items


async def dispatch(
    session: AsyncSession, ctx: AgentContext, name: str, arguments: dict | None
) -> dict:
    tool = _BY_NAME.get(name)
    if tool is None:
        raise NotFoundError(f"未知工具 {name}")
    if not tool_allowed(tool, ctx.scopes):
        needed = " 或 ".join(tool.scopes or ())
        raise ForbiddenError(f"Token 缺少权限：{needed}")
    try:
        args = tool.model.model_validate(arguments or {})
    except ValidationError as exc:
        raise BadRequestError(_validation_message(exc)) from exc
    return await tool.handler(session, ctx, args)
