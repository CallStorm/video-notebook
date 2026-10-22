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


def _field_map(fields: list) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in fields:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        value = item.get("value")
        if isinstance(key, str) and key and isinstance(value, str):
            out[key] = value
    return out


def _topic_hard_constraints(format_key: str, fields: list) -> str | None:
    """Inject a prominent prompt body block so topic beats skill「全书大纲」 flow."""
    if format_key != "mind_map":
        return None
    fmap = _field_map(fields)
    topic = (fmap.get("topic") or "").strip()
    if not topic:
        return None
    focus_mode = (fmap.get("focus_mode") or "action").strip() or "action"
    extra = (fmap.get("extra_constraints") or "").strip()
    lines: list[str]
    if focus_mode == "outline":
        lines = [
            "## 本次主题硬约束（优先于技能里的全书大纲流程）",
            "- 模式：完整大纲（outline）",
            f"- 用户主题参考：{topic}（可用作根节点或副标题；允许按来源全文做结构导图）",
            "- Studio 只交 outputs/mindmap.md 与约定 MANIFEST；不要按技能去走 HTML/全书目录交付",
        ]
    else:
        lines = [
            "## 本次主题硬约束（优先于技能里的全书大纲流程）",
            f"- 根节点必须是：{topic}",
            "- 模式：聚焦应对/行动（action）",
            "- 禁止把根标题扩写成视频全标题或章节总名；仅允许轻微润色措辞",
            "- 一级分支只保留直接回答该主题的行动/原则/步骤/注意点",
            "- 不要用来源的完整大纲（背景、征兆、机制等）作为并列一级大章，除非与应对直接相关",
            "- 若缺一点背景就无法理解主题，最多一个短「必要前提」节点",
            "- Studio 只交 outputs/mindmap.md 与约定 MANIFEST；不要按技能去走 HTML/全书目录交付",
        ]
    if extra:
        lines.append(f"- 用户额外约束：{extra}")
    return "\n".join(lines)


def _prompt(format_key: str, system_prompt: str, fields: list | None = None) -> str:
    parts = [get_format(format_key).instructions]
    hard = _topic_hard_constraints(format_key, fields or [])
    if hard:
        parts.append(hard)
    if isinstance(system_prompt, str) and system_prompt.strip():
        parts.append(system_prompt)
    parts.append(_FIXED_PROMPT)
    return "\n\n".join(parts)


def _pdf_convert_timeout() -> float:
    """Match the sweep grace so conversion cannot stay running past that window."""
    from app.studio.worker import _SWEEP_GRACE_SECONDS

    return float(_SWEEP_GRACE_SECONDS)


def _kill_popen_group(proc: subprocess.Popen[bytes]) -> None:
    """Kill Claude and any child builders (Windows needs /T tree kill)."""
    if proc.poll() is None and proc.pid is not None:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
        elif hasattr(os, "killpg"):
            try:
                os.killpg(proc.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
            except (ProcessLookupError, OSError):
                pass
        else:
            try:
                proc.kill()
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
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired, ProcessLookupError):
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass
        return
    if hasattr(os, "killpg"):
        try:
            os.killpg(proc.pid, sig)
            return
        except (ProcessLookupError, OSError):
            return
    try:
        if sig == getattr(signal, "SIGKILL", object()):
            proc.kill()
        else:
            proc.terminate()
    except (ProcessLookupError, OSError):
        return


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    _kill_group(proc, signal.SIGTERM)
    try:
        await asyncio.wait_for(proc.wait(), _KILL_GRACE_SECONDS)
    except TimeoutError:
        _kill_group(proc, getattr(signal, 'SIGKILL', signal.SIGTERM))
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
    prompt = _prompt(prepared.format_key, prepared.system_prompt, prepared.fields)
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
            error_message=(message or "process failed")[-_STDERR_TAIL:],
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
        task.error_message = (message or "process failed")[-_STDERR_TAIL:]
        task.finished_at = _now()
        if work is not None:
            task.result_json = {"work_dir": str(work)}
        await session.commit()



def _prefer_claude_exe(found: str) -> str:
    """Prefer the real Windows binary over npm's .cmd shim when present."""
    path = Path(found)
    if path.suffix.lower() not in {".cmd", ".bat", ".ps1"}:
        return found
    exe = path.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    if exe.is_file():
        return str(exe)
    return found



