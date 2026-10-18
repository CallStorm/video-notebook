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


def test_fallback_symlink_outside_outputs_is_format_mismatch(tmp_path: Path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"secret\n")
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "leak").symlink_to(outside)
    with pytest.raises(FormatMismatch):
        accept_outputs(get_format("file"), outputs)


def test_skill_manifest_still_accepts_pptx(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write(outputs, "deck.pptx", b"PK pptx")
    _write(outputs, "notes.md", b"side note")
    (outputs / "MANIFEST.json").write_text(
        json.dumps(
            {
                "product_dimension": "presentation",
                "main_file": "deck.pptx",
                "main_file_mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "slides": [{"index": 1, "title": "封面"}],
            }
        ),
        encoding="utf-8",
    )
    accepted = accept_outputs(get_format("slides"), outputs)
    assert accepted.path.name == "deck.pptx"
    assert accepted.mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_preferred_pptx_wins_when_manifest_has_no_main_name(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write(outputs, "deck.pptx", b"PK pptx")
    _write(outputs, "extra.pptx", b"PK extra")
    (outputs / "MANIFEST.json").write_text(
        json.dumps({"theme": "Midnight", "slides": []}),
        encoding="utf-8",
    )
    accepted = accept_outputs(get_format("slides"), outputs)
    assert accepted.path.name == "deck.pptx"


def test_studio_manifest_wrong_file_does_not_fall_back(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write(outputs, "notes.txt", b"hello")
    _write(outputs, "deck.pptx", b"PK pptx")
    (outputs / "MANIFEST.json").write_text(
        json.dumps(
            {
                "status": "success",
                "artifacts": [{"role": "main", "path": "outputs/notes.txt", "mime": "text/plain"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FormatMismatch):
        accept_outputs(get_format("slides"), outputs)


def test_damaged_manifest_does_not_count_as_fallback_candidate(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "MANIFEST.json").write_text("{not json", encoding="utf-8")
    _write(outputs, "payload.bin", b"data")
    accepted = accept_outputs(get_format("file"), outputs)
    assert accepted.path.name == "payload.bin"
