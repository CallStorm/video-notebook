"""管理后台首页：就绪分项、未就绪名单，以及失败 TOP 的数据口径。"""
from __future__ import annotations

from datetime import datetime

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.notebook import Note, Notebook, NotebookSource, Video
from app.models.notebook_index import NotebookIndexState
from app.models.user import User


async def _user(db_session, phone: str, *, role: str = "user") -> tuple[User, str]:
    user = User(phone=phone, name=phone, role=role, status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role=role)
    return user, token


@pytest.mark.asyncio
async def test_admin_stats_lists_exceptions_and_stock_failures(
    client: AsyncClient, db_session
):
    admin, token = await _user(db_session, "13800000961", role="admin")
    other, _ = await _user(db_session, "13800000962")

    stale = Notebook(owner_id=admin.id, title="过期本", is_pinned=False, share_all=False)
    broken = Notebook(owner_id=admin.id, title="字幕失败本", is_pinned=False, share_all=False)
    healthy = Notebook(owner_id=admin.id, title="完整本", is_pinned=False, share_all=False)
    empty = Notebook(owner_id=other.id, title="别人的空壳", is_pinned=False, share_all=False)
    stale_video = Video(
        owner_id=admin.id,
        source_type="upload",
        status="ready",
        storage_key="stale.mp4",
        subtitle_status="ready",
        overview_status="failed",
        overview_error="模型超时",
        title="上",
    )
    broken_video = Video(
        owner_id=admin.id,
        source_type="upload",
        status="ready",
        storage_key="broken.mp4",
        subtitle_status="failed",
        subtitle_error="识别失败",
        overview_status="pending",
        title="下",
    )
    healthy_video = Video(
        owner_id=admin.id,
        source_type="upload",
        status="ready",
        storage_key="ok.mp4",
        subtitle_status="ready",
        overview_status="ready",
        title="好",
    )
    db_session.add_all(
        [stale, broken, healthy, empty, stale_video, broken_video, healthy_video]
    )
    await db_session.commit()
    for row in (stale, broken, healthy, empty, stale_video, broken_video, healthy_video):
        await db_session.refresh(row)

    db_session.add_all(
        [
            NotebookSource(
                notebook_id=stale.id,
                video_id=stale_video.id,
                sort=0,
                selected_for_chat=True,
            ),
            NotebookSource(
                notebook_id=broken.id,
                video_id=broken_video.id,
                sort=0,
                selected_for_chat=True,
            ),
            NotebookSource(
                notebook_id=healthy.id,
                video_id=healthy_video.id,
                sort=0,
                selected_for_chat=True,
            ),
            NotebookIndexState(
                notebook_id=stale.id,
                status="ready",
                indexed_at=datetime(2026, 1, 1, 8, 0, 0),
            ),
            NotebookIndexState(
                notebook_id=healthy.id,
                status="ready",
                indexed_at=datetime(2099, 1, 1, 8, 0, 0),
            ),
            Note(
                notebook_id=stale.id,
                author_id=admin.id,
                title="新笔记",
                content_text="还没写入",
                updated_at=datetime(2026, 2, 1, 8, 0, 0),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/admin/stats", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    readiness = body["readiness"]

    assert readiness["subtitle"]["ready"] == 2
    assert readiness["subtitle"]["total"] == 3
    assert readiness["subtitle_detail"] == {"failed": 1, "processing": 0, "pending": 0}
    assert readiness["overview_detail"]["failed"] == 1
    assert readiness["overview_detail"]["pending"] == 1
    assert readiness["vector_detail"]["stale"] == 1
    assert readiness["vector_detail"]["empty"] == 1
    assert readiness["vector_detail"]["failed"] == 0
    assert readiness["complete_notebooks"]["ready"] == 1

    ids = {item["notebook_id"] for item in readiness["exceptions"]}
    assert healthy.id not in ids
    assert {stale.id, broken.id, empty.id} <= ids
    assert readiness["exception_total"] >= 3

    by_id = {item["notebook_id"]: item for item in readiness["exceptions"]}
    assert by_id[stale.id]["is_mine"] is True
    assert by_id[stale.id]["index_stale"] is True
    assert by_id[stale.id]["index_status"] == "ready"
    assert "模型超时" in (by_id[stale.id]["error"] or "")
    assert by_id[broken.id]["subtitle_failed"] == 1
    assert "识别失败" in (by_id[broken.id]["error"] or "")
    assert by_id[empty.id]["is_mine"] is False
    assert by_id[empty.id]["owner_name"] == other.name
    assert by_id[empty.id]["subtitle_total"] == 0

    ranks = [item["notebook_id"] for item in readiness["exceptions"]]
    assert ranks.index(broken.id) < ranks.index(empty.id)
    assert ranks.index(stale.id) < ranks.index(empty.id)

    assert body["failures"]["basis"] == "stock"
    labels = [item["label"] for item in body["failures"]["top"]]
    assert "字幕失败(业务)" in labels
    assert "概览失败(业务)" in labels
