# Studio 能力、智能体与技能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 管理员能配置技能、智能体和 Studio 能力；笔记本右栏能按能力生成 Markdown 导图、PPTX 或文件，并用对应预览打开。

**Architecture:** 能力指向一个智能体和一种代码登记的产物格式，表单存在能力上。API 只写入 `queued` 任务并投递 Celery 队列 `studio`。worker 用 `claude -p` 在临时目录里跑，按格式验收 `outputs/`，再把主文件放进现有对象存储。导图预览读 Markdown 文本；幻灯片预览读转好的 PDF。

**Tech Stack:** FastAPI、SQLAlchemy 2、Alembic、Celery、Redis、pytest、React 18、Vite、markmap-lib、markmap-view。

**Spec:** `docs/superpowers/specs/2026-10-17-studio-agent-skill-design.md`

## Global Constraints

- 技能 zip 上限 32MB。根目录有 `SKILL.md`，或仅一层文件夹且其中有 `SKILL.md`。路径含 `..`、绝对路径或以 `/` 开头则整包拒绝。
- 智能体提供方只有 `claude_code`。超时默认 600 秒，最小 30，最大 3600。
- 停用智能体时，指向它的能力 `enabled` 改为 false。被未删除能力引用时不能删智能体。被未删除智能体引用时不能删技能。
- 产物格式创建后不能改。`PATCH` 带 `format_key` 返回 400。
- 表单只有 `sources`、`language`、`text`。前两种各自最多一个。文本 `key` 匹配 `^[a-z][a-z0-9_]{0,31}$`，一条能力内唯一。
- 语言只允许 `中文` 和 `English`。
- 预置能力：`思维导图` / `🧠` / `mind_map`，表单为语言、来源、必填单行 `topic`「主题」；`PPT` / `📊` / `slides`，表单为语言、来源、必填多行 `brief`「描述」，提示为「写明受众、结构和期望页数」。两条默认不启用。已存在则不覆盖。预置能力不能删。
- 有任务的自建能力不能删。没有合格智能体时启用能力返回 409。
- 笔记增加 `selected_for_chat`，默认 true。普通聊天不传 `note_ids` 时行为不变。
- 用户可见失败只有：`timeout` 超时、`process_failed` 进程失败、`no_output` 没有主产物、`format_mismatch` 格式不对。
- 非所有者访问 Studio 任务返回 404。管理员接口对普通用户返回 403。
- worker 队列名 `studio`，并发 2。API 进程不跑 Claude。命令是 `claude -p --permission-mode bypassPermissions --model <model_name> --add-dir <work_dir>`，提示从标准输入送入。
- 取消由 worker 每 2 秒读任务状态后结束自己的进程组。API 不发信号。
- 失败工作目录保留 24 小时。扫描间隔 10 分钟。正常超时是 `SIGTERM`，5 秒后 `SIGKILL`。
- PDF 用 `soffice --headless --convert-to pdf --outdir <outputs> <pptx>`。转换失败不把任务打成失败。
- 讨论句有父节点时是 `Discuss what these sources say about {当前}, in the larger context of {父节点}.`，根节点是 `Discuss what these sources say about {当前}.`
- 这期不做第四种格式、建议长度、自动重试、每用户一套智能体、发现页、把字幕任务迁到 Celery。

## 文件地图

| 文件 | 职责 |
|---|---|
| `api/app/models/studio.py` | 技能、智能体、能力、任务、产物 |
| `api/app/models/notebook.py` | 笔记加 `selected_for_chat` |
| `api/alembic/versions/0010_studio.py` | 上述表和列 |
| `api/app/studio/formats.py` | 三种格式的提示与验收 |
| `api/app/studio/runner.py` | 工作目录、进程、入库、取消轮询 |
| `api/app/studio/worker.py` | Celery 应用，只调用 runner |
| `api/app/services/skills.py` | zip 校验与技能 CRUD |
| `api/app/services/agents.py` | 智能体 CRUD 与停用连动 |
| `api/app/services/capabilities.py` | 能力 CRUD、表单校验、种子 |
| `api/app/services/studio_tasks.py` | 创建、列表、删除、入队 |
| `api/app/routes/admin_skills.py` | `/api/admin/skills` |
| `api/app/routes/admin_agents.py` | `/api/admin/agents` |
| `api/app/routes/admin_studio.py` | `/api/admin/studio` |
| `api/app/routes/studio.py` | 笔记本 Studio |
| `web/src/pages/admin-skills.tsx` | 技能页 |
| `web/src/pages/admin-agents.tsx` | 智能体页 |
| `web/src/pages/admin-studio.tsx` | 能力页 |
| `web/src/components/studio-panel.tsx` | 右栏能力、表单、任务列表 |
| `web/src/components/studio-mindmap.tsx` | markmap 预览与讨论句 |
| `web/src/components/studio-slides.tsx` | PDF iframe 与下载 |
| `web/src/lib/studio-discuss.ts` | 讨论句纯函数 |

测试不连 Redis，不调用真的 `claude`，不要求安装 LibreOffice。Celery 任务函数在测试里直接调用 runner。

---

### Task 1: 表与笔记勾选

**Files:**
- Create: `api/app/models/studio.py`
- Create: `api/alembic/versions/0010_studio.py`
- Modify: `api/app/models/notebook.py`（`Note` 增加列）
- Modify: `api/tests/conftest.py`（import 新模型；清理表顺序加上五张新表）
- Test: `api/tests/test_studio_schema.py`

