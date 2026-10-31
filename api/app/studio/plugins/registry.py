"""Discover Studio plugins from disk (Claude-Code-like plugin folders)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_PLUGINS_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PluginSpec:
    id: str
    name: str
    icon: str | None
    version: str
    enabled_by_default: bool
    timeout_seconds: int
    skill_name: str | None
    skill_dir: Path | None
    extensions: tuple[str, ...]
    preferred_names: frozenset[str]
    form: list[dict]
    system_prompt: str
    instructions: str
    root: Path

    @property
    def format_key(self) -> str:
        return self.id


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _load_one(plugin_dir: Path) -> PluginSpec | None:
    meta_path = plugin_dir / "plugin.json"
    if not meta_path.is_file():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    plugin_id = data.get("id")
    if not isinstance(plugin_id, str) or not plugin_id.strip():
        return None
    plugin_id = plugin_id.strip()
    if plugin_id != plugin_dir.name:
        # Directory name is the source of truth for discovery.
        plugin_id = plugin_dir.name

    skill_name = data.get("skill")
    skill_dir: Path | None = None
    if isinstance(skill_name, str) and skill_name.strip():
        skill_name = skill_name.strip()
        candidate = plugin_dir / "skill" / skill_name
        if candidate.is_dir():
            skill_dir = candidate
        else:
            skill_name = skill_name
            skill_dir = None
    else:
        skill_name = None

    extensions_raw = data.get("extensions") or []
    extensions = tuple(
        str(item) for item in extensions_raw if isinstance(item, str) and item.startswith(".")
    )
    preferred_raw = data.get("preferred_names") or []
    preferred = frozenset(
        str(item) for item in preferred_raw if isinstance(item, str) and item.strip()
    )
    form = data.get("form") if isinstance(data.get("form"), list) else []
    icon = data.get("icon")
    if icon is not None and not isinstance(icon, str):
        icon = None
    timeout = data.get("timeout_seconds", 600)
    try:
        timeout_seconds = max(30, int(timeout))
    except (TypeError, ValueError):
        timeout_seconds = 600

    return PluginSpec(
        id=plugin_id,
        name=str(data.get("name") or plugin_id),
        icon=icon,
        version=str(data.get("version") or "0.0.0"),
        enabled_by_default=bool(data.get("enabled_by_default", False)),
        timeout_seconds=timeout_seconds,
        skill_name=skill_name,
        skill_dir=skill_dir,
        extensions=extensions,
        preferred_names=preferred,
        form=list(form),
        system_prompt=_read_text(plugin_dir / "system.md"),
        instructions=_read_text(plugin_dir / "instructions.md"),
        root=plugin_dir,
    )


@lru_cache(maxsize=1)
def _discover() -> dict[str, PluginSpec]:
    found: dict[str, PluginSpec] = {}
    if not _PLUGINS_ROOT.is_dir():
        return found
    for child in sorted(_PLUGINS_ROOT.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_") or child.name.startswith("."):
            continue
        if child.name == "__pycache__":
            continue
        plugin = _load_one(child)
        if plugin is None:
            continue
        found[plugin.id] = plugin
    return found


def reload_plugins() -> None:
    """Clear cache (tests / hot reload after adding a plugin folder)."""
    _discover.cache_clear()


def list_plugins() -> list[PluginSpec]:
    return list(_discover().values())


def get_plugin(plugin_id: str) -> PluginSpec:
    plugins = _discover()
    try:
        return plugins[plugin_id]
    except KeyError as exc:
        known = ", ".join(sorted(plugins)) or "(none)"
        raise KeyError(f"unknown studio plugin {plugin_id!r}; known: {known}") from exc


def plugins_root() -> Path:
    return _PLUGINS_ROOT
