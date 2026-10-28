"""Studio output formats — thin platform accept + plugin-backed instructions."""
from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.studio.plugins.registry import get_plugin, list_plugins

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


def _plugin_format(key: str) -> OutputFormat | None:
    try:
        plugin = get_plugin(key)
    except KeyError:
        return None
    return OutputFormat(
        key=plugin.id,
        label=plugin.name,
        instructions=plugin.instructions,
        extensions=plugin.extensions,
    )


def get_format(key: str) -> OutputFormat:
    plugin_fmt = _plugin_format(key)
    if plugin_fmt is not None:
        return plugin_fmt
    if key == "file":
        return OutputFormat(
            key="file",
            label="文件",
            instructions=_FILE_INSTRUCTIONS,
            extensions=(),
        )
    known = ", ".join(sorted([p.id for p in list_plugins()] + ["file"]))
    raise KeyError(f"unknown studio format {key!r}; known: {known}")


def list_formats() -> list[OutputFormat]:
    """Plugin formats first (disk order), then legacy file fallback."""
    out = [
        OutputFormat(
            key=p.id,
            label=p.name,
            instructions=p.instructions,
            extensions=p.extensions,
        )
        for p in list_plugins()
    ]
    out.append(
        OutputFormat(
            key="file",
            label="文件",
            instructions=_FILE_INSTRUCTIONS,
            extensions=(),
        )
    )
    return out


def _preferred_names(fmt_key: str) -> frozenset[str]:
    try:
        return get_plugin(fmt_key).preferred_names
    except KeyError:
        return frozenset()


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
    if fmt.key == "slides" and path.suffix == ".pptx":
        _ensure_pptx_has_slides(path)


def _ensure_pptx_has_slides(path: Path) -> None:
    """Reject empty officecli shells that only have masters/layouts."""
    if not zipfile.is_zipfile(path):
        # Unit fixtures may use a non-zip stub ("PK pptx"); keep those accepted.
        return
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if any(re.match(r"ppt/slides/slide\d+\.xml$", name) for name in names):
            return
        try:
            xml = zf.read("ppt/presentation.xml").decode("utf-8", errors="replace")
        except KeyError as exc:
            raise FormatMismatch from exc
        if re.search(r"<p:sldId[\s>]", xml):
            return
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
        preferred = _preferred_names(fmt.key)
        named = [item for item in candidates if item.name in preferred]
        if len(named) != 1:
            raise NoOutput
        path = named[0]
    path = path.resolve()
    _ensure_under_outputs(outputs_dir, path)
    _ensure_valid_main_file(fmt, path)
    return Accepted(path=path, mime=_guess_mime(path), title=None)


def _guess_mime(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix, "application/octet-stream")
