"""封面样式：名称驱动确定性 + token 编码。"""
from __future__ import annotations

from app.services.cover_generate import (
    encode_cover_token,
    style_from_title,
    _parse_style,
    match_theme,
)


def test_style_from_title_stable():
    a = style_from_title("美食探店")
    b = style_from_title("美食探店")
    assert a == b
    assert a["pattern"] in {"orbs", "waves", "mesh", "beams", "rings", "grid"}
    assert a["layout"] in {"accent", "split", "badge", "bands", "frame", "hero"}
    assert a["motif"] in {"ev", "tech", "finance", "food", "nature", "creative", "study", "abstract"}
    assert a["b"].startswith("#")


def test_different_names_differ():
    styles = [
        style_from_title(t)
        for t in ("美食探店", "AI编程笔记", "自然旅行", "创意设计", "职场管理", "随便起个名字甲")
    ]
    fingerprints = {(s["layout"], s["motif"], s["pattern"], s["a"], s["b"]) for s in styles}
    assert len(fingerprints) >= 4


def test_keyword_semantic_colors():
    food = style_from_title("周末美食清单")
    tech = style_from_title("AI编程实战")
    nature = style_from_title("自然旅行")
    creative = style_from_title("创意设计")
    ev = style_from_title("新能源汽车")
    econ = style_from_title("经济")
    assert food["b"].upper() in {"#EA580C", "#D97706"}
    assert food["motif"] == "food"
    assert tech["b"].upper() in {"#2563EB", "#4F46E5", "#6366F1", "#0D9488", "#0891B2"}
    assert tech["motif"] == "tech"
    assert nature["b"].upper() in {"#059669", "#65A30D"}
    assert nature["motif"] == "nature"
    assert creative["b"].upper() in {"#7C3AED", "#9333EA"}
    assert creative["motif"] == "creative"
    assert ev["motif"] == "ev"
    assert econ["motif"] == "finance"
    # 新能源 vs 经济：布局或主色必须肉眼可分
    assert (ev["layout"], ev["b"]) != (econ["layout"], econ["b"]) or ev["motif"] != econ["motif"]


def test_match_theme_ev_and_finance():
    assert match_theme("新能源汽车") is not None
    assert match_theme("新能源汽车")[1] == "ev"
    assert match_theme("经济")[1] == "finance"


def test_encode_token_roundtrip_shape():
    style = style_from_title("学习笔记")
    token = encode_cover_token(style)
    assert token.startswith("gen:v3:")
    parts = token.split(":")
    assert len(parts) == 10  # gen / v3 / layout / motif / pattern / a / b / c / ink / mist


def test_parse_style_fallback():
    fb = style_from_title("兜底")
    got = _parse_style("not json", fallback=fb)
    assert got == fb
    raw = (
        '{"layout":"hero","motif":"tech","pattern":"waves","a":"#112233","b":"#445566",'
        '"c":"#778899","ink":"#FFFFFF","mist":"#AABBCC"}'
    )
    got2 = _parse_style(raw, fallback=fb)
    assert got2["layout"] == "hero"
    assert got2["motif"] == "tech"
    assert got2["pattern"] == "waves"
    assert got2["a"] == "#112233"


def test_style_label_empty_no_cover_text():
    """封面不印字：样式 token / label 不携带展示文案。"""
    for title in ("新能源汽车", "经济", "财经", "美食探店", "随便名字"):
        style = style_from_title(title)
        assert style.get("label", "") == ""
        token = encode_cover_token(style)
        # token 本身也不应含中文标题
        assert title not in token
        assert "·" not in token
