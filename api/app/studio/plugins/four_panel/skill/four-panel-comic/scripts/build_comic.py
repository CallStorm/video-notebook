"""Deterministic four-panel comic builder from Studio form fields."""
from __future__ import annotations

import json
import re
from pathlib import Path


LABELS = ("误区", "冲突", "例子", "结论")


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


def _clip(text: str, max_len: int) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _parse_brief(brief: str) -> tuple[str, list[dict[str, str]], list[str]]:
    """Return theme, points[{text,evidence,example}], conclusions."""
    theme = ""
    points: list[dict[str, str]] = []
    conclusions: list[str] = []
    section = "none"
    current: dict[str, str] | None = None

    for raw in (brief or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("主题：") or line.startswith("主题:"):
            theme = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            section = "none"
            continue
        if line in {"要点：", "要点:"} or line.startswith("要点：") or line.startswith("要点:"):
            if line in {"要点：", "要点:"} or line[2:].strip() in {":", "：", ""}:
                section = "points"
                continue
        if line in {"结论：", "结论:"} or line.startswith("结论：") or line.startswith("结论:"):
            if current is not None:
                points.append(current)
                current = None
            section = "conclusions"
            rest = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            if rest and rest not in {":", "："}:
                conclusions.append(rest)
            continue
        if section == "points":
            m = re.match(r"^(\d+)[\.、\)]\s*(.+)$", line)
            if m:
                if current is not None:
                    points.append(current)
                current = {"text": m.group(2).strip(), "evidence": "", "example": ""}
                continue
            if current is None:
                continue
            if line.startswith("原句：") or line.startswith("原句:") or line.startswith("原句摘要："):
                current["evidence"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("例：") or line.startswith("例:"):
                current["example"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            else:
                # continuation of claim
                current["text"] = (current["text"] + " " + line).strip()
            continue
        if section == "conclusions":
            m = re.match(r"^(\d+)[\.、\)]\s*(.+)$", line)
            conclusions.append(m.group(2).strip() if m else line)
    if current is not None:
        points.append(current)
    return theme, points, conclusions


def build_comic_from_fields(fields: list) -> dict:
    fmap = _field_map(fields)
    title = (fmap.get("title") or "").strip()
    brief = (fmap.get("brief") or "").strip()
    theme, points, conclusions = _parse_brief(brief)
    if not title:
        title = theme or (points[0]["text"] if points else "知识四格漫")
    title = _clip(title, 24)

    primary = points[0] if points else {"text": brief or title, "evidence": "", "example": ""}
    claim = primary.get("text") or title
    evidence = primary.get("evidence") or ""
    example = primary.get("example") or evidence or claim
    conclusion = conclusions[0] if conclusions else f"记住：{_clip(claim, 40)}"

    # Fold extra points lightly into 结论 caption if present
    if len(points) > 1:
        extras = "；".join(_clip(p["text"], 28) for p in points[1:3])
        if extras:
            conclusion = _clip(f"{conclusion}（相关：{extras}）", 120)

    panels = [
        {
            "label": "误区",
            "caption": _clip(f"常见误区：以为不用管「{_clip(claim, 36)}」也能过关。", 100),
            "dialogue": "差不多就行了吧？",
            "scene": "想当然、省一步",
        },
        {
            "label": "冲突",
            "caption": _clip(claim, 100),
            "dialogue": _clip(evidence, 60) if evidence else "等等，关键不在这里…",
            "scene": "被现实打脸 / 对照原句",
        },
        {
            "label": "例子",
            "caption": _clip(example, 100),
            "dialogue": "比如这样落地…",
            "scene": "生活/工作小剧场",
        },
        {
            "label": "结论",
            "caption": _clip(conclusion, 100),
            "dialogue": "下次按这个做。",
            "scene": "可执行收获",
        },
    ]
    # Ensure labels exact
    for i, label in enumerate(LABELS):
        panels[i]["label"] = label
    return {"title": title, "panels": panels}


def write_comic_outputs(outputs_dir: Path, fields: list) -> Path:
    """Write comic.json + MANIFEST.json under outputs_dir; return comic path."""
    outputs_dir.mkdir(parents=True, exist_ok=True)
    comic = build_comic_from_fields(fields)
    comic_path = outputs_dir / "comic.json"
    comic_path.write_text(json.dumps(comic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "status": "success",
        "title": comic["title"],
        "artifacts": [
            {
                "role": "main",
                "path": "outputs/comic.json",
                "mime": "application/json",
            }
        ],
    }
    (outputs_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return comic_path


def main() -> None:
    import sys

    # Usage: build_comic.py <workspace_root>
    work = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    inputs = work / "inputs.json"
    data = json.loads(inputs.read_text(encoding="utf-8")) if inputs.is_file() else {}
    fields = data.get("fields") if isinstance(data, dict) else []
    if not isinstance(fields, list):
        fields = []
    write_comic_outputs(work / "outputs", fields)
    print("ok")


if __name__ == "__main__":
    main()
