"""知识底稿导出为 Word。"""
from __future__ import annotations

import io

import pytest
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import Notebook
from app.models.user import User
from app.services.draft_docx import build_draft_docx, draft_docx_filename


def _blocks(data: bytes) -> list[str]:
    doc = Document(io.BytesIO(data))
    out: list[str] = []
    for child in doc.element.body:
        if child.tag == qn("w:p"):
            text = "".join(node.text or "" for node in child.iter(qn("w:t"))).strip()
            if text:
                out.append(text)
        elif child.tag == qn("w:tbl"):
            rows = []
            for tr in child.iter(qn("w:tr")):
                cells = []
                for tc in tr.findall(qn("w:tc")):
                    cells.append("".join(node.text or "" for node in tc.iter(qn("w:t"))).strip())
                rows.append(" | ".join(cells))
            out.append("TABLE " + " || ".join(rows))
    return out


def test_docx_section_order_and_omits_empty_point_fields() -> None:
    data = build_draft_docx(
        notebook_title="趋势交易",
        theme="顺势持有",
        concepts=[{"term": "结构", "definition": "高低点还没被破坏"}],
        points=[
            {
                "text": "回撤不是反转",
                "time": "08:12",
                "evidence": "回撤是趋势呼吸",
                "example": "三次回踩均线",
                "comment": "我总是卖在半山腰",
                "checked": False,
            },
            {
                "text": "仓位跟着结构走",
                "time": "15:33",
                "evidence": "结构在，仓位在",
                "example": "",
                "comment": None,
                "checked": False,
            },
        ],
        conclusions=["守住再加", ""],
    )
    text = "\n".join(_blocks(data))
    assert text.index("一、主题") < text.index("二、概念") < text.index("三、要点") < text.index("四、我的结论")
    assert "顺势持有" in text
    assert "结构" in text and "高低点还没被破坏" in text
    assert "TABLE 要点 | 原句 | 例子 || 回撤不是反转 | 回撤是趋势呼吸 | 三次回踩均线 || 仓位跟着结构走 | 结构在，仓位在 | " in text
    assert "我的评论" not in text
    assert "我总是卖在半山腰" not in text
    assert "08:12" not in text
    assert "15:33" not in text
    assert "守住再加" in text
    assert "收获" not in text
    assert "待问" not in text
    doc = Document(io.BytesIO(data))
    title = doc.paragraphs[0]
    section = next(p for p in doc.paragraphs if p.text.startswith("一、"))
    assert title.style.name == "Heading 1"
    assert section.style.name == "Heading 2"
    assert title.runs[0].font.size == Pt(22)
    assert section.runs[0].font.size == Pt(14)
    title_borders = title._p.find(qn("w:pPr")).find(qn("w:pBdr"))
    assert title_borders.find(qn("w:bottom")) is not None
    assert title_borders.find(qn("w:left")) is None
    section_props = section._p.find(qn("w:pPr"))
    assert section_props is None or section_props.find(qn("w:pBdr")) is None


def test_docx_omits_empty_sections_and_keeps_checked_points() -> None:
    data = build_draft_docx(
        notebook_title="趋势交易",
        theme="  ",
        concepts=[{"term": "  ", "definition": "不会出现"}],
        points=[
            {"text": "未勾选", "evidence": "不该出现", "checked": False},
            {"text": "已勾选", "time": "01:00", "evidence": "这句留下", "checked": True},
        ],
        conclusions=[],
    )
    text = "\n".join(_blocks(data))
    assert "主题" not in text
    assert "概念" not in text
    assert "我的结论" not in text
    assert "不会出现" not in text
    assert "未勾选" not in text
    assert "已勾选" in text
    assert "这句留下" in text
    assert "01:00" not in text
    assert "一、要点" in text


def test_filename_strips_invalid_characters() -> None:
    assert draft_docx_filename('趋势/交易:笔记') == "趋势 交易 笔记-底稿.docx"
    assert draft_docx_filename("   ") == "笔记本-底稿.docx"


@pytest.mark.asyncio
async def test_export_endpoint_returns_docx(client: AsyncClient, db_session) -> None:
    user = User(phone="13800007721", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    notebook = Notebook(owner_id=user.id, title="趋势交易", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    db_session.add(
        NotebookKnowledgeDraft(
            notebook_id=notebook.id,
            owner_id=user.id,
            status="ready",
            conclusion="守住再加",
            content_json={
                "theme": "顺势持有",
                "concepts": [{"term": "结构", "definition": "还没破"}],
                "points": [
                    {
                        "id": "p1",
                        "text": "回撤不是反转",
                        "time": "08:12",
                        "evidence": "回撤是趋势呼吸",
                        "checked": False,
                    }
                ],
                "takeaways": [{"id": "t1", "text": "不要导出收获"}],
                "open_questions": ["不要导出待问"],
                "conclusions": ["守住再加"],
            },
            source_video_ids=[],
            source_note_ids=[],
        )
    )
    await db_session.commit()
    token, _ = create_access_token(user.id, role="user")
    response = await client.get(
        f"/api/notebooks/{notebook.id}/knowledge-draft/export.docx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    text = "\n".join(_blocks(response.content))
    assert "顺势持有" in text
    assert "不要导出收获" not in text
    assert "不要导出待问" not in text

    missing = await client.get(
        f"/api/notebooks/{notebook.id + 999}/knowledge-draft/export.docx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 404
