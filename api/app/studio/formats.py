from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_MIND_MAP_INSTRUCTIONS = """\
- 主文件是 markmap 用的 Markdown：`#` 为中心主题，子节点为缩进的无序列表。
- 路径 `outputs/mindmap.md`。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改：
  {"status":"success","title":"导图名称","artifacts":[{"role":"main","path":"outputs/mindmap.md","mime":"text/markdown"}]}"""

_SLIDES_INSTRUCTIONS = """\
- 主文件是 pptx，路径 `outputs/deck.pptx`。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改，也不要写成技能自己的清单：
  {"status":"success","title":"演示标题","artifacts":[{"role":"main","path":"outputs/deck.pptx","mime":"application/vnd.openxmlformats-officedocument.presentationml.presentation"}]}"""

_FILE_INSTRUCTIONS = """\
一个非空主文件放在 `outputs/`。`outputs/MANIFEST.json` 必须是这一份，字段名不能改：
{"status":"success","title":"文件名称","artifacts":[{"role":"main","path":"outputs/<文件名>","mime":"<mime>"}]}"""

_MIME_BY_SUFFIX: dict[str, str] = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
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
    "slides": frozenset({"deck.pptx"}),
}


_FORMATS: dict[str, OutputFormat] = {
    "mind_map": OutputFormat(
        key="mind_map",
        label="思维导图",
        instructions=_MIND_MAP_INSTRUCTIONS,
        extensions=(".md", ".markdown"),
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
    return [_FORMATS[k] for k in ("mind_map", "slides", "file")]


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
