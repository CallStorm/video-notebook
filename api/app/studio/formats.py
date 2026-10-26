from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_MIND_MAP_INSTRUCTIONS = """\
- 主文件是 markmap 用的 Markdown：`#` 为中心主题，子节点为缩进的无序列表。
- 路径 `outputs/mindmap.md`。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改：
  {"status":"success","title":"导图名称","artifacts":[{"role":"main","path":"outputs/mindmap.md","mime":"text/markdown"}]}
- 表单字段（`inputs.json` → `fields`）：
  - `topic`：主题（聚焦轴）
  - `focus_mode`：`action`（聚焦应对/行动，默认）或 `outline`（完整大纲）
  - `extra_constraints`：用户额外约束（若有，必须遵守）
- 若 prompt 中出现「本次主题硬约束」区块，其优先级高于本说明与技能里的全书大纲流程。
- 当 `focus_mode=action`（或未给 focus_mode 但 topic 非空）：
  - 根节点 `#` 必须用 topic（可轻微润色措辞，禁止扩写成视频全标题或章节总名）。
  - 一级分支只保留直接回答该主题的行动/原则/步骤/注意点。
  - 来源里与主题无关的块默认不进图：纯背景、征兆/症状清单、宏观叙事、历史铺垫、人物介绍等。
  - 若缺一点背景就无法理解主题，最多保留一个短「必要前提」节点，勿展开成大章。
  - 禁止按视频/文档章节目录做全覆盖式导图。
- 当 `focus_mode=outline`，或 topic 为空：可按来源全文做结构导图；根节点可用材料标题，topic 仅作参考。
- MANIFEST 的 title：action 模式优先用 topic；outline 模式可用材料标题。"""

_SLIDES_INSTRUCTIONS = """\
- 主文件是 pptx，路径 `outputs/deck.pptx`。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改，也不要写成技能自己的清单：
  {"status":"success","title":"演示标题","artifacts":[{"role":"main","path":"outputs/deck.pptx","mime":"application/vnd.openxmlformats-officedocument.presentationml.presentation"}]}"""

_STRUCTURED_NOTES_INSTRUCTIONS = """\
- 主文件是结构化笔记 JSON，路径 `outputs/notes.json`（UTF-8）。
- 也可用 Markdown 备选：`outputs/notes.md`（仅当无法写 JSON 时）。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改：
  {"status":"success","title":"笔记标题","artifacts":[{"role":"main","path":"outputs/notes.json","mime":"application/json"}]}
- JSON 字段（只写有内容的；数组可为空但不能省略键）：
  {
    "theme": "一句话主题",
    "concepts": [{"term": "术语", "definition": "一句话解释"}],
    "points": [{"time": "MM:SS 或 HH:MM:SS", "text": "带时间戳的要点"}],
    "evidence": [{"text": "论据或原文要点（精简）"}],
    "takeaways": ["可执行结论 / 行动项"]
  }
- 目标：帮助用户吸收来源——精简、好懂、可复查；禁止长散文堆砌。
- `points.time` 尽量来自字幕/时间轴；没有可靠时间戳时可省略 time，只保留 text。
- `concepts` 只收关键术语；`takeaways` 要可执行，不要空话。
- 表单字段（`inputs.json` → `fields`）：
  - `focus`：可选聚焦问题（有则围绕它裁剪，无关内容不写）
  - `extra_constraints`：用户额外约束（若有，必须遵守）
- MANIFEST title：优先用 theme 精炼短标题。"""

_FILE_INSTRUCTIONS = """\
一个非空主文件放在 `outputs/`。`outputs/MANIFEST.json` 必须是这一份，字段名不能改：
{"status":"success","title":"文件名称","artifacts":[{"role":"main","path":"outputs/<文件名>","mime":"<mime>"}]}"""

_MIME_BY_SUFFIX: dict[str, str] = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".json": "application/json",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


@dataclass(frozen=True)
class OutputFormat:
    key: str
    label: str
    instructions: str
    extensions: tuple[str, ...]


@dataclass(frozen=True)
class Accepted:
    path: Path
    mime: str
    title: str | None


class FormatMismatch(Exception):
    pass


class NoOutput(Exception):
    pass


_PREFERRED_NAMES: dict[str, frozenset[str]] = {
    "mind_map": frozenset({"mindmap.md", "mindmap.markdown"}),
    "structured_notes": frozenset({"notes.json", "notes.md", "notes.markdown"}),
    "slides": frozenset({"deck.pptx"}),
}


