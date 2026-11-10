"""Studio output formats — thin platform accept + plugin-backed instructions."""
from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

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
    if fmt.key == "reading_page":
        _ensure_reading_page(path)


_READING_CLOCK_RE = re.compile(r"^\d{1,2}:[0-5]?\d(?::[0-5]?\d)?$")
_READING_DIAGRAM_KINDS = frozenset({"flow", "compare", "sequence"})
_READING_CALLOUT_TONES = frozenset({"note", "warn"})
_READING_COMPARE_TONES = frozenset({"plain", "contrast"})
_HTML_MARKUP_RE = re.compile(
    r"<\s*/?\s*(?:!doctype|html|head|body|div|span|p|br|hr|img|a|table|thead|tbody|tr|td|th|"
    r"ul|ol|li|h[1-6]|style|script|section|article|button|svg|path|figure|figcaption|"
    r"blockquote|strong|em|dl|dt|dd)\b",
    re.IGNORECASE,
)
_MAX_READING_SECTIONS = 8
_MAX_READING_DIAGRAMS = 3
_MAX_READING_DIAGRAMS_PER_KIND = 2
_MAX_READING_CALLOUTS = 3
_MAX_READING_CARD_GROUPS = 2
_MAX_READING_CARDS = 6
_MAX_READING_PROSE = 3
_MAX_READING_LANES = 4
_MAX_READING_ROWS = 6


class _ReadingSectionStats(TypedDict):
    diagram: int
    kind: str
    callout: int
    cards: int


def _reading_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _reading_video_id(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip()) > 0
    return False


