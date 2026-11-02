"""概览重试只在字幕就绪后进行，并且不改字幕状态。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.notebook import Notebook, NotebookSource, Video
from app.models.user import User


async def _owner(db_session) -> tuple[User, str]:
    user = User(phone="13800000921", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role="user")
    return user, token


async def _video(db_session, user: User, *, subtitle_status: str) -> int:
    notebook = Notebook(owner_id=user.id, title="片", is_pinned=False, share_all=False)
    video = Video(
        owner_id=user.id,
        source_type="upload",
        status="ready",
        storage_key="abc.mp4",
        subtitle_status=subtitle_status,
        subtitle_error="识别失败" if subtitle_status == "failed" else None,
        overview_status="failed",
        overview_error="概览写失败",
        title="已入库",
    )
    db_session.add_all([notebook, video])
    await db_session.commit()
    await db_session.refresh(notebook)
    await db_session.refresh(video)
    db_session.add(
        NotebookSource(
            notebook_id=notebook.id,
            video_id=video.id,
            sort=0,
            selected_for_chat=True,
        )
    )
    await db_session.commit()
    return video.id


@pytest.mark.asyncio
async def test_overview_retry_rejects_until_subtitles_are_ready(client: AsyncClient, db_session):
    user, token = await _owner(db_session)
    video_id = await _video(db_session, user, subtitle_status="failed")
    response = await client.post(
        f"/api/sources/{video_id}/overview/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "字幕" in response.json()["message"]


@pytest.mark.asyncio
async def test_overview_retry_reruns_overview_only(client: AsyncClient, db_session):
    user, token = await _owner(db_session)
    video_id = await _video(db_session, user, subtitle_status="ready")
    response = await client.post(
        f"/api/sources/{video_id}/overview/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overview_status"] == "processing"
    assert body["overview_error"] is None
    assert body["subtitle_status"] == "ready"
