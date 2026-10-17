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
