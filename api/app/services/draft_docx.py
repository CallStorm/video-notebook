"""把已完成的知识底稿写成一份 Word。

板块顺序固定为：主题、概念、要点、我的结论。
某一块没有内容就整节不写。
笔记本名是一级标题，下面有横线。四个板块是二级标题，只有序号，左边不加线。
要点是一张表，表头为要点、原句、例子。空的格子留空。时间和评论不写入。
有勾选时只导出勾选的要点，否则导出全部。
"""
from __future__ import annotations

import io
import re
from typing import Any

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

_FONT = "微软雅黑"
_LABEL = RGBColor(0x5A, 0x5A, 0x5A)
_INK = RGBColor(0x1C, 0x1C, 0x1C)
_SECTION_NUMERALS = "一二三四"


def draft_docx_filename(title: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n]+', " ", title or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()[:80]
    return f"{cleaned or '笔记本'}-底稿.docx"


def build_draft_docx(
    *,
    notebook_title: str,
    theme: str,
    concepts: list[dict[str, Any]],
    points: list[dict[str, Any]],
    conclusions: list[str],
) -> bytes:
    title = (notebook_title or "").strip() or "笔记本"
    doc = Document()
    _prepare_styles(doc)
    _add_title(doc, title)
    section_index = 0

    theme_text = (theme or "").strip()
    if theme_text:
        _add_section_heading(doc, section_index, "主题")
        section_index += 1
        _add_body(doc, theme_text, size=12)

    concept_rows = _concepts(concepts)
    if concept_rows:
        _add_section_heading(doc, section_index, "概念")
        section_index += 1
        _add_table(
            doc,
            ["概念", "释义"],
            concept_rows,
            widths=(Cm(3.2), Cm(13.2)),
        )

    point_rows = _points(points)
    if point_rows:
        _add_section_heading(doc, section_index, "要点")
        section_index += 1
        _add_point_table(doc, point_rows)

    conclusion_rows = _conclusions(conclusions)
    if conclusion_rows:
        _add_section_heading(doc, section_index, "我的结论")
        _add_table(
            doc,
            ["序号", "结论"],
            conclusion_rows,
            widths=(Cm(1.6), Cm(14.8)),
            center_first=True,
        )

    _add_page_number(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _concepts(concepts: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in concepts or []:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        if not term:
            continue
        rows.append([term, str(item.get("definition") or "").strip()])
    return rows


def _points(points: list[dict[str, Any]]) -> list[dict[str, str]]:
    usable = [item for item in points or [] if isinstance(item, dict)]
    checked = [item for item in usable if item.get("checked") and str(item.get("text") or "").strip()]
    chosen = checked or [item for item in usable if str(item.get("text") or "").strip()]
    rows: list[dict[str, str]] = []
    for item in chosen:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        rows.append(
            {
                "text": text,
                "evidence": str(item.get("evidence") or "").strip(),
                "example": str(item.get("example") or "").strip(),
            }
        )
    return rows


def _conclusions(conclusions: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in conclusions or []:
        text = str(item or "").strip()
        if text:
            rows.append([str(len(rows) + 1), text])
    return rows


def _prepare_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = _FONT
    normal.font.size = Pt(11)
    normal.font.color.rgb = _INK
    _east_asia(normal.element, _FONT)
    _drop_theme_color(normal.element)
    for name, size in (("Heading 1", 22), ("Heading 2", 14)):
        style = doc.styles[name]
        style.font.name = _FONT
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = _INK
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)
        _east_asia(style.element, _FONT)
        _drop_theme_color(style.element)


def _east_asia(element, font: str) -> None:
    props = element.get_or_add_rPr()
    fonts = props.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        props.append(fonts)
    fonts.set(qn("w:ascii"), font)
    fonts.set(qn("w:hAnsi"), font)
    fonts.set(qn("w:eastAsia"), font)


def _drop_theme_color(element) -> None:
    props = element.find(qn("w:rPr"))
    if props is None:
        return
    color = props.find(qn("w:color"))
    if color is None:
        return
    for key in list(color.attrib):
        if key.split("}")[-1].startswith("theme"):
            del color.attrib[key]


def _font(run, *, size: float, bold: bool = False, color: RGBColor | None = None) -> None:
    run.font.name = _FONT
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = color or _INK
    _east_asia(run._element, _FONT)
    _drop_theme_color(run._element)


def _paragraph_border(paragraph, *, edge: str, size: str, color: str) -> None:
    props = paragraph._p.get_or_add_pPr()
    borders = props.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        props.append(borders)
    border = OxmlElement(f"w:{edge}")
    border.set(qn("w:val"), "single")
    border.set(qn("w:sz"), size)
    border.set(qn("w:space"), "1")
    border.set(qn("w:color"), color)
    borders.append(border)


def _add_title(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph(style="Heading 1")
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(12)
    _paragraph_border(paragraph, edge="bottom", size="18", color="1C1C1C")
    _font(paragraph.add_run(text), size=22, bold=True)


def _add_section_heading(doc: Document, index: int, text: str) -> None:
    paragraph = doc.add_paragraph(style="Heading 2")
    paragraph.paragraph_format.space_before = Pt(16)
    paragraph.paragraph_format.space_after = Pt(8)
    _font(paragraph.add_run(f"{_SECTION_NUMERALS[index]}、{text}"), size=14, bold=True)


def _add_body(doc: Document, text: str, *, size: float = 11) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(4)
    _font(paragraph.add_run(text), size=size)


def _shade(cell, fill: str) -> None:
    tc = cell._tc
    props = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    props.append(shd)


def _set_widths(table, widths) -> None:
    table.autofit = False
    table.allow_autofit = False
    for row in table.rows:
        for cell, width in zip(row.cells, widths, strict=False):
            cell.width = width


def _add_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    *,
    widths,
    center_first: bool = False,
) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    _set_widths(table, widths)
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        _shade(cell, "F3F3F3")
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if center_first and index == 0 else WD_ALIGN_PARAGRAPH.LEFT
        _font(paragraph.add_run(header), size=9, bold=True)
    for r_index, row in enumerate(rows):
        for c_index, value in enumerate(row):
            cell = table.rows[r_index + 1].cells[c_index]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            paragraph = cell.paragraphs[0]
            if center_first and c_index == 0:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _font(paragraph.add_run(value), size=10.5, bold=c_index == 0 and not center_first)


def _add_point_table(doc: Document, rows: list[dict[str, str]]) -> None:
    _add_table(
        doc,
        ["要点", "原句", "例子"],
        [[row["text"], row["evidence"], row["example"]] for row in rows],
        widths=(Cm(5.6), Cm(5.4), Cm(5.4)),
    )


def _add_page_number(doc: Document) -> None:
    paragraph = doc.sections[0].footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)
    _font(run, size=9, color=_LABEL)
