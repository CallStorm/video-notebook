"""技能 zip 校验与 CRUD。"""
from __future__ import annotations

import io
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.studio import Agent, Skill

MAX_SKILL_ZIP_BYTES = 32 * 1024 * 1024
_SKILL_MD = "SKILL.md"


def _is_unsafe(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("\\"):
        return True
    path = PurePosixPath(normalized)
    return path.is_absolute() or ".." in path.parts


def _file_names(zf: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if _is_unsafe(name):
            raise BadRequestError("技能包包含非法路径")
        if info.is_dir() or name.endswith("/"):
            continue
        names.append(name)
    return names


def _root_prefix(names: list[str]) -> str:
    if any(name == _SKILL_MD for name in names):
        return ""
    tops = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    if len(tops) != 1:
        raise BadRequestError("技能包必须在根目录或单层文件夹内包含 SKILL.md")
    folder = next(iter(tops))
    nested = f"{folder}/{_SKILL_MD}"
    if nested not in names:
        raise BadRequestError("技能包必须在根目录或单层文件夹内包含 SKILL.md")
    return folder


def _inspect_zip(data: bytes) -> tuple[str, str]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise BadRequestError("不是有效的 zip") from exc
    with zf:
        names = _file_names(zf)
        prefix = _root_prefix(names)
        member = _SKILL_MD if prefix == "" else f"{prefix}/{_SKILL_MD}"
        return prefix, zf.read(member).decode("utf-8")


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse simple YAML-like frontmatter keys (name / description)."""
    if not text.startswith("---"):
        return {}
    rest = text[3:]
    end = rest.find("\n---")
    if end < 0:
        return {}
    result: dict[str, str] = {}
    current_key: str | None = None
    current_parts: list[str] = []

    def _flush() -> None:
        nonlocal current_key, current_parts
        if current_key is None:
            return
        value = " ".join(part.strip() for part in current_parts).strip().strip("'\"")
        if value:
            result[current_key] = value
        current_key = None
        current_parts = []

    for line in rest[:end].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ":" in stripped and not stripped.startswith("#"):
            key, raw = stripped.split(":", 1)
            key_l = key.strip().lower()
            if key_l in {"name", "description"}:
                _flush()
                current_key = key_l
                current_parts = [raw.strip()]
                continue
        if current_key is not None:
            current_parts.append(stripped)
    _flush()
    return result


def _frontmatter_name(text: str) -> str | None:
    return _parse_frontmatter(text).get("name") or None


def _frontmatter_description(text: str) -> str | None:
    return _parse_frontmatter(text).get("description") or None


def _extract(data: bytes, dest: Path, prefix: str) -> tuple[int, int]:
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()
    file_count = 0
    size_bytes = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if info.is_dir() or name.endswith("/"):
                continue
            if _is_unsafe(name):
                raise BadRequestError("技能包包含非法路径")
            rel = name
            if prefix:
                if name == prefix or name.startswith(f"{prefix}/"):
                    rel = name[len(prefix) :].lstrip("/")
                else:
                    continue
            if not rel:
                continue
            target = (dest / rel).resolve()
            if not target.is_relative_to(dest_resolved):
                raise BadRequestError("技能包包含非法路径")
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = zf.read(info)
            target.write_bytes(payload)
            file_count += 1
            size_bytes += len(payload)
    return file_count, size_bytes


async def _ensure_unique_name(
    session: AsyncSession, name: str, *, exclude_id: int | None = None
) -> None:
    stmt = select(Skill.id).where(Skill.name == name, Skill.deleted_at.is_(None))
    if exclude_id is not None:
        stmt = stmt.where(Skill.id != exclude_id)
    existing = await session.scalar(stmt.limit(1))
    if existing is not None:
        raise ConflictError("技能名称已存在")


async def _get_live_skill(session: AsyncSession, skill_id: int) -> Skill:
    skill = await session.get(Skill, skill_id)
    if skill is None or skill.deleted_at is not None:
        raise NotFoundError("技能不存在")
    return skill


async def create_skill_from_zip(session: AsyncSession, *, uploaded_by: int, data: bytes) -> Skill:
    if len(data) > MAX_SKILL_ZIP_BYTES:
        raise BadRequestError("技能包超过 32MB")
    prefix, skill_md = _inspect_zip(data)
    name = _frontmatter_name(skill_md)
    description = _frontmatter_description(skill_md)
    if name:
        await _ensure_unique_name(session, name)

    skill = Skill(
        name=name or "pending",
        description=description,
        version=None,
        storage_path="",
        file_count=0,
        size_bytes=0,
        uploaded_by=uploaded_by,
    )
    session.add(skill)
    await session.flush()
    if not name:
        skill.name = f"skill-{skill.id}"

    dest = get_settings().skills_root / str(skill.id)
    skill.storage_path = str(dest)
    try:
        file_count, size_bytes = _extract(data, dest, prefix)
        skill.file_count = file_count
        skill.size_bytes = size_bytes
    except Exception:
        await session.delete(skill)
        shutil.rmtree(dest, ignore_errors=True)
        await session.commit()
        raise
    await session.commit()
    await session.refresh(skill)
    return skill


async def list_skills(session: AsyncSession) -> list[Skill]:
    rows = (
        await session.execute(
            select(Skill).where(Skill.deleted_at.is_(None)).order_by(Skill.id.desc())
        )
    ).scalars().all()
    return list(rows)


async def get_skill(session: AsyncSession, skill_id: int) -> Skill:
    return await _get_live_skill(session, skill_id)


async def update_skill(
    session: AsyncSession,
    skill_id: int,
    *,
    name: str | None,
    description: str | None,
    version: str | None,
) -> Skill:
    skill = await _get_live_skill(session, skill_id)
    if name is not None:
        await _ensure_unique_name(session, name, exclude_id=skill.id)
        skill.name = name
    if description is not None:
        skill.description = description
    if version is not None:
        skill.version = version
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return skill


async def delete_skill(session: AsyncSession, skill_id: int) -> None:
    skill = await _get_live_skill(session, skill_id)
    referenced = await session.scalar(
        select(Agent.id).where(Agent.skill_id == skill_id, Agent.deleted_at.is_(None)).limit(1)
    )
    if referenced is not None:
        raise ConflictError("技能仍被智能体引用")
    skill.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(skill)
    await session.commit()


def skill_zip_bytes(skill: Skill) -> bytes:
    root = Path(skill.storage_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(root).as_posix())
    return buf.getvalue()


def read_skill_markdown(skill: Skill) -> str | None:
    """Return SKILL.md text from the extracted skill directory, if present."""
    root = Path(skill.storage_path)
    path = root / _SKILL_MD
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def skill_meta_for_prompt(skill: Skill) -> tuple[str, str | None]:
    """Name + description for drafting an agent system prompt.

    Prefer live SKILL.md frontmatter (authoritative), then DB fields.
    """
    md = read_skill_markdown(skill)
    fm = _parse_frontmatter(md) if md else {}
    name = (fm.get("name") or skill.name or "").strip() or skill.name
    description = (fm.get("description") or skill.description or "").strip() or None
    return name, description


def _infer_role(skill_name: str, agent_name: str | None) -> str:
    if agent_name and agent_name.strip():
        return agent_name.strip()
    lowered = skill_name.lower()
    if any(token in lowered for token in ("pptx", "ppt", "slide", "deck", "officecli")):
        return "PPT / 演示文稿专家"
    if any(token in lowered for token in ("mindmap", "mind-map", "导图")):
        return "思维导图专家"
    return f"{skill_name} 专家"



def _is_mindmap_skill(skill_name: str) -> bool:
    lowered = skill_name.lower()
    return any(token in lowered for token in ("mindmap", "mind-map", "导图"))


def build_system_prompt_draft(
    *,
    skill_name: str,
    skill_description: str | None = None,
    agent_name: str | None = None,
) -> str:
    """Draft a complementary system prompt for Studio + Claude Code.

    Runtime already:
    - copies the skill into `.claude/skills/<name>/` (Claude Code loads SKILL.md);
    - prepends format-specific output instructions;
    - appends a fixed prompt about inputs.json / outputs / MANIFEST.

    So this draft must NOT paste the whole skill body or repeat MANIFEST schema.
    It should set role, scope, skill usage, language, and failure behavior.
    """
    role = _infer_role(skill_name, agent_name)
    desc = (skill_description or "").strip()
    if len(desc) > 280:
        desc = desc[:277].rstrip() + "…"
    desc_block = (
        f"- 技能用途（摘要）：{desc}"
        if desc
        else "- 技能用途：以 `.claude/skills` 中该技能的 SKILL.md 为准。"
    )
    lines = [
        f"你是「{role}」，在视频笔记 Studio 任务中完成交付。",
        "",
        "## 技能",
        f"- 已绑定技能：`{skill_name}`。运行时会出现在 `.claude/skills/{skill_name}/`，请严格按该目录下 SKILL.md 的工作流、工具与质量门槛执行。",
        desc_block,
        "- 不要把技能全文复述进回复；需要细节时查阅技能文件与其 help，不要臆造命令或参数。",
        "",
        "## 输入与交付",
        "- 先阅读工作区 `inputs.json`（含 language、fields、sources：视频字幕与笔记文本），据此理解任务目标与可用材料。",
        "- 主产物与 `outputs/MANIFEST.json` 必须写在 `outputs/`；路径、mime、MANIFEST 字段以任务提示中的格式说明与固定约定为准，不要改成技能自有清单结构。",
        "- 不要修改 `inputs.json`。",
    ]
    if _is_mindmap_skill(skill_name):
        lines.extend(
            [
                "",
                "## 思维导图主题",
                "- `fields` 中 `key=topic` 是聚焦问题与导图形态：有主题时只展开直接相关分支，勿按来源做全章目录式覆盖。",
                "- 纯背景、征兆清单、宏观叙事等无关块默认省略；必要时最多一个短「必要前提」节点。",
                "- 仅当主题为空或用户明确要完整大纲时，才按全文做结构导图。产物格式细则以任务提示中的格式说明为准。",
            ]
        )
    lines.extend(
        [
            "",
            "## 原则",
            "- 输出语言：若 `inputs.json.language` 有指定则用该语言，否则默认中文。",
            "- 材料不足时：在已有 sources/fields 范围内尽力完成；缺关键信息时在说明中写清缺口，不要伪造数据、占位符或无依据的结论。",
            "- 失败时给出可操作的原因（缺依赖、命令失败、材料不足等），并尽量留下已产出的部分文件，而不是空目录。",
            "- 完成后确认 `outputs/` 中有可被平台验收的主文件与 MANIFEST。",
        ]
    )
    return "\n".join(lines)


async def draft_system_prompt(
    session: AsyncSession, skill_id: int, *, agent_name: str | None = None
) -> dict[str, str | None]:
    skill = await _get_live_skill(session, skill_id)
    name, description = skill_meta_for_prompt(skill)
    prompt = build_system_prompt_draft(
        skill_name=name,
        skill_description=description,
        agent_name=agent_name,
    )
    return {
        "skill_name": name,
        "skill_description": description,
        "system_prompt": prompt,
    }

