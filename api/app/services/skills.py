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


def _frontmatter_name(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    rest = text[3:]
    end = rest.find("\n---")
    if end < 0:
        return None
    for line in rest[:end].splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("name:"):
            value = stripped.split(":", 1)[1].strip().strip("'\"")
            return value or None
    return None


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
    if name:
        await _ensure_unique_name(session, name)

    skill = Skill(
        name=name or "pending",
        description=None,
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
