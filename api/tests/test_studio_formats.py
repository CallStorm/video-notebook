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


def test_mind_map_instructions_treat_topic_as_focus_axis():
    instructions = get_format("mind_map").instructions
    assert "topic" in instructions
    assert "focus_mode" in instructions
    assert "extra_constraints" in instructions
    assert "action" in instructions
    assert "outline" in instructions
    assert "本次主题硬约束" in instructions
    assert "必要前提" in instructions
    assert "禁止按视频/文档章节目录做全覆盖式导图" in instructions



def test_structured_notes_json_manifest_accepted(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    payload = b'{"theme":"t","concepts":[],"points":[],"evidence":[],"takeaways":[]}'
    _write(outputs, "notes.json", payload)
    (outputs / "MANIFEST.json").write_text(
        json.dumps(
            {
                "status": "success",
                "title": "笔记",
                "artifacts": [
                    {"role": "main", "path": "outputs/notes.json", "mime": "application/json"}
                ],
            }
        ),
        encoding="utf-8",
    )
    accepted = accept_outputs(get_format("structured_notes"), outputs)
    assert accepted.title == "笔记"
    assert accepted.path.name == "notes.json"
    assert accepted.mime == "application/json"


def test_structured_notes_instructions_cover_schema():
    instructions = get_format("structured_notes").instructions
    assert "notes.json" in instructions
    assert "concepts" in instructions
    assert "takeaways" in instructions
    assert "focus" in instructions

def _reading_page(theme: str = "先核对原句，再决定信不信。") -> dict:
    return {
        "title": "如何核对",
        "theme": theme,
        "lede": "把散落的要点收成一条能读完的线。",
        "sections": [
            {
                "id": "s1",
                "title": "回到原句",
                "summary": "先听说话人自己怎么说。",
                "steps": [
                    {
                        "title": "点开时间",
                        "body": "原句比转述更值得先听一遍。",
                        "time": "12:04",
                        "video_id": 3,
                        "quote": "你得回到原句。",
                    }
                ],
                "diagram": {
                    "kind": "flow",
                    "nodes": [
                        {"label": "原句", "detail": "字幕里的话"},
                        {"label": "判断", "detail": "撑不撑得住"},
                    ],
                },
            }
        ],
        "closing": "核对完再写自己的结论。",
    }


def _write_reading(outputs: Path, payload: object) -> None:
    _write(outputs, "page.json", json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    (outputs / "MANIFEST.json").write_text(
        json.dumps(
            {
                "status": "success",
                "title": "如何核对",
                "artifacts": [
                    {"role": "main", "path": "outputs/page.json", "mime": "application/json"}
                ],
            }
        ),
        encoding="utf-8",
    )


def test_reading_page_json_manifest_accepted(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write_reading(outputs, _reading_page())
    accepted = accept_outputs(get_format("reading_page"), outputs)
    assert accepted.title == "如何核对"
    assert accepted.path.name == "page.json"
    assert accepted.mime == "application/json"


def test_reading_page_rejects_html_and_flat_json(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write(outputs, "page.json", b"<!DOCTYPE html><html></html>")
    (outputs / "MANIFEST.json").write_text(
        json.dumps(
            {
                "status": "success",
                "artifacts": [{"role": "main", "path": "outputs/page.json", "mime": "text/html"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FormatMismatch):
        accept_outputs(get_format("reading_page"), outputs)

    bad = _reading_page()
    bad["sections"][0]["steps"] = [{"title": "只有标题"}]
    _write_reading(outputs, bad)
    with pytest.raises(FormatMismatch):
        accept_outputs(get_format("reading_page"), outputs)

    timed = _reading_page()
    timed["sections"][0]["steps"][0]["time"] = "大约五分钟"
    _write_reading(outputs, timed)
    with pytest.raises(FormatMismatch):
        accept_outputs(get_format("reading_page"), outputs)


def test_reading_page_instructions_ask_for_regrouping():
    instructions = get_format("reading_page").instructions
    assert "page.json" in instructions
    assert "theme" in instructions
    assert "禁止一条要点一个 section" in instructions
    assert "不要写 HTML" in instructions
    assert "callout" in instructions
    assert "cards" in instructions
    assert "lanes" in instructions
    assert "contrast" in instructions
    for kind in ("flow", "compare", "sequence"):
        assert kind in instructions


def _illustrated_page() -> dict:
    return {
        "title": "先稳住，再换气",
        "kicker": "技术纠错",
        "theme": "问题往往不在动作本身，而在位置还没稳就急着做下一步。",
        "lede": "先判断问题从哪来，再把位置做对，最后才把动作接回去。",
        "sections": [
            {
                "id": "s1",
                "title": "先判断问题从哪来",
                "summary": "看起来急，根子多半在位置。",
                "prose": ["如果一上来就改节奏，动作会越改越乱。先看位置是不是还没稳。"],
                "callout": {
                    "tone": "warn",
                    "label": "注意",
                    "body": "急着做下一步时，前面的位置会跟着散。先修位置，才不容易反复。",
                },
            },
            {
                "title": "位置要找的感觉",
                "summary": "用一条短流程记住顺序。",
                "diagram": {
                    "kind": "flow",
                    "caption": "稳定之后，最后一步才是动作本身。",
                    "nodes": [
                        {"label": "准备", "detail": "视线放下"},
                        {"label": "走平", "detail": "身体在一条线上"},
                        {"label": "先送重心"},
                        "再做动作",
                    ],
                },
                "steps": [
                    {
                        "title": "先找位置",
                        "body": "不要先把力气用在最后一步。位置平了，后面的动作才会短。",
                        "time": "02:14",
                        "video_id": 7,
                        "quote": "你先把身体放平，气自然就在后面。",
                    },
                    {
                        "title": "重心跟上",
                        "body": "手走完的时候，重心不要晚半拍。",
                        "time": "05:37",
                        "video_id": "7",
                    },
                ],
            },
            {
                "title": "动作再接上去",
                "summary": "这是一个短动作。",
                "prose": "接上去之前，先看三条线是不是还在。",
                "diagram": {
                    "kind": "sequence",
                    "row_header": "阶段",
                    "lanes": ["头", "手", "髋"],
                    "rows": [
                        {
                            "label": "准备",
                            "cells": [
                                {"lane": "头", "text": "视线向下"},
                                {"lane": "髋", "text": "保持走平"},
                            ],
                        },
                        {
                            "label": "划水",
                            "cells": [
                                {"lane": "手", "text": "手走完"},
                                {"lane": "髋", "text": "髋跟上"},
                            ],
                        },
                        {
                            "label": "换气",
                            "cells": [
                                {"lane": "头", "text": "短抬即回"},
                                {"lane": "髋", "text": "不要跟着抬"},
                            ],
                        },
                    ],
                },
                "cards": [
                    {"title": "幅度", "body": "只够完成这一下，不必把整个位置抬高。"},
                    {"title": "回落", "body": "做完立刻回到原来的线上。"},
                ],
            },
            {
                "title": "常见对错对照",
                "summary": "把看起来像在做、其实在找的情况分开。",
                "diagram": {
                    "kind": "compare",
                    "tone": "contrast",
                    "columns": ["容易做错的", "更稳的做法"],
                    "nodes": [
                        {"label": "一下来就找结果", "detail": "先走平，稳了再做"},
                        {"label": "做的时候腰跟着抬", "detail": "只动该动的部分"},
                    ],
                },
                "callout": {"label": "要点", "body": "能跳回原片的地方，优先看位置是不是先平。"},
            },
        ],
        "closing": "先把位置走稳，后面的动作就会变短。",
    }


def _legacy_diagram_page() -> dict:
    page = _reading_page()
    page["sections"].append(
        {
            "title": "旧顺序",
            "steps": [{"body": "旧页面可以只给一串节点。"}],
            "diagram": {"kind": "sequence", "nodes": ["听完", {"label": "再判断", "detail": "回到原句"}]},
        }
    )
    page["sections"].append(
        {
            "title": "旧对照",
            "steps": [{"body": "对照仍然是左右两格，不另起一种图。"}],
            "diagram": {
                "kind": "compare",
                "nodes": [
                    {"label": "转述", "detail": "先放一放"},
                    {"label": "原句", "detail": "先听这一句"},
                ],
            },
        }
    )
    return page


def test_reading_page_accepts_legacy_diagrams_and_illustrated_blocks(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    _write_reading(outputs, _legacy_diagram_page())
    accepted = accept_outputs(get_format("reading_page"), outputs)
    assert accepted.path.name == "page.json"

    _write_reading(outputs, _illustrated_page())
    accepted = accept_outputs(get_format("reading_page"), outputs)
    assert accepted.title == "如何核对"
    assert accepted.mime == "application/json"


def test_reading_page_rejects_html_markup_and_invalid_blocks(tmp_path: Path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    def reject(payload: dict) -> None:
        _write_reading(outputs, payload)
        with pytest.raises(FormatMismatch):
            accept_outputs(get_format("reading_page"), outputs)

    html_lede = _reading_page()
    html_lede["lede"] = "<p>先看原句</p>"
    reject(html_lede)

    html_prose = _reading_page()
    html_prose["sections"][0]["prose"] = "<div>急着改节奏</div>"
    reject(html_prose)

    html_step = _reading_page()
    html_step["sections"][0]["steps"][0]["body"] = "看完再决定<br/>不要跳过"
    reject(html_step)

    empty = _reading_page()
    empty["sections"] = [{"title": "只有标题"}]
    reject(empty)

    bad_columns = _illustrated_page()
    bad_columns["sections"][3]["diagram"]["columns"] = ["只有一列"]
    reject(bad_columns)

    bad_lane = _illustrated_page()
    bad_lane["sections"][2]["diagram"]["rows"][0]["cells"][0]["lane"] = "脚"
    reject(bad_lane)

    duplicate_lane = _illustrated_page()
    duplicate_lane["sections"][2]["diagram"]["rows"][1]["cells"] = [
        {"lane": "手", "text": "第一次"},
        {"lane": "手", "text": "第二次"},
    ]
    reject(duplicate_lane)

    one_card = _illustrated_page()
    one_card["sections"][2]["cards"] = [{"title": "幅度", "body": "只够一下。"}]
    reject(one_card)

    missing_callout = _illustrated_page()
    missing_callout["sections"][0]["callout"] = {"tone": "warn", "label": "注意"}
    reject(missing_callout)

    bad_tone = _illustrated_page()
    bad_tone["sections"][0]["callout"]["tone"] = "danger"
    reject(bad_tone)

    long_prose = _reading_page()
    long_prose["sections"][0]["prose"] = ["一", "二", "三", "四"]
    reject(long_prose)

    extra_flow = _illustrated_page()
    extra_flow["sections"].append(
        {
            "title": "再来一条流程",
            "diagram": {
                "kind": "flow",
                "nodes": [{"label": "甲"}, {"label": "乙"}],
            },
        }
    )
    reject(extra_flow)

    three_flows = _reading_page()
    three_flows["sections"] = [
        {
            "title": f"流程 {index}",
            "diagram": {"kind": "flow", "nodes": ["甲", "乙", "丙"]},
        }
        for index in range(3)
    ]
    reject(three_flows)

    many_callouts = {
        "theme": "提醒太多就不是一篇短文。",
        "sections": [
            {
                "title": f"提醒 {index}",
                "callout": {"tone": "note", "body": "这一条就够了。"},
            }
            for index in range(4)
        ],
    }
    reject(many_callouts)

    too_many_sections = {
        "theme": "组数不该跟着要点条数走。",
        "sections": [
            {"title": f"第 {index} 组", "prose": "合并之后不该拆成这么多组。"}
            for index in range(9)
        ],
    }
    reject(too_many_sections)


def test_empty_pptx_zip_is_format_mismatch(tmp_path: Path):
    import io
    import zipfile

    outputs = tmp_path / "outputs"
    outputs.mkdir()
    buf = io.BytesIO()
    xml = (
        "<?xml version='1.0'?>"
        "<p:presentation xmlns:p='http://schemas.openxmlformats.org/presentationml/2006/main'>"
        "<p:sldIdLst />"
        "</p:presentation>"
    )
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ppt/presentation.xml", xml)
    _write(outputs, "deck.pptx", buf.getvalue())
    with pytest.raises(FormatMismatch):
        accept_outputs(get_format("slides"), outputs)
