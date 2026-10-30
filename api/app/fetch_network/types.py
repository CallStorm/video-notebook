from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PlatformKey = Literal["youtube", "bilibili"]
PLATFORMS: tuple[PlatformKey, ...] = ("youtube", "bilibili")


@dataclass(frozen=True)
class ResolvedNetwork:
    platform: PlatformKey | None
    cookiefile: Path | None
    proxy: str | None