def _claude_fail_detail(claude_bin: str, code: int, stderr: str) -> str:
    """Build a non-empty process_failed message that includes exit code and bin."""
    tail = (stderr or "").strip()
    if not tail:
        tail = "process failed (no stderr)"
    return f"claude exit {code}; bin={claude_bin}; {tail}"[-_STDERR_TAIL:]

def resolve_claude_bin(claude_bin: str | None = None) -> str:
    """Resolve Claude Code CLI to a path create_subprocess_exec can launch.

    Bare name "claude" fails on Windows asyncio (no PATHEXT search). Prefer an
    absolute path from settings, PATH, or the npm-installed claude.exe.
    """
    candidates: list[str] = []
    if claude_bin and claude_bin.strip():
        candidates.append(claude_bin.strip())
    try:
        from app.core.config import get_settings

        configured = (get_settings().claude_cli_path or "").strip()
        if configured:
            candidates.append(configured)
    except Exception:  # noqa: BLE001 — settings optional at import time in tests
        pass
    candidates.append("claude")

    seen: set[str] = set()
    for raw in candidates:
        if raw in seen:
            continue
        seen.add(raw)
        path = Path(raw)
        if path.is_file():
            return str(path.resolve())
        found = shutil.which(raw)
        if found:
            return _prefer_claude_exe(found)
    raise FileNotFoundError(
        "找不到 Claude Code 命令行。请安装 @anthropic-ai/claude-code，"
        "或设置环境变量 CLAUDE_CLI_PATH 为 claude 可执行文件路径。"
    )


def _claude_env(api_key: str, base_url: str | None) -> dict[str, str]:
    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"] = api_key
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    else:
        env.pop("ANTHROPIC_BASE_URL", None)
    return env




_sync_engine = None


def _get_sync_engine():
    """Lazy sync engine for cancel checks from Windows worker threads."""
    global _sync_engine
    if _sync_engine is None:
        from sqlalchemy import create_engine

        from app.core.config import get_settings

        url = get_settings().database_url
        for async_driver, sync_driver in (
            ("mysql+aiomysql", "mysql+pymysql"),
            ("mysql+asyncmy", "mysql+pymysql"),
            ("postgresql+asyncpg", "postgresql+psycopg"),
            ("sqlite+aiosqlite", "sqlite"),
        ):
            if url.startswith(async_driver):
                url = sync_driver + url[len(async_driver) :]
                break
        _sync_engine = create_engine(url, pool_pre_ping=True)
    return _sync_engine


def _stopped_sync(task_id: int) -> bool:
    """Best-effort cancel check from a worker thread.

    On failure (e.g. tests using SQLite while sync engine points at MySQL),
    return False so the run continues until the wall-clock timeout.
    """
    from sqlalchemy import text

    try:
        engine = _get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT status, deleted_at FROM studio_tasks WHERE id = :id"),
                {"id": task_id},
            ).first()
    except Exception:  # noqa: BLE001 — cancel check must not abort the run
        return False
    if row is None:
        return True
    status, deleted_at = row[0], row[1]
    return status == "canceled" or deleted_at is not None