**Interfaces:**
- Consumes: `Base`、`TimestampMixin`、`BigInt` 写法见 `api/app/models/notebook.py`
- Produces: 模型类 `Skill`、`Agent`、`StudioCapability`、`StudioTask`、`StudioArtifact`。`Note.selected_for_chat: bool`，默认 true。任务状态字符串 `queued|running|succeeded|failed|canceled`。

- [ ] **Step 1: Write the failing test**

```python
from app.db.base import Base
from app.models.studio import (  # noqa: F401
    Agent,
    Skill,
    StudioArtifact,
    StudioCapability,
    StudioTask,
)


def test_studio_tables_and_note_flag_exist():
    names = set(Base.metadata.tables)
    assert {
        "skills",
        "agents",
        "studio_capabilities",
        "studio_tasks",
        "studio_artifacts",
    } <= names
    assert "selected_for_chat" in Base.metadata.tables["notes"].c
    assert Base.metadata.tables["notes"].c.selected_for_chat.default.arg is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_studio_schema.py::test_studio_tables_and_note_flag_exist -v`

Expected: FAIL，`app.models.studio` 不存在。

- [ ] **Step 3: Write minimal implementation**

`Note` 增加：

```python
selected_for_chat: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

`studio.py` 五张表的列与规格第 4 节一致。`studio_tasks.deleted_at` 可空。`agents.provider` 用 `String(32)`，默认 `claude_code`，不要用数据库枚举。`studio_capabilities.format_key` 用 `String(32)`。`form_json`、`params_json`、`result_json` 用 `JSON`。

`0010_studio.py` 的 `down_revision` 是 `0009_notes`。`upgrade` 先给 `notes` 加列（`server_default=sa.true()`），再按 `skills` → `agents` → `studio_capabilities` → `studio_tasks` → `studio_artifacts` 建表。外键：`agents.skill_id` → `skills.id`，`studio_capabilities.agent_id` → `agents.id`，`studio_tasks.notebook_id` → `notebooks.id`，`studio_tasks.capability_id` → `studio_capabilities.id`，`studio_artifacts.task_id` → `studio_tasks.id`，删除任务时产物级联删除。

`conftest.py` 导入五个模型，并在清理顺序的最前面加入 `studio_artifacts`、`studio_tasks`、`studio_capabilities`、`agents`、`skills`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_studio_schema.py::test_studio_tables_and_note_flag_exist -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/models/studio.py api/app/models/notebook.py api/alembic/versions/0010_studio.py api/tests/conftest.py api/tests/test_studio_schema.py
git commit -m "Add studio tables and the note selection flag."
```

---

### Task 2: 产物格式验收

**Files:**
- Create: `api/app/studio/__init__.py`
- Create: `api/app/studio/formats.py`
- Test: `api/tests/test_studio_formats.py`

**Interfaces:**
- Consumes: 无
- Produces:

```python
class OutputFormat:
    key: str
    label: str
    instructions: str
    extensions: tuple[str, ...]  # 空元组表示 file 不限扩展名

class Accepted:
    path: Path
    mime: str
    title: str | None

class FormatMismatch(Exception): ...
class NoOutput(Exception): ...

def get_format(key: str) -> OutputFormat: ...
def list_formats() -> list[OutputFormat]: ...
def accept_outputs(fmt: OutputFormat, outputs_dir: Path) -> Accepted: ...
```

`get_format` 未知 key 抛 `KeyError`。`accept_outputs` 按规格第 3.4 节和第 5.4 节：清单可用则验收主文件；清单缺失或损坏则兜底。空文件、扩展名不对抛 `FormatMismatch`。零个或多个兜底文件抛 `NoOutput`。`path` 必须解析后仍在 `outputs_dir` 内。

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

import pytest

from app.studio.formats import FormatMismatch, NoOutput, accept_outputs, get_format


def _write(dirpath: Path, name: str, data: bytes) -> None:
    target = dirpath / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def test_manifest_markdown_is_accepted(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write(outputs, "mindmap.md", b"# Topic\n")
    (outputs / "MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "status": "success",
                "title": "灭佛",
                "artifacts": [
                    {"role": "main", "path": "outputs/mindmap.md", "mime": "text/markdown"}
                ],
            }
        ),
        encoding="utf-8",
    )
    accepted = accept_outputs(get_format("mind_map"), outputs)
    assert accepted.title == "灭佛"
    assert accepted.path.name == "mindmap.md"
    assert accepted.path.read_text(encoding="utf-8").startswith("# Topic")


