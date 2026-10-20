"""Locate ffmpeg/ffprobe for yt-dlp and subtitle helpers.

Interactive shells often have WinGet Links on PATH; Celery workers started
from Make/Cursor may not. Resolve explicitly and prepend to PATH.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_resolved_dir: Path | None = None


def _candidate_bins() -> list[Path]:
    from app.core.config import get_settings

    out: list[Path] = []
    configured = (get_settings().ffmpeg_location or "").strip()
    if configured:
        p = Path(configured)
        out.append(p if p.is_dir() else p.parent)

    which = shutil.which("ffmpeg")
    if which:
        out.append(Path(which).resolve().parent)

    home = Path.home()
    out.extend(
        [
            home / "AppData/Local/Microsoft/WinGet/Links",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Links",
            Path("C:/ffmpeg/bin"),
            home / "scoop/apps/ffmpeg/current/bin",
            Path("C:/ProgramData/chocolatey/bin"),
        ]
    )

    # WinGet package layout: .../Gyan.FFmpeg_.../ffmpeg-*-full_build/bin
    packages = home / "AppData/Local/Microsoft/WinGet/Packages"
    if packages.is_dir():
        for pkg in packages.glob("Gyan.FFmpeg*"):
            for bin_dir in pkg.glob("ffmpeg-*/bin"):
                out.append(bin_dir)

    return out


def resolve_ffmpeg_dir() -> Path | None:
    """Return directory containing ffmpeg.exe / ffmpeg, or None."""
    global _resolved_dir
    if _resolved_dir is not None:
        return _resolved_dir

    for directory in _candidate_bins():
        if not directory:
            continue
        try:
            directory = directory.resolve()
        except OSError:
            continue
        if not directory.is_dir():
            continue
        ffmpeg = directory / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if ffmpeg.is_file():
            _resolved_dir = directory
            logger.info("ffmpeg found at %s", ffmpeg)
            return _resolved_dir
    logger.warning("ffmpeg not found on PATH or known install locations")
    return None


def ensure_ffmpeg_on_path() -> Path | None:
    """Prepend ffmpeg bin dir to PATH for this process (idempotent)."""
    directory = resolve_ffmpeg_dir()
    if directory is None:
        return None
    dir_s = str(directory)
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if dir_s not in parts:
        os.environ["PATH"] = dir_s + os.pathsep + os.environ.get("PATH", "")
        logger.info("prepended ffmpeg dir to PATH: %s", dir_s)
    return directory


def ytdlp_ffmpeg_location() -> str | None:
    """Value for yt-dlp `ffmpeg_location` (directory or binary)."""
    directory = ensure_ffmpeg_on_path()
    return str(directory) if directory else None
