"""Run one studio task in a temporary directory and store its artifact."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update

from app.db.session import get_sessionmaker
from app.models.notebook import Note, Video
from app.models.studio import (
    Agent,
    ClaudeCodeConfig,
    Skill,
    StudioArtifact,
    StudioCapability,
    StudioTask,
)
from app.storage import get_storage
from app.studio.formats import FormatMismatch, NoOutput, accept_outputs, get_format
from app.subtitles.store import load_subtitle

_FIXED_PROMPT = (
    "阅读 inputs.json。若存在 .claude/skills 则使用其中的技能。"
    "不要修改 inputs.json。主文件和 MANIFEST.json 写在 outputs/。"
    "MANIFEST.json 只用上面给出的 status、title、artifacts 结构，不要改成技能自己的清单字段。"
)
_POLL_SECONDS = 2.0
_KILL_GRACE_SECONDS = 5.0
_STDERR_TAIL = 2000


@dataclass
class _Prepared:
    model_name: str
    api_key: str
    base_url: str | None
    system_prompt: str
    format_key: str
    language: object
    fields: list
    sources: list[dict]
    capability_name: str
    skill_src: Path | None
    skill_dirname: str | None
    skill_missing: bool
    agent_timeout: int


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _safe_skill_name(name: str) -> str:
    cleaned = name.replace("\\", "_").replace("/", "_").replace("\0", "").strip()
    if cleaned in {"", ".", ".."}:
        return "skill"
    return cleaned


def _choose_title(manifest_title: str | None, fields: list, capability_name: str) -> str:
    candidates: list[object] = [manifest_title]
    if fields and isinstance(fields[0], dict):
        candidates.append(fields[0].get("value"))
    candidates.append(capability_name)
    for item in candidates:
        if isinstance(item, str) and item.strip():
            return item.strip()[:255]
    return (capability_name or "studio")[:255]


def _prompt(format_key: str, system_prompt: str) -> str:
    return "\n\n".join([get_format(format_key).instructions, system_prompt, _FIXED_PROMPT])


def _pdf_convert_timeout() -> float:
    """Match the sweep grace so conversion cannot stay running past that window."""
    from app.studio.worker import _SWEEP_GRACE_SECONDS

    return float(_SWEEP_GRACE_SECONDS)


def _kill_popen_group(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None and proc.pid is not None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        proc.communicate()


def _soffice_convert(
    pptx_path: Path,
    outputs_dir: Path,
    *,
    timeout_seconds: float,
) -> None:
    proc = subprocess.Popen(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(outputs_dir),
            str(pptx_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        _stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _kill_popen_group(proc)
        raise
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode or 1, proc.args, stderr=stderr)


def _kill_group(proc: asyncio.subprocess.Process, sig: int) -> None:
    if proc.pid is None or proc.returncode is not None:
        return
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        return


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    _kill_group(proc, signal.SIGTERM)
    try:
        await asyncio.wait_for(proc.wait(), _KILL_GRACE_SECONDS)
    except TimeoutError:
        _kill_group(proc, signal.SIGKILL)
        await proc.wait()


async def _sources(session, params: dict) -> list[dict]:
    sources: list[dict] = []
    for video_id in params.get("video_ids") or []:
        video = await session.get(Video, video_id)
        if video is None:
            sources.append({"id": video_id, "kind": "video", "title": "", "text": ""})
            continue
        _subtitle, lines = await load_subtitle(session, video)
        sources.append(
            {
                "id": video.id,
                "kind": "video",
                "title": video.title or "",
                "text": "\n".join(line.text for line in lines),
            }
        )
    for note_id in params.get("note_ids") or []:
        note = await session.get(Note, note_id)
        if note is None:
            sources.append({"id": note_id, "kind": "note", "title": "", "text": ""})
            continue
        sources.append(
            {
                "id": note.id,
                "kind": "note",
                "title": note.title,
                "text": note.content_text,
            }
        )
    return sources


async def _prepare(session, task: StudioTask) -> _Prepared:
    agent = await session.get(Agent, task.agent_id)
    if agent is None:
        raise RuntimeError("agent missing")
    cap = await session.get(StudioCapability, task.capability_id)
    params = task.params_json or {}
    skill_src: Path | None = None
    skill_dirname: str | None = None
    skill_missing = False
    if agent.skill_id is not None:
        skill = await session.get(Skill, agent.skill_id)
        path = Path(skill.storage_path) if skill is not None else None
        if skill is None or path is None or not path.is_dir():
            skill_missing = True
        else:
            skill_src = path
            skill_dirname = _safe_skill_name(skill.name)
    config = await session.get(ClaudeCodeConfig, 1)
    return _Prepared(
        model_name=(config.model_name if config is not None else "").strip(),
        api_key=config.get_api_key().strip() if config is not None else "",
        base_url=(config.base_url or "").strip() or None if config is not None else None,
        system_prompt=agent.system_prompt or "",
        format_key=task.format_key,
        language=params.get("language"),
        fields=list(params.get("fields") or []),
        sources=await _sources(session, params),
        capability_name=cap.name if cap is not None else task.title,
        skill_src=skill_src,
        skill_dirname=skill_dirname,
        skill_missing=skill_missing,
        agent_timeout=agent.timeout_seconds,
    )


def _write_workspace(work: Path, prepared: _Prepared) -> str:
    (work / "outputs").mkdir(parents=True, exist_ok=True)
    (work / "inputs.json").write_text(
        json.dumps(
            {
                "language": prepared.language,
                "fields": prepared.fields,
                "sources": prepared.sources,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    prompt = _prompt(prepared.format_key, prepared.system_prompt)
    (work / "prompt.txt").write_text(prompt, encoding="utf-8")
    if prepared.skill_src is not None and prepared.skill_dirname is not None:
        dest = work / ".claude" / "skills" / prepared.skill_dirname
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(prepared.skill_src, dest)
    return prompt


async def _stopped(factory, task_id: int) -> bool:
    async with factory() as session:
        task = await session.get(StudioTask, task_id)
        if task is None:
            return True
        return task.status == "canceled" or task.deleted_at is not None


def _queued_filter(task_id: int):
    return (
        StudioTask.id == task_id,
        StudioTask.status == "queued",
        StudioTask.deleted_at.is_(None),
    )


async def _fail_if_queued(session, task_id: int, message: str) -> None:
    await session.execute(
        update(StudioTask)
        .where(*_queued_filter(task_id))
        .values(
            status="failed",
            error_code="process_failed",
            error_message=(message or "")[-_STDERR_TAIL:],
            finished_at=_now(),
        )
    )
    await session.commit()


async def _claim_running(session, task_id: int) -> bool:
    result = await session.execute(
        update(StudioTask)
        .where(*_queued_filter(task_id))
        .values(status="running", started_at=_now())
    )
    await session.commit()
    return result.rowcount == 1


async def _mark_failed(factory, task_id: int, code: str, message: str, work: Path | None) -> None:
    async with factory() as session:
        task = await session.get(StudioTask, task_id)
        if (
            task is None
            or task.deleted_at is not None
            or task.status not in {"queued", "running"}
        ):
            return
        task.status = "failed"
        task.error_code = code
        task.error_message = (message or "")[-_STDERR_TAIL:]
        task.finished_at = _now()
        if work is not None:
            task.result_json = {"work_dir": str(work)}
        await session.commit()


def _claude_env(api_key: str, base_url: str | None) -> dict[str, str]:
    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"] = api_key
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    else:
        env.pop("ANTHROPIC_BASE_URL", None)
    return env


async def _run_claude(
    *,
    claude_bin: str,
    model_name: str,
    api_key: str,
    base_url: str | None,
    work: Path,
    prompt: str,
    task_id: int,
    timeout_seconds: int,
    factory,
) -> tuple[str, int, str]:
    stdout_path = work / "stdout.log"
    stderr_path = work / "stderr.log"
    stdout_f = stdout_path.open("wb")
    stderr_f = stderr_path.open("wb")
    outcome = "ok"
    code = 1
    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                claude_bin,
                "-p",
                "--permission-mode",
                "bypassPermissions",
                "--model",
                model_name,
                "--add-dir",
                str(work),
                stdin=asyncio.subprocess.PIPE,
                stdout=stdout_f,
                stderr=stderr_f,
                cwd=work,
                env=_claude_env(api_key, base_url),
                start_new_session=True,
            )
        except OSError as exc:
            stderr_f.write(str(exc).encode("utf-8"))
            return "ok", 1, str(exc)
        assert proc.stdin is not None
        proc.stdin.write(prompt.encode("utf-8"))
        try:
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        proc.stdin.close()
        try:
            await proc.stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass
        deadline = time.monotonic() + timeout_seconds
        while proc.returncode is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                await _terminate(proc)
                outcome = "timeout"
                break
            try:
                await asyncio.wait_for(proc.wait(), min(_POLL_SECONDS, remaining))
            except TimeoutError:
                if await _stopped(factory, task_id):
                    await _terminate(proc)
                    outcome = "canceled"
                    break
        code = proc.returncode if proc.returncode is not None else 1
    finally:
        stdout_f.close()
        stderr_f.close()
    stderr_text = ""
    if stderr_path.is_file():
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    return outcome, code, stderr_text


def _store_main(path: Path, mime: str) -> tuple[str, bytes]:
    data = path.read_bytes()
    key = get_storage().put(data=data, content_type=mime, suffix=path.suffix)
    return key, data


async def _delete_unshared(session, task_id: int, keys: list[str]) -> None:
    """Drop this attempt's blobs unless another task's artifact still has the key."""
    storage = get_storage()
    for key in keys:
        other = await session.scalar(
            select(StudioArtifact.id)
            .where(
                StudioArtifact.storage_key == key,
                StudioArtifact.task_id != task_id,
            )
            .limit(1)
        )
        if other is None:
            storage.delete(key)


async def _delete_unshared_keys(factory, task_id: int, keys: list[str]) -> None:
    async with factory() as session:
        await _delete_unshared(session, task_id, keys)


def _convert_pdf(
    pptx_path: Path,
    outputs_dir: Path,
    pdf_convert: Callable[[Path, Path], None],
) -> tuple[str, str] | str:
    """Return (storage_key, filename) or a short pdf_error string."""
    try:
        pdf_convert(pptx_path, outputs_dir)
        pdf_path = outputs_dir / f"{pptx_path.stem}.pdf"
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise RuntimeError("pdf missing")
        pdf_bytes = pdf_path.read_bytes()
        key = get_storage().put(
            data=pdf_bytes, content_type="application/pdf", suffix=".pdf"
        )
        return key, pdf_path.name
    except Exception as exc:  # noqa: BLE001 — conversion must not fail the task
        text = str(exc).strip() or exc.__class__.__name__
        return text[:500]


async def _store_success(
    factory,
    task_id: int,
    *,
    prepared: _Prepared,
    accepted_path: Path,
    accepted_mime: str,
    accepted_title: str | None,
    pdf_convert: Callable[[Path, Path], None] | None,
    pdf_timeout_seconds: float | None,
    work: Path,
    stored_keys: list[str],
) -> None:
    main_key, data = _store_main(accepted_path, accepted_mime)
    stored_keys.append(main_key)
    text_content: str | None = None
    if prepared.format_key == "mind_map":
        try:
            text_content = data.decode("utf-8")
        except UnicodeDecodeError:
            await _delete_unshared_keys(factory, task_id, [main_key])
            stored_keys.remove(main_key)
            await _mark_failed(factory, task_id, "format_mismatch", "format mismatch", work)
            return
    side: tuple[str, str] | None = None
    pdf_error: str | None = None
    if prepared.format_key == "slides":
        if pdf_convert is None:
            timeout = (
                _pdf_convert_timeout()
                if pdf_timeout_seconds is None
                else pdf_timeout_seconds
            )

            def convert(pptx_path: Path, outputs_dir: Path) -> None:
                _soffice_convert(pptx_path, outputs_dir, timeout_seconds=timeout)

        else:
            convert = pdf_convert
        converted = _convert_pdf(accepted_path, work / "outputs", convert)
        if isinstance(converted, str):
            pdf_error = converted
        else:
            side = converted
            stored_keys.append(side[0])
    keys = [main_key]
    if side is not None:
        keys.append(side[0])
    async with factory() as session:
        result = await session.execute(
            update(StudioTask)
            .where(
                StudioTask.id == task_id,
                StudioTask.status == "running",
                StudioTask.deleted_at.is_(None),
            )
            .values(
                status="succeeded",
                error_code=None,
                error_message=None,
                finished_at=_now(),
                title=_choose_title(
                    accepted_title, prepared.fields, prepared.capability_name
                ),
                result_json={"pdf_error": pdf_error} if pdf_error else None,
            )
        )
        if result.rowcount != 1:
            await session.rollback()
            await _delete_unshared(session, task_id, keys)
            shutil.rmtree(work, ignore_errors=True)
            return
        session.add(
            StudioArtifact(
                task_id=task_id,
                role="main",
                filename=accepted_path.name,
                mime=accepted_mime,
                storage_key=main_key,
                text_content=text_content,
            )
        )
        if side is not None:
            session.add(
                StudioArtifact(
                    task_id=task_id,
                    role="side",
                    filename=side[1],
                    mime="application/pdf",
                    storage_key=side[0],
                    text_content=None,
                )
            )
        await session.commit()
    shutil.rmtree(work)


async def _abandon_attempt(
    factory,
    task_id: int,
    message: str,
    work: Path | None,
    stored_keys: list[str],
) -> None:
    """Record process_failed unless cancel or success already won. Drop leaked objects."""
    async with factory() as session:
        task = await session.get(StudioTask, task_id)
        if task is None:
            status, deleted = None, False
        else:
            status, deleted = task.status, task.deleted_at is not None
        if status != "succeeded":
            await _delete_unshared(session, task_id, stored_keys)
    if status == "running" and not deleted:
        await _mark_failed(factory, task_id, "process_failed", message, work)
        return
    if work is not None and (status == "canceled" or deleted):
        shutil.rmtree(work, ignore_errors=True)


async def execute_studio_task(
    task_id: int,
    *,
    claude_bin: str = "claude",
    pdf_convert: Callable[[Path, Path], None] | None = None,
    timeout_seconds: int | None = None,
    pdf_timeout_seconds: float | None = None,
) -> None:
    factory = get_sessionmaker()
    async with factory() as session:
        task = await session.get(StudioTask, task_id)
        if task is None or task.status != "queued":
            return
        try:
            prepared = await _prepare(session, task)
        except RuntimeError as exc:
            await _fail_if_queued(session, task_id, str(exc))
            return
        limit = prepared.agent_timeout if timeout_seconds is None else timeout_seconds
        if not await _claim_running(session, task_id):
            return

    stored_keys: list[str] = []
    work: Path | None = None
    try:
        work = Path(tempfile.mkdtemp(prefix=f"studio_{task_id}_"))
        prompt = _write_workspace(work, prepared)
        if prepared.skill_missing:
            await _mark_failed(factory, task_id, "process_failed", "技能目录不存在", work)
            return
        if not prepared.api_key or not prepared.model_name:
            await _mark_failed(factory, task_id, "process_failed", "还没有配置 Claude Code", work)
            return

        outcome, code, stderr = await _run_claude(
            claude_bin=claude_bin,
            model_name=prepared.model_name,
            api_key=prepared.api_key,
            base_url=prepared.base_url,
            work=work,
            prompt=prompt,
            task_id=task_id,
            timeout_seconds=limit,
            factory=factory,
        )
        if outcome == "canceled" or await _stopped(factory, task_id):
            shutil.rmtree(work, ignore_errors=True)
            return
        if outcome == "timeout":
            await _mark_failed(factory, task_id, "timeout", stderr or "timeout", work)
            return
        if code != 0:
            await _mark_failed(
                factory, task_id, "process_failed", stderr or "process failed", work
            )
            return

        outputs = work / "outputs"
        try:
            accepted = accept_outputs(get_format(prepared.format_key), outputs)
        except FormatMismatch:
            await _mark_failed(factory, task_id, "format_mismatch", "format mismatch", work)
            return
        except NoOutput:
            await _mark_failed(factory, task_id, "no_output", "no output", work)
            return

        await _store_success(
            factory,
            task_id,
            prepared=prepared,
            accepted_path=accepted.path,
            accepted_mime=accepted.mime,
            accepted_title=accepted.title,
            pdf_convert=pdf_convert,
            pdf_timeout_seconds=pdf_timeout_seconds,
            work=work,
            stored_keys=stored_keys,
        )
    except Exception as exc:  # noqa: BLE001
        await _abandon_attempt(factory, task_id, str(exc), work, stored_keys)
