"""Run a queued studio task through a fake Claude process."""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select

from app.models.notebook import Note, Notebook, Subtitle, SubtitleLine, Video
from app.models.studio import (
    Agent,
    ClaudeCodeConfig,
    Skill,
    StudioArtifact,
    StudioCapability,
    StudioTask,
)
from app.models.user import User
from app.storage import get_storage
from app.studio.runner import execute_studio_task

_FIXED = (
    "阅读 inputs.json。若存在 .claude/skills 则使用其中的技能。"
    "不要修改 inputs.json。主文件和 MANIFEST.json 写在 outputs/。"
    "MANIFEST.json 只用上面给出的 status、title、artifacts 结构，不要改成技能自己的清单字段。"
)
_LONG = "不截断" * 80


async def _user(db_session) -> User:
    user = User(phone="13800000701", name="Runner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed(
    db_session,
    *,
    format_key: str = "mind_map",
    status: str = "queued",
    skill_path: str | None = None,
    with_sources: bool = True,
) -> tuple[StudioTask, Video | None, Note | None]:
    user = await _user(db_session)
    notebook = Notebook(owner_id=user.id, title="本", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.flush()

    skill_id = None
    if skill_path is not None:
        skill = Skill(
            name="导图技能",
            storage_path=skill_path,
            file_count=1,
            size_bytes=1,
            uploaded_by=user.id,
        )
        db_session.add(skill)
        await db_session.flush()
        skill_id = skill.id

    agent = Agent(
        name="导图智能体",
        system_prompt="写出导图",
        timeout_seconds=600,
        is_active=True,
        updated_by=user.id,
        skill_id=skill_id,
    )
    db_session.add(agent)
    await db_session.flush()
    config = await db_session.get(ClaudeCodeConfig, 1)
    if config is None:
        config = ClaudeCodeConfig(id=1)
        db_session.add(config)
    config.model_name = "claude-sonnet-4-6"
    config.base_url = None
    config.set_api_key("sk-test")
    await db_session.flush()
    cap = StudioCapability(
        name="思维导图" if format_key == "mind_map" else "PPT",
        icon="🧠",
        format_key=format_key,
        agent_id=agent.id,
        enabled=True,
        is_builtin=True,
        form_json=[],
    )
    db_session.add(cap)
    await db_session.flush()

    video = None
    note = None
    video_ids: list[int] = []
    note_ids: list[int] = []
    if with_sources:
        video = Video(
            owner_id=user.id,
            source_type="upload",
            status="ready",
            subtitle_status="ready",
            overview_status="pending",
            title="选中的片子",
        )
        db_session.add(video)
        await db_session.flush()
        subtitle = Subtitle(
            video_id=video.id,
            source="asr",
            language="zh",
            format="srt",
            line_count=2,
            version=1,
        )
        db_session.add(subtitle)
        await db_session.flush()
        db_session.add(
            SubtitleLine(
                subtitle_id=subtitle.id,
                line_no=1,
                start_ms=0,
                end_ms=1000,
                text="第一行",
            )
        )
        db_session.add(
            SubtitleLine(
                subtitle_id=subtitle.id,
                line_no=2,
                start_ms=1000,
                end_ms=2000,
                text="第二行" + _LONG,
            )
        )
        note = Note(
            notebook_id=notebook.id,
            author_id=user.id,
            title="笔记标题",
            content_text="笔记全文" + _LONG,
        )
        db_session.add(note)
        await db_session.flush()
        video_ids = [video.id]
        note_ids = [note.id]

    task = StudioTask(
        notebook_id=notebook.id,
        owner_id=user.id,
        capability_id=cap.id,
        agent_id=agent.id,
        format_key=format_key,
        title=cap.name,
        status=status,
        params_json={
            "language": "中文",
            "video_ids": video_ids,
            "note_ids": note_ids,
            "fields": [{"key": "topic", "label": "主题", "value": "灭佛"}],
        },
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    await db_session.commit()
    return task, video, note


def _script(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _mindmap_script(path: Path, capture: Path) -> None:
    stdin_file = capture / "stdin.txt"
    cwd_file = capture / "cwd.txt"
    inputs_file = capture / "inputs.json"
    argv_file = capture / "argv.txt"
    _script(
        path,
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > '{argv_file}'\n"
        f"cat > '{stdin_file}'\n"
        f"cp inputs.json '{inputs_file}'\n"
        "out=$(pwd)/outputs\n"
        "mkdir -p \"$out\"\n"
        "printf '# 灭佛\\n' > \"$out/mindmap.md\"\n"
        "cat > \"$out/MANIFEST.json\" <<'EOF'\n"
        '{"version":1,"status":"success","title":"自动标题","artifacts":[{"role":"main","path":"outputs/mindmap.md","mime":"text/markdown"}]}\n'
        "EOF\n"
        f"pwd > '{cwd_file}'\n",
    )


def _pptx_script(path: Path) -> None:
    _script(
        path,
        "#!/bin/sh\n"
        "out=$(pwd)/outputs\n"
        "mkdir -p \"$out\"\n"
        "printf 'PK pptx' > \"$out/deck.pptx\"\n",
    )


async def _artifacts(db_session, task_id: int) -> list[StudioArtifact]:
    rows = (
        await db_session.execute(
            select(StudioArtifact).where(StudioArtifact.task_id == task_id)
        )
    ).scalars().all()
    return list(rows)


async def test_fake_claude_stores_markdown(db_session, tmp_path):
    capture = tmp_path / "capture"
    capture.mkdir()
    script = tmp_path / "claude"
    _mindmap_script(script, capture)
    task, video, note = await _seed(db_session)
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "succeeded"
    assert task.title == "自动标题"
    artifact = (
        await db_session.execute(
            select(StudioArtifact).where(StudioArtifact.task_id == task.id)
        )
    ).scalar_one()
    assert artifact.text_content.startswith("# 灭佛")
    assert artifact.storage_key
    stdin = (capture / "stdin.txt").read_text(encoding="utf-8")
    assert "outputs/MANIFEST.json" in stdin
    assert "inputs.json" in stdin
    assert _FIXED in stdin
    assert "写出导图" in stdin
    assert "本次主题硬约束" in stdin
    assert "根节点必须是：灭佛" in stdin
    cwd = Path((capture / "cwd.txt").read_text(encoding="utf-8").strip())
    assert cwd.name.startswith(f"studio_{task.id}_")
    assert not cwd.exists()
    argv = (capture / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert argv[:6] == [
        "-p",
        "--permission-mode",
        "bypassPermissions",
        "--model",
        "claude-sonnet-4-6",
        "--add-dir",
    ]
    assert Path(argv[6]).resolve() == cwd.resolve()
    inputs = json.loads((capture / "inputs.json").read_text(encoding="utf-8"))
    assert inputs["language"] == "中文"
    assert inputs["fields"][0]["value"] == "灭佛"
    by_kind = {item["kind"]: item for item in inputs["sources"]}
    assert by_kind["video"]["id"] == video.id
    assert by_kind["video"]["title"] == "选中的片子"
    assert by_kind["video"]["text"].startswith("第一行\n第二行")
    assert _LONG in by_kind["video"]["text"]
    assert by_kind["note"]["id"] == note.id
    assert by_kind["note"]["title"] == "笔记标题"
    assert by_kind["note"]["text"] == "笔记全文" + _LONG



def test_resolve_claude_bin_prefers_existing_file(tmp_path, monkeypatch):
    from app.studio import runner as runner_mod

    fake = tmp_path / ("claude.exe" if os.name == "nt" else "claude")
    fake.write_text("x", encoding="utf-8")
    monkeypatch.setattr(runner_mod, "resolve_claude_bin", runner_mod.resolve_claude_bin)
    assert runner_mod.resolve_claude_bin(str(fake)) == str(fake.resolve())


def test_resolve_claude_bin_uses_which(monkeypatch, tmp_path):
    from app.studio import runner as runner_mod

    fake = tmp_path / "claude.cmd"
    fake.write_text("@echo off\n", encoding="utf-8")
    exe = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin"
    exe.mkdir(parents=True)
    target = exe / "claude.exe"
    target.write_text("x", encoding="utf-8")
    monkeypatch.setattr(runner_mod.shutil, "which", lambda name: str(fake) if name == "claude" else None)
    monkeypatch.setattr("app.core.config.get_settings", lambda: type("S", (), {"claude_cli_path": "claude"})())
    assert runner_mod.resolve_claude_bin(None) == str(target)


async def test_exit_code_is_process_failed(db_session, tmp_path):
    script = tmp_path / "claude"
    _script(script, "#!/bin/sh\necho boom >&2\nexit 1\n")
    task, _, _ = await _seed(db_session, with_sources=False)
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "failed"
    assert task.error_code == "process_failed"
    work = Path(task.result_json["work_dir"])
    assert work.is_dir()
    assert (work / "stderr.log").read_text(encoding="utf-8").strip() == "boom"


async def test_timeout(db_session, tmp_path):
    script = tmp_path / "claude"
    _script(script, "#!/bin/sh\nsleep 30\n")
    task, _, _ = await _seed(db_session, with_sources=False)
    await execute_studio_task(task.id, claude_bin=str(script), timeout_seconds=1)
    await db_session.refresh(task)
    assert task.status == "failed"
    assert task.error_code == "timeout"
    assert Path(task.result_json["work_dir"]).is_dir()


async def test_wrong_file_is_format_mismatch(db_session, tmp_path):
    script = tmp_path / "claude"
    _script(
        script,
        "#!/bin/sh\n"
        "out=$(pwd)/outputs\n"
        "mkdir -p \"$out\"\n"
        "printf 'hello' > \"$out/notes.txt\"\n"
        "cat > \"$out/MANIFEST.json\" <<'EOF'\n"
        '{"version":1,"status":"success","artifacts":[{"role":"main","path":"outputs/notes.txt","mime":"text/plain"}]}\n'
        "EOF\n",
    )
    task, _, _ = await _seed(db_session, with_sources=False)
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "failed"
    assert task.error_code == "format_mismatch"
    assert Path(task.result_json["work_dir"]).is_dir()


def _write_deck_pdf(pptx_path: Path, outputs_dir: Path) -> None:
    (outputs_dir / "deck.pdf").write_bytes(b"%PDF-1.4 deck")


def _raise_pdf(_pptx_path: Path, _outputs_dir: Path) -> None:
    raise RuntimeError("convert failed")


async def test_pdf_convert_stores_side_artifact(db_session, tmp_path):
    script = tmp_path / "claude"
    _pptx_script(script)
    task, _, _ = await _seed(db_session, format_key="slides", with_sources=False)
    await execute_studio_task(task.id, claude_bin=str(script), pdf_convert=_write_deck_pdf)
    await db_session.refresh(task)
    assert task.status == "succeeded"
    rows = await _artifacts(db_session, task.id)
    by_role = {row.role: row for row in rows}
    assert set(by_role) == {"main", "side"}
    assert by_role["main"].filename == "deck.pptx"
    assert by_role["main"].text_content is None
    assert by_role["main"].storage_key
    assert (
        by_role["main"].mime
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    assert by_role["side"].filename == "deck.pdf"
    assert by_role["side"].storage_key
    assert task.result_json is None or "pdf_error" not in (task.result_json or {})


async def test_pdf_error_keeps_success(db_session, tmp_path):
    script = tmp_path / "claude"
    _pptx_script(script)
    task, _, _ = await _seed(db_session, format_key="slides", with_sources=False)
    await execute_studio_task(task.id, claude_bin=str(script), pdf_convert=_raise_pdf)
    await db_session.refresh(task)
    assert task.status == "succeeded"
    assert task.result_json["pdf_error"]
    rows = await _artifacts(db_session, task.id)
    assert rows
    assert all(row.role != "side" for row in rows)


async def test_missing_skill_dir_is_process_failed(db_session, tmp_path):
    marker = tmp_path / "started"
    script = tmp_path / "claude"
    _script(script, f"#!/bin/sh\ntouch '{marker}'\n")
    task, _, _ = await _seed(
        db_session,
        with_sources=False,
        skill_path=str(tmp_path / "missing-skill"),
    )
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "failed"
    assert task.error_code == "process_failed"
    assert not marker.exists()
    assert Path(task.result_json["work_dir"]).is_dir()


async def test_skips_task_that_is_not_queued(db_session, tmp_path):
    script = tmp_path / "claude"
    _mindmap_script(script, tmp_path / "capture")
    (tmp_path / "capture").mkdir()
    task, _, _ = await _seed(db_session, status="running", with_sources=False)
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "running"
    assert task.title == "思维导图"
    assert await _artifacts(db_session, task.id) == []


async def test_cancel_during_prepare_is_not_started(db_session, tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from app.studio import runner as runner_module

    marker = tmp_path / "started"
    script = tmp_path / "claude"
    _script(script, f"#!/bin/sh\ntouch '{marker}'\n")
    task, _, _ = await _seed(db_session, with_sources=False)
    original = runner_module._prepare

    async def cancel_during_prepare(session, studio_task):
        studio_task.status = "canceled"
        studio_task.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
        return await original(session, studio_task)

    monkeypatch.setattr(runner_module, "_prepare", cancel_during_prepare)
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "canceled"
    assert not marker.exists()


async def test_runner_keeps_blob_shared_with_another_task(db_session, tmp_path, monkeypatch):
    data = b"hello-map\n"
    key = get_storage().put(data=data, content_type="text/markdown", suffix=".md")
    keeper, _, _ = await _seed(db_session, status="succeeded", with_sources=False)
    db_session.add(
        StudioArtifact(
            task_id=keeper.id,
            role="main",
            filename="mindmap.md",
            mime="text/markdown",
            storage_key=key,
            text_content="hello-map\n",
        )
    )
    await db_session.commit()

    script = tmp_path / "claude"
    _script(
        script,
        "#!/bin/sh\n"
        "out=$(pwd)/outputs\n"
        "mkdir -p \"$out\"\n"
        "printf 'hello-map\\n' > \"$out/mindmap.md\"\n",
    )
    task = StudioTask(
        notebook_id=keeper.notebook_id,
        owner_id=keeper.owner_id,
        capability_id=keeper.capability_id,
        agent_id=keeper.agent_id,
        format_key=keeper.format_key,
        title=keeper.title,
        status="queued",
        params_json={"language": "中文", "video_ids": [], "note_ids": [], "fields": []},
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    from app.studio import runner as runner_module

    storage = get_storage()
    real_put = storage.put
    seen: list[str] = []

    def spy_put(**kwargs):
        stored = real_put(**kwargs)
        seen.append(stored)
        return stored

    monkeypatch.setattr(storage, "put", spy_put)
    real_store = runner_module._store_success

    async def cancel_then_store(*args, **kwargs):
        task_id = args[1]
        factory = runner_module.get_sessionmaker()
        async with factory() as session:
            row = await session.get(StudioTask, task_id)
            row.status = "canceled"
            await session.commit()
        await real_store(*args, **kwargs)

    monkeypatch.setattr(runner_module, "_store_success", cancel_then_store)
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert seen == [key]
    assert task.status == "canceled"
    assert await _artifacts(db_session, task.id) == []
    assert get_storage().exists(key)
    assert get_storage().get(key) == data


async def test_pdf_convert_deadline_keeps_success(db_session, tmp_path, monkeypatch):
    soffice = tmp_path / "soffice"
    _script(soffice, "#!/bin/sh\nsleep 30\n")
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join([str(tmp_path), os.environ.get("PATH", "")]),
    )
    script = tmp_path / "claude"
    _pptx_script(script)
    task, _, _ = await _seed(db_session, format_key="slides", with_sources=False)
    await execute_studio_task(task.id, claude_bin=str(script), pdf_timeout_seconds=1)
    await db_session.refresh(task)
    assert task.status == "succeeded"
    assert "timed out" in task.result_json["pdf_error"]
    rows = await _artifacts(db_session, task.id)
    assert [row.role for row in rows] == ["main"]
    assert get_storage().get(rows[0].storage_key) == b"PK pptx"


async def test_unexpected_error_after_running_is_process_failed(db_session, tmp_path, monkeypatch):
    script = tmp_path / "claude"
    _script(script, "#!/bin/sh\nexit 0\n")
    task, _, _ = await _seed(db_session, with_sources=False)

    def boom(_fmt, _outputs):
        raise RuntimeError("accept blew up")

    monkeypatch.setattr("app.studio.runner.accept_outputs", boom)
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "failed"
    assert task.error_code == "process_failed"


async def test_missing_claude_config_does_not_start(db_session, tmp_path):
    capture = tmp_path / "capture"
    capture.mkdir()
    script = tmp_path / "claude"
    _mindmap_script(script, capture)
    task, _, _ = await _seed(db_session, with_sources=False)
    config = await db_session.get(ClaudeCodeConfig, 1)
    await db_session.delete(config)
    await db_session.commit()
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "failed"
    assert task.error_code == "process_failed"
    assert not (capture / "argv.txt").exists()


async def test_claude_env_comes_from_config_not_shell(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-shell")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://shell.example")
    capture = tmp_path / "capture"
    capture.mkdir()
    script = tmp_path / "claude"
    env_file = capture / "env.txt"
    _script(
        script,
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$ANTHROPIC_API_KEY\" \"$ANTHROPIC_BASE_URL\" > '{env_file}'\n"
        "mkdir -p outputs\n"
        "printf '# 灭佛\\n' > outputs/mindmap.md\n"
        "cat > outputs/MANIFEST.json <<'EOF'\n"
        '{"version":1,"status":"success","title":"自动标题","artifacts":[{"role":"main","path":"outputs/mindmap.md","mime":"text/markdown"}]}\n'
        "EOF\n",
    )
    task, _, _ = await _seed(db_session, with_sources=False)
    config = await db_session.get(ClaudeCodeConfig, 1)
    config.model_name = "claude-opus-4-6"
    config.base_url = "https://config.example"
    config.set_api_key("sk-from-config")
    await db_session.commit()
    await execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "succeeded"
    assert (capture / "env.txt").read_text(encoding="utf-8").splitlines() == [
        "sk-from-config",
        "https://config.example",
    ]

def test_prompt_injects_topic_hard_constraints_for_action_mode():
    from app.studio.runner import _prompt, _topic_hard_constraints

    fields = [
        {"key": "topic", "label": "主题", "value": "年轻人如何应对"},
        {"key": "focus_mode", "label": "导图模式", "value": "action"},
        {"key": "extra_constraints", "label": "额外约束", "value": "一级仅行动建议"},
    ]
    hard = _topic_hard_constraints("mind_map", fields)
    assert hard is not None
    assert "年轻人如何应对" in hard
    assert "聚焦应对/行动" in hard
    assert "用户额外约束：一级仅行动建议" in hard
    assert "优先于技能里的全书大纲流程" in hard

    prompt = _prompt("mind_map", "系统提示", fields)
    assert hard in prompt
    assert prompt.index(hard) < prompt.index("系统提示")
    assert "阅读 inputs.json" in prompt


def test_prompt_outline_mode_allows_full_structure():
    from app.studio.runner import _topic_hard_constraints

    fields = [
        {"key": "topic", "label": "主题", "value": "年轻人如何应对"},
        {"key": "focus_mode", "label": "导图模式", "value": "outline"},
    ]
    hard = _topic_hard_constraints("mind_map", fields)
    assert hard is not None
    assert "完整大纲" in hard
    assert "根节点必须是" not in hard


def test_prompt_skips_hard_block_without_topic():
    from app.studio.runner import _topic_hard_constraints

    assert _topic_hard_constraints("mind_map", [{"key": "topic", "value": "  "}]) is None
    assert _topic_hard_constraints("slides", [{"key": "topic", "value": "x"}]) is None