_FORMATS: dict[str, OutputFormat] = {
    "mind_map": OutputFormat(
        key="mind_map",
        label="思维导图",
        instructions=_MIND_MAP_INSTRUCTIONS,
        extensions=(".md", ".markdown"),
    ),
    "structured_notes": OutputFormat(
        key="structured_notes",
        label="结构化笔记",
        instructions=_STRUCTURED_NOTES_INSTRUCTIONS,
        extensions=(".json", ".md", ".markdown"),
    ),
    "slides": OutputFormat(
        key="slides",
        label="PPT",
        instructions=_SLIDES_INSTRUCTIONS,
        extensions=(".pptx",),
    ),
    "file": OutputFormat(
        key="file",
        label="文件",
        instructions=_FILE_INSTRUCTIONS,
        extensions=(),
    ),
}


def get_format(key: str) -> OutputFormat:
    return _FORMATS[key]


def list_formats() -> list[OutputFormat]:
    return [_FORMATS[k] for k in ("mind_map", "structured_notes", "slides", "file")]


def accept_outputs(fmt: OutputFormat, outputs_dir: Path) -> Accepted:
    manifest = _load_manifest(outputs_dir)
    if manifest is not None:
        studio = _accept_studio_manifest(fmt, outputs_dir, manifest)
        if studio is not None:
            return studio
        named = _accept_named_file(fmt, outputs_dir, manifest)
        if named is not None:
            return named
    return _accept_fallback(fmt, outputs_dir)


def _load_manifest(outputs_dir: Path) -> dict | None:
    manifest_path = outputs_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _resolve_artifact_path(outputs_dir: Path, manifest_path: str) -> Path:
    if manifest_path.startswith("outputs/"):
        base = outputs_dir.parent
    else:
        base = outputs_dir
    resolved = (base / manifest_path).resolve()
    _ensure_under_outputs(outputs_dir, resolved)
    return resolved


def _ensure_under_outputs(outputs_dir: Path, path: Path) -> None:
    outputs_resolved = outputs_dir.resolve()
    try:
        path.relative_to(outputs_resolved)
    except ValueError as exc:
        raise FormatMismatch from exc


def _ensure_valid_main_file(fmt: OutputFormat, path: Path) -> None:
    if not path.is_file():
        raise FormatMismatch
    if path.stat().st_size == 0:
        raise FormatMismatch
    if fmt.extensions and path.suffix not in fmt.extensions:
        raise FormatMismatch


def _studio_main(data: dict) -> dict | None:
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    for item in artifacts:
        if isinstance(item, dict) and item.get("role") == "main":
            return item
    return None


def _manifest_title(data: dict) -> str | None:
    title = data.get("title")
    if isinstance(title, str):
        return title
    return None


def _accept_studio_manifest(fmt: OutputFormat, outputs_dir: Path, data: dict) -> Accepted | None:
    """Accept the studio manifest. None means this is not that schema."""
    main = _studio_main(data)
    if main is None:
        return None
    if data.get("status") != "success":
        raise FormatMismatch
    path_str = main.get("path")
    if not isinstance(path_str, str) or not path_str:
        return None
    path = _resolve_artifact_path(outputs_dir, path_str)
    _ensure_valid_main_file(fmt, path)
    mime = main.get("mime")
    if not isinstance(mime, str) or not mime:
        mime = _guess_mime(path)
    return Accepted(path=path, mime=mime, title=_manifest_title(data))


def _named_file(data: dict) -> str | None:
    for key in ("main_file", "path", "file"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _accept_named_file(fmt: OutputFormat, outputs_dir: Path, data: dict) -> Accepted | None:
    raw = _named_file(data)
    if raw is None:
        return None
    path = _resolve_artifact_path(outputs_dir, raw)
    try:
        _ensure_valid_main_file(fmt, path)
    except FormatMismatch:
        return None
    mime = data.get("main_file_mime")
    if not isinstance(mime, str) or not mime:
        mime = data.get("mime")
    if not isinstance(mime, str) or not mime:
        mime = _guess_mime(path)
    return Accepted(path=path, mime=mime, title=_manifest_title(data))


def _accept_fallback(fmt: OutputFormat, outputs_dir: Path) -> Accepted:
    candidates: list[Path] = []
    for entry in outputs_dir.iterdir():
        if entry.name == "MANIFEST.json":
            continue
        if not entry.is_file():
            continue
        if entry.stat().st_size == 0:
            continue
        if fmt.extensions and entry.suffix not in fmt.extensions:
            continue
        candidates.append(entry)
    if len(candidates) == 1:
        path = candidates[0]
    else:
        preferred = _PREFERRED_NAMES.get(fmt.key, frozenset())
        named = [item for item in candidates if item.name in preferred]
        if len(named) != 1:
            raise NoOutput
        path = named[0]
    path = path.resolve()
    _ensure_under_outputs(outputs_dir, path)
    return Accepted(path=path, mime=_guess_mime(path), title=None)


def _guess_mime(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix, "application/octet-stream")