def _run_claude_sync(
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
    """Windows-safe Claude launch.

    Celery uses a threads pool; asyncio.create_subprocess_exec raises a bare
    NotImplementedError on Windows outside the main thread. Use sync Popen and
    poll for timeout/cancel instead.
    """
    stdout_path = work / "stdout.log"
    stderr_path = work / "stderr.log"
    outcome = "ok"
    code = 1
    with stdout_path.open("wb") as stdout_f, stderr_path.open("wb") as stderr_f:
        try:
            proc = subprocess.Popen(
                [
                    claude_bin,
                    "-p",
                    "--permission-mode",
                    "bypassPermissions",
                    "--model",
                    model_name,
                    "--add-dir",
                    str(work),
                ],
                stdin=subprocess.PIPE,
                stdout=stdout_f,
                stderr=stderr_f,
                cwd=work,
                env=_claude_env(api_key, base_url),
            )
        except OSError as exc:
            msg = str(exc).strip() or f"{exc.__class__.__name__}: failed to start Claude Code"
            stderr_f.write(msg.encode("utf-8"))
            stderr_f.flush()
            return "ok", 1, msg
        try:
            assert proc.stdin is not None
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            (work / "runner_launched.txt").write_text(
                f"pid={proc.pid} bin={claude_bin} mode=sync", encoding="utf-8"
            )
        except OSError:
            pass
        deadline = time.monotonic() + timeout_seconds
        while proc.poll() is None:
            if time.monotonic() >= deadline:
                _kill_popen_group(proc)
                outcome = "timeout"
                break
            if _stopped_sync(task_id):
                _kill_popen_group(proc)
                outcome = "canceled"
                break
            time.sleep(min(_POLL_SECONDS, max(0.1, deadline - time.monotonic())))
        code = proc.returncode if proc.returncode is not None else 1
    stderr_text = ""
    if stderr_path.is_file():
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    try:
        (work / "runner_meta.json").write_text(
            json.dumps(
                {
                    "claude_bin": claude_bin,
                    "outcome": outcome,
                    "exit_code": code,
                    "stderr_len": len(stderr_text),
                    "stdout_len": stdout_path.stat().st_size if stdout_path.is_file() else 0,
                    "mode": "sync",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    return outcome, code, stderr_text


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
    if os.name == "nt":
        return await asyncio.to_thread(
            _run_claude_sync,
            claude_bin=claude_bin,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            work=work,
            prompt=prompt,
            task_id=task_id,
            timeout_seconds=timeout_seconds,
            factory=factory,
        )
    stdout_path = work / "stdout.log"
    stderr_path = work / "stderr.log"
    stdout_f = stdout_path.open("wb")
    stderr_f = stderr_path.open("wb")
    outcome = "ok"
    code = 1
    try:
        try:
            # Windows Celery threads: start_new_session (CREATE_NEW_PROCESS_GROUP)
            # has been observed to let claude.exe exit in <100ms with empty stdio.
            popen_kwargs: dict = {}
            if os.name != "nt":
                popen_kwargs["start_new_session"] = True
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
                **popen_kwargs,
            )
            try:
                (work / "runner_launched.txt").write_text(
                    f"pid={proc.pid} bin={claude_bin}", encoding="utf-8"
                )
            except OSError:
                pass
        except OSError as exc:
            msg = str(exc).strip() or f"{exc.__class__.__name__}: failed to start Claude Code"
            stderr_f.write(msg.encode("utf-8"))
            stderr_f.flush()
            return "ok", 1, msg
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
    try:
        (work / "runner_meta.json").write_text(
            json.dumps(
                {
                    "claude_bin": claude_bin,
                    "outcome": outcome,
                    "exit_code": code,
                    "stderr_len": len(stderr_text),
                    "stdout_len": stdout_path.stat().st_size if stdout_path.is_file() else 0,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
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
    claude_bin: str | None = None,
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

        try:
            resolved_bin = resolve_claude_bin(claude_bin)
        except FileNotFoundError as exc:
            await _mark_failed(factory, task_id, "process_failed", str(exc), work)
            return

        outcome, code, stderr = await _run_claude(
            claude_bin=resolved_bin,
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
        outputs = work / "outputs"
        if outcome == "timeout":
            # Claude may have finished the main artifact but hung on cleanup/MANIFEST.
            try:
                accepted = accept_outputs(get_format(prepared.format_key), outputs)
            except (FormatMismatch, NoOutput):
                tail = (stderr or "").strip()
                msg = f"已超过智能体超时上限 {limit} 秒仍未完成。"
                if tail:
                    msg = f"{msg}\n{tail}"
                await _mark_failed(factory, task_id, "timeout", msg, work)
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
            return
        fail_detail = _claude_fail_detail(resolved_bin, code, stderr)
        try:
            accepted = accept_outputs(get_format(prepared.format_key), outputs)
        except FormatMismatch:
            if code != 0:
                await _mark_failed(factory, task_id, "process_failed", fail_detail, work)
            else:
                await _mark_failed(factory, task_id, "format_mismatch", "format mismatch", work)
            return
        except NoOutput:
            if code != 0:
                await _mark_failed(factory, task_id, "process_failed", fail_detail, work)
            else:
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
        detail = str(exc).strip() or f"{exc.__class__.__name__}: studio runner crashed"
        if work is not None:
            try:
                (work / "runner_exception.txt").write_text(
                    f"{exc.__class__.__name__}: {exc!r}", encoding="utf-8"
                )
            except OSError:
                pass
        await _abandon_attempt(factory, task_id, detail, work, stored_keys)