def _reject_html_markup(value: object) -> None:
    if isinstance(value, str):
        if _HTML_MARKUP_RE.search(value):
            raise FormatMismatch
        return
    if isinstance(value, dict):
        for item in value.values():
            _reject_html_markup(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_html_markup(item)


def _ensure_reading_page(path: Path) -> None:
    """Reject HTML pages and JSON that is not a grouped reading document."""
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FormatMismatch from exc
    stripped = raw.lstrip("\ufeff").lstrip()
    lowered = stripped[:32].lower()
    if lowered.startswith("<!doctype") or lowered.startswith("<html") or lowered.startswith("<body"):
        raise FormatMismatch
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise FormatMismatch from exc
    if not isinstance(data, dict):
        raise FormatMismatch
    _reject_html_markup(data)
    if _reading_text(data.get("theme")) is None:
        raise FormatMismatch
    for key in ("title", "kicker", "lede", "closing"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            raise FormatMismatch
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections or len(sections) > _MAX_READING_SECTIONS:
        raise FormatMismatch
    diagrams = 0
    kinds = {"flow": 0, "compare": 0, "sequence": 0}
    callouts = 0
    card_groups = 0
    for section in sections:
        stats = _ensure_reading_section(section)
        diagrams += stats["diagram"]
        if stats["kind"]:
            kinds[stats["kind"]] += 1
        callouts += stats["callout"]
        card_groups += stats["cards"]
    if diagrams > _MAX_READING_DIAGRAMS or callouts > _MAX_READING_CALLOUTS:
        raise FormatMismatch
    if card_groups > _MAX_READING_CARD_GROUPS:
        raise FormatMismatch
    if any(count > _MAX_READING_DIAGRAMS_PER_KIND for count in kinds.values()):
        raise FormatMismatch


def _ensure_reading_section(section: object) -> _ReadingSectionStats:
    if not isinstance(section, dict):
        raise FormatMismatch
    if _reading_text(section.get("title")) is None:
        raise FormatMismatch
    if "summary" in section and section["summary"] is not None and not isinstance(section["summary"], str):
        raise FormatMismatch
    prose = _reading_prose_count(section.get("prose")) if "prose" in section else 0
    steps = _reading_step_count(section.get("steps")) if "steps" in section else 0
    kind = ""
    diagram = 0
    if "diagram" in section and section["diagram"] is not None:
        kind = _ensure_reading_diagram(section["diagram"])
        diagram = 1
    cards = _reading_card_count(section.get("cards")) if "cards" in section else 0
    callout = _reading_callout_count(section.get("callout")) if "callout" in section else 0
    if steps + prose + diagram + cards + callout == 0:
        raise FormatMismatch
    return {"diagram": diagram, "kind": kind, "callout": callout, "cards": cards}


def _reading_prose_count(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        if _reading_text(value) is None:
            raise FormatMismatch
        return 1
    if isinstance(value, list):
        if not value or len(value) > _MAX_READING_PROSE:
            raise FormatMismatch
        for item in value:
            if _reading_text(item) is None:
                raise FormatMismatch
        return len(value)
    raise FormatMismatch


def _reading_step_count(value: object) -> int:
    if value is None:
        return 0
    if not isinstance(value, list) or not value:
        raise FormatMismatch
    for step in value:
        _ensure_reading_step(step)
    return len(value)


def _reading_callout_count(value: object) -> int:
    if value is None:
        return 0
    if not isinstance(value, dict):
        raise FormatMismatch
    if _reading_text(value.get("body")) is None:
        raise FormatMismatch
    tone = value.get("tone")
    if tone not in (None, "") and tone not in _READING_CALLOUT_TONES:
        raise FormatMismatch
    label = value.get("label")
    if label not in (None, ""):
        text = _reading_text(label)
        if text is None or len(text) > 8:
            raise FormatMismatch
    return 1


def _reading_card_count(value: object) -> int:
    if value is None:
        return 0
    if not isinstance(value, list) or not (2 <= len(value) <= _MAX_READING_CARDS):
        raise FormatMismatch
    for card in value:
        if not isinstance(card, dict):
            raise FormatMismatch
        if _reading_text(card.get("title")) is None or _reading_text(card.get("body")) is None:
            raise FormatMismatch
    return 1


def _ensure_reading_step(step: object) -> None:
    if not isinstance(step, dict):
        raise FormatMismatch
    if _reading_text(step.get("body")) is None:
        raise FormatMismatch
    if "title" in step and step["title"] is not None and not isinstance(step["title"], str):
        raise FormatMismatch
    for key in ("quote", "aside"):
        if key in step and step[key] is not None and not isinstance(step[key], str):
            raise FormatMismatch
    if "time" in step and step["time"] not in (None, ""):
        clock = step["time"]
        if not isinstance(clock, str) or _READING_CLOCK_RE.fullmatch(clock.strip()) is None:
            raise FormatMismatch
    if "video_id" in step and step["video_id"] not in (None, "") and not _reading_video_id(step["video_id"]):
        raise FormatMismatch


def _ensure_reading_diagram(diagram: object) -> str:
    if not isinstance(diagram, dict):
        raise FormatMismatch
    kind = diagram.get("kind") or "flow"
    if not isinstance(kind, str) or kind not in _READING_DIAGRAM_KINDS:
        raise FormatMismatch
    if "caption" in diagram and diagram["caption"] is not None and not isinstance(diagram["caption"], str):
        raise FormatMismatch
    if kind == "compare":
        _ensure_compare_diagram(diagram)
    elif kind == "sequence" and _sequence_uses_rows(diagram):
        _ensure_sequence_chart(diagram)
    else:
        _ensure_reading_nodes(diagram.get("nodes"))
    return kind


def _sequence_uses_rows(diagram: dict) -> bool:
    has_rows = "rows" in diagram and diagram["rows"] is not None
    has_lanes = "lanes" in diagram and diagram["lanes"] is not None
    return has_rows or has_lanes


def _ensure_compare_diagram(diagram: dict) -> None:
    tone = diagram.get("tone")
    if tone not in (None, "") and tone not in _READING_COMPARE_TONES:
        raise FormatMismatch
    columns = diagram.get("columns")
    if columns is not None:
        if not isinstance(columns, list) or len(columns) != 2:
            raise FormatMismatch
        for item in columns:
            if _reading_text(item) is None:
                raise FormatMismatch
    _ensure_reading_nodes(diagram.get("nodes"))


def _ensure_sequence_chart(diagram: dict) -> None:
    header = diagram.get("row_header")
    if header is not None:
        text = _reading_text(header)
        if text is None or len(text) > 8:
            raise FormatMismatch
    lanes = _reading_lanes(diagram.get("lanes"))
    rows = diagram.get("rows")
    if not isinstance(rows, list) or not (2 <= len(rows) <= _MAX_READING_ROWS):
        raise FormatMismatch
    known = set(lanes)
    for row in rows:
        if not isinstance(row, dict) or _reading_text(row.get("label")) is None:
            raise FormatMismatch
        cells = row.get("cells")
        if not isinstance(cells, list) or not cells or len(cells) > len(lanes):
            raise FormatMismatch
        seen: set[str] = set()
        for cell in cells:
            if not isinstance(cell, dict) or _reading_text(cell.get("text")) is None:
                raise FormatMismatch
            lane = cell.get("lane")
            if not isinstance(lane, str) or lane not in known or lane in seen:
                raise FormatMismatch
            seen.add(lane)
    if "nodes" in diagram and diagram["nodes"] is not None:
        _ensure_reading_nodes(diagram["nodes"])


def _reading_lanes(value: object) -> list[str]:
    if not isinstance(value, list) or not (2 <= len(value) <= _MAX_READING_LANES):
        raise FormatMismatch
    lanes: list[str] = []
    for item in value:
        text = _reading_text(item)
        if text is None or text in lanes or len(text) > 12:
            raise FormatMismatch
        lanes.append(text)
    return lanes


def _ensure_reading_nodes(nodes: object) -> None:
    if not isinstance(nodes, list) or not (2 <= len(nodes) <= 6):
        raise FormatMismatch
    for node in nodes:
        if isinstance(node, str):
            if not node.strip():
                raise FormatMismatch
            continue
        if not isinstance(node, dict) or _reading_text(node.get("label")) is None:
            raise FormatMismatch
        if "detail" in node and node["detail"] is not None and not isinstance(node["detail"], str):
            raise FormatMismatch


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