def test_missing_manifest_accepts_one_pptx(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write(outputs, "deck.pptx", b"PK pptx")
    accepted = accept_outputs(get_format("slides"), outputs)
    assert accepted.path.name == "deck.pptx"
    assert accepted.title is None


def test_wrong_extension_is_format_mismatch(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write(outputs, "notes.txt", b"hello")
    (outputs / "MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "status": "success",
                "artifacts": [{"role": "main", "path": "outputs/notes.txt", "mime": "text/plain"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FormatMismatch):
        accept_outputs(get_format("mind_map"), outputs)


def test_empty_file_is_format_mismatch(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write(outputs, "mindmap.md", b"")
    (outputs / "MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "status": "success",
                "artifacts": [{"role": "main", "path": "outputs/mindmap.md", "mime": "text/markdown"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FormatMismatch):
        accept_outputs(get_format("mind_map"), outputs)


def test_two_files_without_manifest_are_no_output(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write(outputs, "a.md", b"# A\n")
    _write(outputs, "b.md", b"# B\n")
    with pytest.raises(NoOutput):
        accept_outputs(get_format("mind_map"), outputs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_studio_formats.py -v`

Expected: FAIL，`app.studio.formats` 不存在。

- [ ] **Step 3: Write minimal implementation**

三种格式的 `instructions` 用规格第 3.1–3.3 节的原文。`mind_map.extensions` 是 `(".md", ".markdown")`。`slides.extensions` 是 `(".pptx",)`。`file.extensions` 是 `()`。

清单里的 `path` 写成 `outputs/mindmap.md` 时，相对 `outputs_dir` 的父目录解析；若写成 `mindmap.md`，相对 `outputs_dir` 解析。解析结果必须位于 `outputs_dir.resolve()` 之下。`status != "success"` 抛 `FormatMismatch`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_studio_formats.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/studio/__init__.py api/app/studio/formats.py api/tests/test_studio_formats.py
git commit -m "Accept studio artifacts against the registered output formats."
```

---

### Task 3: 技能管理 API

**Files:**
- Create: `api/app/services/skills.py`
- Create: `api/app/schemas/studio.py`
- Create: `api/app/routes/admin_skills.py`
- Modify: `api/app/routes/__init__.py`
- Test: `api/tests/test_admin_skills.py`

**Interfaces:**
- Consumes: `Skill`、`ConflictError`、`BadRequestError`、`require_admin`
- Produces:

```python
MAX_SKILL_ZIP_BYTES = 32 * 1024 * 1024

async def create_skill_from_zip(session, *, uploaded_by: int, data: bytes) -> Skill: ...
async def update_skill(session, skill_id: int, *, name: str | None, description: str | None, version: str | None) -> Skill: ...
async def delete_skill(session, skill_id: int) -> None: ...
def skill_zip_bytes(skill: Skill) -> bytes: ...
```

路由前缀 `/admin/skills`。下载用 `StreamingResponse`，文件名 `skill-<id>.zip`。

- [ ] **Step 1: Write the failing test**

测试助手与 `api/tests/test_credentials_models.py` 相同：插入 `role="admin"` 的用户，`create_access_token(admin.id, role="admin")`，请求头 `{"Authorization": f"Bearer {token}"}`。

```python
import io
import zipfile

def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buf.getvalue()


async def test_upload_requires_skill_md(client, admin_headers):
    bad = _zip({"README.md": "nope"})
    response = await client.post(
        "/api/admin/skills",
        headers=admin_headers,
        files={"file": ("skill.zip", bad, "application/zip")},
    )
    assert response.status_code == 400


async def test_upload_single_folder_and_reject_traversal(client, admin_headers):
    good = _zip({"officecli-pptx/SKILL.md": "---\nname: officecli-pptx\n---\n"})
    created = await client.post(
        "/api/admin/skills",
        headers=admin_headers,
        files={"file": ("skill.zip", good, "application/zip")},
    )
    assert created.status_code == 201
    assert created.json()["name"] == "officecli-pptx"
    slipped = _zip({"../SKILL.md": "x"})
    rejected = await client.post(
        "/api/admin/skills",
        headers=admin_headers,
        files={"file": ("bad.zip", slipped, "application/zip")},
    )
    assert rejected.status_code == 400
```

再写四条：超过 32MB 的 zip 返回 400，且 `skills_root` 下没有新目录；`GET /api/admin/skills/{id}/download` 能解出原来的 `SKILL.md`；技能被某个 `Agent(skill_id=...)` 引用时 `DELETE` 返回 409；普通用户 token 调用 `GET /api/admin/skills` 返回 403。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_admin_skills.py -v`

Expected: FAIL，404 或路由不存在。

- [ ] **Step 3: Write minimal implementation**

解压目标是 `get_settings().skills_root / str(skill.id)`。先插入行拿到 id，再解压；解压失败则删除该行和已写出的目录。名称取 `SKILL.md` frontmatter 的 `name`，没有则用 `skill-<id>`。同名未删除技能返回 409。

`delete_skill` 查询未删除且 `skill_id` 等于该技能的 `Agent`，有则 `ConflictError("技能仍被智能体引用")`。否则写 `deleted_at`，目录保留到软删之后不立刻删，避免误删正在复制的运行；本任务不删目录。

在 `routes/__init__.py` 挂上 `admin_skills.router`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_admin_skills.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/services/skills.py api/app/schemas/studio.py api/app/routes/admin_skills.py api/app/routes/__init__.py api/tests/test_admin_skills.py
git commit -m "Add admin skill upload with zip checks."
```

---

### Task 4: 智能体管理 API

**Files:**
- Create: `api/app/services/agents.py`
- Create: `api/app/routes/admin_agents.py`
- Modify: `api/app/schemas/studio.py`
- Modify: `api/app/routes/__init__.py`
- Test: `api/tests/test_admin_agents.py`

**Interfaces:**
- Consumes: `Agent`、`StudioCapability`、`Skill`
- Produces:

```python
async def create_agent(session, *, updated_by: int, payload: AgentWrite) -> Agent: ...
async def disable_agent(session, agent_id: int) -> Agent: ...
async def enable_agent(session, agent_id: int) -> Agent: ...
async def delete_agent(session, agent_id: int) -> None: ...
```

`AgentWrite` 字段：`name: str`，`skill_id: int | None`，`model_name: str`，`system_prompt: str`，`timeout_seconds: int = 600`。超时不在 30 到 3600 之间返回 400。`skill_id` 指向已删除或不存在的技能返回 400。

- [ ] **Step 1: Write the failing test**

```python
async def test_disable_agent_turns_off_capabilities(client, admin_headers, db_session):
    created = await client.post(
        "/api/admin/agents",
        headers=admin_headers,
        json={
            "name": "导图智能体",
            "skill_id": None,
            "model_name": "claude-sonnet-4-6",
            "system_prompt": "写出导图",
            "timeout_seconds": 600,
        },
    )
    assert created.status_code == 201
    agent_id = created.json()["id"]
    cap = StudioCapability(
        name="思维导图",
        icon="🧠",
        format_key="mind_map",
        agent_id=agent_id,
        enabled=True,
        is_builtin=True,
        form_json=[],
    )
    db_session.add(cap)
    await db_session.commit()
    disabled = await client.post(f"/api/admin/agents/{agent_id}/disable", headers=admin_headers)
    assert disabled.status_code == 200
    await db_session.refresh(cap)
    assert cap.enabled is False
    removed = await client.delete(f"/api/admin/agents/{agent_id}", headers=admin_headers)
    assert removed.status_code == 409
```

再写一条：`timeout_seconds=10` 返回 400。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_admin_agents.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`disable_agent` 把 `is_active` 设为 false，并把 `agent_id` 指向它且未删除的能力 `enabled` 设为 false。`delete_agent` 在仍有未删除能力指向它时抛 `ConflictError("智能体仍被能力选用")`，否则写 `deleted_at`。`provider` 固定写 `claude_code`，请求体里没有这个字段。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_admin_agents.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/services/agents.py api/app/routes/admin_agents.py api/app/schemas/studio.py api/app/routes/__init__.py api/tests/test_admin_agents.py
git commit -m "Add agents and turn off capabilities when an agent is disabled."
```

---

### Task 5: 能力管理 API 与预置种子

**Files:**
- Create: `api/app/services/capabilities.py`
- Create: `api/app/routes/admin_studio.py`
- Modify: `api/app/main.py`（lifespan 里在管理员种子之后调用能力种子）
- Modify: `api/app/schemas/studio.py`
- Modify: `api/app/routes/__init__.py`
- Test: `api/tests/test_admin_capabilities.py`

**Interfaces:**
- Consumes: `get_format`、`Agent`、`StudioCapability`、`StudioTask`
- Produces:

```python
def validate_form(fields: list[dict]) -> list[dict]: ...
async def seed_builtin_capabilities(session) -> None: ...
async def enable_capability(session, capability_id: int) -> StudioCapability: ...
async def delete_capability(session, capability_id: int) -> None: ...
```

`GET /api/admin/studio/formats` 返回 `[{key, label}]`。启用时智能体缺失、已删除或 `is_active` 为 false，抛 `ConflictError("能力还没有可用的智能体")`。

- [ ] **Step 1: Write the failing test**

```python
async def test_seed_is_idempotent_and_enable_requires_agent(client, admin_headers, db_session):
    from app.services.capabilities import seed_builtin_capabilities

    await seed_builtin_capabilities(db_session)
    await seed_builtin_capabilities(db_session)
    rows = (
        await db_session.execute(
            select(StudioCapability).where(StudioCapability.is_builtin.is_(True))
        )
    ).scalars().all()
    assert {row.format_key for row in rows} == {"mind_map", "slides"}
    assert all(row.enabled is False for row in rows)
    mind = next(row for row in rows if row.format_key == "mind_map")
    mind.name = "改过的名字"
    await db_session.commit()
    await seed_builtin_capabilities(db_session)
    await db_session.refresh(mind)
    assert mind.name == "改过的名字"
    assert [field["type"] for field in mind.form_json] == ["language", "sources", "text"]
    assert mind.form_json[2]["key"] == "topic"
    denied = await client.post(
        f"/api/admin/studio/capabilities/{mind.id}/enable",
        headers=admin_headers,
    )
    assert denied.status_code == 409
```

再写三条：两个 `sources` 字段的 `POST` 返回 400；`PATCH` 带 `format_key` 返回 400；预置能力 `DELETE` 返回 409；自建能力在存在 `StudioTask` 时 `DELETE` 返回 409，没有任务时返回 204。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_admin_capabilities.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

种子只在不存在 `is_builtin=true` 且 `format_key` 匹配的行时插入。`validate_form` 拒绝重复的来源、语言和文本 `key`，以及不匹配正则的 `key`。`main.py` 的 lifespan 在 `seed_admin_if_empty()` 之后调用 `seed_builtin_capabilities`。测试环境 `APP_ENV=test` 时不要在 lifespan 里自动种子，避免和用例互相污染；用例自己调用函数。`app_env == "test"` 时跳过。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_admin_capabilities.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/services/capabilities.py api/app/routes/admin_studio.py api/app/schemas/studio.py api/app/main.py api/app/routes/__init__.py api/tests/test_admin_capabilities.py
git commit -m "Add studio capabilities and seed the two builtin entries."
```

---

### Task 6: 创建 Studio 任务

**Files:**
- Create: `api/app/services/studio_tasks.py`
- Create: `api/app/routes/studio.py`
- Modify: `api/app/routes/__init__.py`
- Test: `api/tests/test_studio_tasks.py`

**Interfaces:**
- Consumes: `validate_form` 的结果存在 `form_json`、`get_notebook`
- Produces:

```python
async def create_task(session, *, owner_id: int, notebook_id: int, body: TaskCreate) -> StudioTask: ...
def enqueue_studio_task(task_id: int) -> None: ...
```

`TaskCreate`：`capability_id: int`，`language: str | None`，`video_ids: list[int]`，`note_ids: list[int]`，`fields: dict[str, str]`。

`enqueue_studio_task` 本任务先调用 `app.studio.worker.studio_run.delay`。测试里 monkeypatch 成记录 id 的函数。若 `delay` 抛异常，把任务写成 `failed` / `process_failed`。

- [ ] **Step 1: Write the failing test**

准备一本所有者的笔记本、一条启用的 `mind_map` 能力、一个启用的智能体、一个 `selected_for_chat=true` 的视频。表单是语言、来源、必填 `topic`。

```python
async def test_create_task_snapshots_and_rejects_outsider(client, owner_headers, outsider_headers, notebook_id, capability_id, video_id, monkeypatch):
    queued: list[int] = []
    monkeypatch.setattr(
        "app.services.studio_tasks.enqueue_studio_task",
        lambda task_id: queued.append(task_id),
    )
    created = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=owner_headers,
        json={
            "capability_id": capability_id,
            "language": "中文",
            "video_ids": [video_id],
            "note_ids": [],
            "fields": {"topic": "灭佛"},
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "queued"
    assert body["format_key"] == "mind_map"
    assert body["title"] == "思维导图"
    assert queued == [body["id"]]
    hidden = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=outsider_headers,
        json={
            "capability_id": capability_id,
            "language": "中文",
            "video_ids": [video_id],
            "note_ids": [],
            "fields": {"topic": "灭佛"},
        },
    )
    assert hidden.status_code == 404
```

再写：必填文本空白返回 400；来源为空返回 400；`language` 为 `fr` 返回 400；能力 `enabled=false` 返回 400。`GET /api/notebooks/{id}/studio/capabilities` 不返回未启用的能力。`enqueue_studio_task` 抛异常时，该任务变为 `failed`，`error_code` 为 `process_failed`。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_studio_tasks.py::test_create_task_snapshots_and_rejects_outsider -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

创建前用所有者身份取笔记本，取不到按现有 `get_notebook` 的 404。校验视频和笔记都属于该笔记本。`params_json` 存规格第 4 节的形状。`title` 先写能力名称。先 `commit`，再 `enqueue_studio_task`。列表接口 `GET /api/notebooks/{id}/studio/tasks` 不返回 `deleted_at` 非空的行，按 `id` 降序，不带 `text_content`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_studio_tasks.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/services/studio_tasks.py api/app/routes/studio.py api/app/routes/__init__.py api/tests/test_studio_tasks.py
git commit -m "Queue a studio task from an enabled capability."
```

---

### Task 7: 运行器

**Files:**
- Create: `api/app/studio/runner.py`
- Test: `api/tests/test_studio_runner.py`

**Interfaces:**
- Consumes: `accept_outputs`、`get_format`、`get_storage`、`StudioTask`
- Produces:

```python
async def execute_studio_task(
    task_id: int,
    *,
    claude_bin: str = "claude",
    pdf_convert: Callable[[Path, Path], None] | None = None,
    timeout_seconds: int | None = None,
) -> None: ...

`timeout_seconds` 缺省时用智能体上的值。测试传入 `1`，避免真的等满 30 秒。
```

`pdf_convert(pptx_path, outputs_dir)` 默认调用 `soffice`。测试传入一个把 `deck.pdf` 写进目录的函数，以及一个抛 `RuntimeError` 的函数。

- [ ] **Step 1: Write the failing test**

假的 claude 是一个可执行脚本，读标准输入，把固定 Markdown 写到当前目录的 `outputs/mindmap.md`，并写清单 `title` 为 `自动标题`。脚本路径传给 `claude_bin`。

```python
async def test_fake_claude_stores_markdown(db_session, tmp_path, monkeypatch):
    script = tmp_path / "claude"
    script.write_text(
        "#!/bin/sh\n"
        "out=$(pwd)/outputs\n"
        "mkdir -p \"$out\"\n"
        "printf '# 灭佛\\n' > \"$out/mindmap.md\"\n"
        "cat > \"$out/MANIFEST.json\" <<'EOF'\n"
        '{"version":1,"status":"success","title":"自动标题","artifacts":[{"role":"main","path":"outputs/mindmap.md","mime":"text/markdown"}]}\n'
        "EOF\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    # 插入 queued 的 mind_map 任务，params_json 含 topic=灭佛、一个视频 id
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
```

再写四条：脚本 `exit 1` 时 `error_code == "process_failed"`；`execute_studio_task(..., timeout_seconds=1)` 且脚本 `sleep 30` 时 `error_code == "timeout"`；脚本写出 `notes.txt` 且格式是 `mind_map` 时 `error_code == "format_mismatch"`；`slides` 任务里 `pdf_convert` 抛错时任务仍是 `succeeded`，`result_json["pdf_error"]` 非空，且没有 `role=side` 的产物。成功那条还要断言工作目录已删除，并且假 claude 收到的标准输入含有 `outputs/MANIFEST.json` 和 `inputs.json`。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_studio_runner.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

只在状态仍是 `queued` 时改为 `running`。用独立的 session，不复用请求 session。工作目录用 `tempfile.mkdtemp(prefix=f"studio_{task_id}_")`。`inputs.json` 的 `sources` 由 `video_ids` 和 `note_ids` 装出，视频文本用 `load_subtitle` 的行文本拼接，笔记用 `content_text`。不截断。

`prompt.txt` 三截：格式 `instructions`、智能体 `system_prompt`、固定说明「阅读 inputs.json。若存在 .claude/skills 则使用其中的技能。不要修改 inputs.json。主文件和 MANIFEST.json 写在 outputs/。」

技能目录缺失时不启动进程，直接 `process_failed`。进程用 `asyncio.create_subprocess_exec`，`stdin=PIPE` 写入 `prompt.txt`，`start_new_session=True`。每 2 秒查一次任务，若 `status == "canceled"` 或 `deleted_at` 非空，`os.killpg`。超时按规格发 `SIGTERM` 再 `SIGKILL`。

成功后 `storage.put`。导图把同一份字节解码为 utf-8 写入 `text_content`。然后删除工作目录。失败保留目录，路径记在 `result_json.work_dir`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_studio_runner.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/studio/runner.py api/tests/test_studio_runner.py
git commit -m "Run a studio task through a Claude process and store its artifact."
```

---

### Task 8: Worker、取消与扫描

**Files:**
- Create: `api/app/studio/worker.py`
- Modify: `api/app/services/studio_tasks.py`（`enqueue_studio_task` 调用 `studio_run.delay`）
- Modify: `Makefile`
- Test: `api/tests/test_studio_cancel.py`

**Interfaces:**
- Consumes: `execute_studio_task`
- Produces:

```python
celery_app = Celery(...)

@celery_app.task(name="studio.run")
def studio_run(task_id: int) -> None: ...

async def sweep_studio_tasks(now: datetime) -> None: ...
async def delete_task(session, *, owner_id: int, task_id: int) -> None: ...
```

`studio_run` 只做 `asyncio.run(execute_studio_task(task_id))`。

- [ ] **Step 1: Write the failing test**

```python
async def test_delete_queued_task_is_not_run(db_session):
    # 插入一条 queued 任务
    await delete_task(db_session, owner_id=owner_id, task_id=task.id)
    await execute_studio_task(task.id, claude_bin="/bin/false")
    await db_session.refresh(task)
    assert task.status == "canceled"
    assert task.deleted_at is not None
```

`execute_studio_task` 看到状态不是 `queued` 就返回，不能把 `/bin/false` 的失败写进任务。再写两条：`sweep_studio_tasks` 把 `started_at` 早于超时加 60 秒、状态仍是 `running` 的任务写成 `failed` / `process_failed`；`result_json.work_dir` 指向的失败目录若修改时间早于 24 小时，扫描后目录不存在。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_studio_cancel.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`delete_task` 写 `deleted_at`。原状态是 `queued` 或 `running` 时改为 `canceled`。原状态已结束时，删除该任务产物的 `storage_key`。非所有者 `NotFoundError`。

`Makefile` 增加：

```makefile
worker:
	cd api && uv run celery -A app.studio.worker:celery_app worker -Q studio -c 2
```

`help` 里加一行说明。不要把 worker 放进 `make api`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_studio_cancel.py tests/test_studio_tasks.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/studio/worker.py api/app/services/studio_tasks.py Makefile api/tests/test_studio_cancel.py
git commit -m "Cancel studio tasks from the worker and add the studio queue."
```

---

### Task 9: 讨论用的笔记上下文

**Files:**
- Modify: `api/app/schemas/chat.py`
- Modify: `api/app/chat/service.py`
- Modify: `api/app/routes/chat.py`
- Test: `api/tests/test_chat.py`

**Interfaces:**
- Consumes: `prepare_chat(session, *, owner_id, notebook_id, message, source_ids)`
- Produces: `prepare_chat(..., note_ids: list[int] | None = None)`。`ChatRequest.note_ids: list[int] | None = None`。

不传 `note_ids` 时，现有 `test_chat.py` 全部保持通过。传入 `note_ids` 时，这些笔记的全文接在字幕上下文之后，不产生新的 `[n]` 编号。笔记不属于该笔记本则 404。快照里没有视频但有笔记时，允许发送，不再要求「至少一个来源有字幕」。

- [ ] **Step 1: Write the failing test**

在 `test_chat.py` 增加：

```python
async def test_chat_without_note_ids_stays_on_videos(client, db_session, user, monkeypatch):
    notebook_id, selected_id, _ignored = await _notebook_with_lines(db_session, user)
    note = Note(
        notebook_id=notebook_id,
        author_id=user.id,
        title="旁注",
        content_text="笔记里的句子",
        selected_for_chat=True,
    )
    db_session.add(note)
    await db_session.commit()
    captured: dict = {}

    async def fake_stream(prepared):
        captured["prompt"] = prepared.prompt
        yield {"type": "done", "message_id": None, "citations": []}

    monkeypatch.setattr("app.chat.service.stream_answer", fake_stream)
    token, _ = create_access_token(user.id, role=user.role)
    await client.post(
        f"/api/notebooks/{notebook_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "在说什么？", "source_ids": [selected_id]},
    )
    assert "笔记里的句子" not in captured["prompt"]
```

再写一条传入 `note_ids` 时，prompt 同时含字幕和「笔记里的句子」。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_chat.py::test_chat_without_note_ids_stays_on_videos -v`

Expected: FAIL，请求 422 或 prompt 断言失败。若 422，是因为模型还没这个字段；实现后第一条应 PASS，第二条在实现前 FAIL。两条一起跑到都 PASS。

- [ ] **Step 3: Write minimal implementation**

`post_chat` 把 `body.note_ids` 传给 `prepare_chat`。笔记块格式：

```text
笔记：旁注
笔记里的句子
```

多篇之间空一行。拼到 `context.text` 之后、用户问题之前。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_chat.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/schemas/chat.py api/app/chat/service.py api/app/routes/chat.py api/tests/test_chat.py
git commit -m "Let one chat turn include snapshotted note text."
```

---

### Task 10: 后台三页

**Files:**
- Create: `web/src/pages/admin-skills.tsx`
- Create: `web/src/pages/admin-agents.tsx`
- Create: `web/src/pages/admin-studio.tsx`
- Modify: `web/src/router.tsx`
- Modify: `web/src/pages/admin.tsx`

**Interfaces:**
- Consumes: 规格第 9 节的管理员 API。`api()` 来自 `web/src/lib/api.ts`。页面用现有 `RequireAuth admin`。
- Produces: 路由 `/admin/skills`、`/admin/agents`、`/admin/studio`。后台首页放三个链接。

Web 没有组件测试运行器。这一任务的自动检查是 `npm run typecheck`。

- [ ] **Step 1: 写三页的空路由，确认类型失败或页面尚未存在**

在 `router.tsx` 增加三条路由，暂时指向还不存在的页面，运行：

Run: `cd web && npm run typecheck`

Expected: FAIL，找不到页面模块。

- [ ] **Step 2: 实现三页**

技能页：表格列为名称、版本、大小、上传时间。上传用 `<input type="file" accept=".zip">`，`FormData` 字段名 `file`。删除 409 时显示返回的 `message`。

智能体页：表单字段只有名称、skill 下拉（含「不绑定」）、模型名、系统提示、超时。列表显示名称、技能名、模型、超时、启用。停用调用 `POST /api/admin/agents/{id}/disable`。

能力页：`GET /api/admin/studio/formats` 填产物格式下拉。创建后格式不可改，编辑表单不渲染格式控件。表单字段编辑器可以添加来源、语言、文本；来源或语言已存在时对应按钮禁用。文本要填 `key`、标题、提示、必填、单行或多行。启用失败时显示 409 的 `message`。预置两条在删除按钮处禁用。

`admin.tsx` 在标题下增加三个 `Link`。

- [ ] **Step 3: 类型检查**

Run: `cd web && npm run typecheck`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/admin-skills.tsx web/src/pages/admin-agents.tsx web/src/pages/admin-studio.tsx web/src/router.tsx web/src/pages/admin.tsx
git commit -m "Add admin pages for skills, agents, and studio capabilities."
```

---

### Task 11: 笔记本右栏的能力、表单和任务

**Files:**
- Create: `web/src/components/studio-panel.tsx`
- Modify: `web/src/pages/notebook.tsx`（用 `StudioPanel` 替换 `StudioHome` 里「还没接入」的分支；笔记视图保持原样）
- Modify: `web/src/pages/notebook.tsx` 的笔记行，加上与视频相同的勾选，调用现有选择接口。若笔记还没有选择端点，在 `api/app/routes/chat.py` 增加 `PATCH /api/notebooks/{id}/notes/{note_id}`，正文 `{selected_for_chat: bool}`，只改这一列。

**Interfaces:**
- Consumes: `GET /api/notebooks/{id}/studio/capabilities` 只返回已启用能力。`POST /api/notebooks/{id}/studio/tasks`。`GET /api/notebooks/{id}/studio/tasks`。`DELETE /api/studio/tasks/{id}`。
- Produces: `StudioPanel` 组件。进行中的任务每 2 秒重新拉取列表，直到没有 `queued` 或 `running`。

- [ ] **Step 1: Write the failing API test for note selection**

```python
async def test_patch_note_selection(client, owner_headers, notebook_id, note_id):
    response = await client.patch(
        f"/api/notebooks/{notebook_id}/notes/{note_id}",
        headers=owner_headers,
        json={"selected_for_chat": False},
    )
    assert response.status_code == 200
    assert response.json()["selected_for_chat"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_studio_tasks.py::test_patch_note_selection -v`

Expected: FAIL

- [ ] **Step 3: 实现选择接口和右栏**

选择接口只更新 `selected_for_chat`。笔记本详情里的笔记对象带上这个字段。

`StudioPanel`：上方按钮用能力的 `icon` 和 `name`。点击打开弹层。来源默认勾上 `selected_for_chat` 的视频和笔记，提交时用弹层里的选择，不调用选择接口。语言是「中文」「English」下拉。提交成功后关闭弹层并刷新任务。失败行把 `error_code` 显示成规格第 8 节的四句中文。删除调用 `DELETE`。

- [ ] **Step 4: Run tests and typecheck**

Run: `cd api && uv run pytest tests/test_studio_tasks.py -v`

Run: `cd web && npm run typecheck`

Expected: 两者都 PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/routes/chat.py api/tests/test_studio_tasks.py web/src/components/studio-panel.tsx web/src/pages/notebook.tsx
git commit -m "Show enabled studio capabilities and their tasks in the notebook."
```

---

### Task 12: 导图预览与节点讨论

**Files:**
- Create: `web/src/lib/studio-discuss.ts`
- Create: `web/src/components/studio-mindmap.tsx`
- Modify: `web/src/components/notebook-chat.tsx`（`readChatStream` 增加可选 `noteIds`，请求体带 `note_ids`）
- Modify: `web/src/pages/notebook.tsx`（成功的 `mind_map` 任务打开预览；节点点击把讨论交给中栏）
- Modify: `web/package.json`（依赖 `markmap-lib`、`markmap-view`）

**Interfaces:**
- Consumes: `GET /api/studio/tasks/{id}` 返回的 `text_content`、`params_json.video_ids`、`params_json.note_ids`
- Produces:

```ts
export function discussPrompt(current: string, parent: string | null): string
```

- [ ] **Step 1: 安装 markmap 并写讨论句函数**

```bash
cd web && npm install markmap-lib markmap-view
```

```ts
export function discussPrompt(current: string, parent: string | null): string {
  const text = current.trim();
  const upper = parent?.trim() ?? "";
  if (upper) {
    return `Discuss what these sources say about ${text}, in the larger context of ${upper}.`;
  }
  return `Discuss what these sources say about ${text}.`;
}
```

- [ ] **Step 2: 实现预览**

`studio-mindmap.tsx` 用 `markmap-lib` 的 `Transformer` 和 `markmap-view` 的 `Markmap.create`。左侧按钮调用 markmap 的放大、缩小和 `fit()`。全部展开把树节点的折叠状态清掉后 `setData`。下载用 `text_content` 生成 `Blob`，文件名用任务标题加 `.md`。

点击 `g.markmap-node` 里的文字（不是折叠用的 `circle`）时，用该节点文字和父节点文字调用 `discussPrompt`，通过 props `onDiscuss(message)` 交给笔记本页。导图不卸载。

笔记本页收到讨论后调用扩展后的 `readChatStream(access, notebookId, message, videoIds, { noteIds, ...handlers })`。`videoIds` 和 `noteIds` 来自该任务的 `params_json`，不用左栏当前勾选。

左上角列出快照来源。点视频沿用现有的左栏打开视频。点笔记沿用现有的右栏笔记视图，返回时回到这张导图。

铺满用一个 `fixed inset-0 z-40 bg-background` 的层，不新增路由。

- [ ] **Step 3: 类型检查**

Run: `cd web && npm run typecheck`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/package.json web/package-lock.json web/src/lib/studio-discuss.ts web/src/components/studio-mindmap.tsx web/src/components/notebook-chat.tsx web/src/pages/notebook.tsx
git commit -m "Preview mind maps and send a node discussion into chat."
```

---

### Task 13: 幻灯片与文件预览

**Files:**
- Create: `web/src/components/studio-slides.tsx`
- Create: `web/src/components/studio-file.tsx`
- Modify: `api/app/routes/studio.py`（`GET /api/studio/tasks/{id}` 与 `GET /api/studio/tasks/{id}/artifacts/{artifact_id}`）
- Modify: `web/src/pages/notebook.tsx`
- Test: `api/tests/test_studio_tasks.py`

**Interfaces:**
- Consumes: `storage.signed_url`，与 `get_play_url` 一样返回 `{url, expires_in}`
- Produces: 幻灯片预览组件和文件下载组件

- [ ] **Step 1: Write the failing test**

```python
async def test_artifact_url_is_signed(client, owner_headers, task_id, artifact_id):
    response = await client.get(
        f"/api/studio/tasks/{task_id}/artifacts/{artifact_id}",
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json()["url"].startswith("/api/storage/")
    assert "token=" in response.json()["url"]
```

任务和产物在测试里直接插入，`storage_key` 用测试 storage 放进去的一份字节。非所有者请求同一地址返回 404。`GET /api/studio/tasks/{id}` 对 `mind_map` 带 `text_content`，对 `slides` 不带文件字节，只带产物 id 和 `pdf_error`。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_studio_tasks.py::test_artifact_url_is_signed -v`

Expected: FAIL

- [ ] **Step 3: 实现预览**

`studio-slides.tsx`：没有 `pdf_error` 时，iframe 的 `src` 用 PDF 产物的 `url`。有 `pdf_error` 时显示「预览不可用」，不渲染 iframe，不提供 PDF 下载。更多菜单里 PPTX 下载始终用主产物的 `url`。

`studio-file.tsx` 只有一个下载按钮，用主产物的 `url`。没有铺满，没有画布。

幻灯片预览的铺满与导图同一层写法。

- [ ] **Step 4: Run tests and typecheck**

Run: `cd api && uv run pytest tests/test_studio_tasks.py tests/test_studio_runner.py tests/test_studio_formats.py -q`

Run: `cd web && npm run typecheck`

Expected: 两者都 PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/routes/studio.py api/tests/test_studio_tasks.py web/src/components/studio-slides.tsx web/src/components/studio-file.tsx web/src/pages/notebook.tsx
git commit -m "Preview slides as PDF and download generic studio files."
```

---

## 规格覆盖

| 规格 | 任务 |
|---|---|
| 表、笔记勾选 | 1 |
| 三种格式的验收和提示 | 2、7 |
| 技能 zip、32MB、引用时不能删 | 3 |
| 智能体超时、停用连动、引用时不能删 | 4 |
| 能力表单、预置种子、启用 409、删除规则 | 5 |
| 创建任务、快照、非所有者 404 | 6 |
| 运行器、假 claude、PDF 失败仍成功 | 7 |
| 取消、扫描、`make worker` | 8 |
| 讨论的 `note_ids`，普通聊天不变 | 9、12 |
| 后台三页 | 10 |
| 右栏表单、任务、四类错误、笔记勾选 | 11 |
| 导图预览和讨论句 | 12 |
| 幻灯片 iframe、文件下载、签名 URL | 13 |

不在任何任务里实现：发现页、自动重试、建议长度、第四种格式、字幕改走 Celery。

## 收尾检查

全部任务完成后运行：

```bash
cd api && uv run pytest -q
cd web && npm run typecheck
```

浏览器里用管理员上传一份含 `SKILL.md` 的 zip，建一个智能体并启用，把「思维导图」绑上它再启用。在笔记本里用勾选的来源生成一次。worker 需另开 `make worker`，且机器上有可用的 `claude`。没有真实 Claude 时，只靠上面的 pytest 验收运行器。
