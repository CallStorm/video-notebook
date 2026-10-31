"""LLM traces list: filter by kind / notebook_id on server."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio

from app.core.security import create_access_token
from app.models.notebook import Notebook
from app.models.observability import LlmTrace
from app.models.user import User


@pytest_asyncio.fixture
async def admin_headers(db_session) -> dict[str, str]:
    admin = User(phone="13800000991", name="ObsAdmin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    token, _ = create_access_token(admin.id, role="admin")
    return {"Authorization": f"Bearer {token}"}


_TRACE_SEQ = 0


def _trace(
    *,
    kind: str,
    notebook_id: int | None,
    status: str = "ok",
) -> LlmTrace:
    global _TRACE_SEQ
    _TRACE_SEQ += 1
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return LlmTrace(
        id=_TRACE_SEQ,
        trace_id=str(uuid4()),
        kind=kind,
        status=status,
        notebook_id=notebook_id,
        video_id=None,
        thread_id=None,
        message_id=None,
        provider="test",
        model_name="test-model",
        error_text=None,
        prompt_tokens=10,
        completion_tokens=5,
        latency_ms=100,
        started_at=now,
        finished_at=now,
    )


@pytest.mark.asyncio
async def test_list_llm_traces_filters_by_kind_and_notebook(
    client, admin_headers, db_session
):
    owner = User(phone="13800000992", name="Owner", role="user", status="active")
    owner.set_password("userpw1234")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    nb_a = Notebook(owner_id=owner.id, title="NB-A")
    nb_b = Notebook(owner_id=owner.id, title="NB-B")
    db_session.add_all([nb_a, nb_b])
    await db_session.commit()
    await db_session.refresh(nb_a)
    await db_session.refresh(nb_b)

    db_session.add_all(
        [
            _trace(kind="overview", notebook_id=nb_a.id),
            _trace(kind="chat", notebook_id=nb_a.id),
            _trace(kind="overview", notebook_id=nb_b.id),
            _trace(kind="studio", notebook_id=nb_b.id, status="failed"),
        ]
    )
    await db_session.commit()

    all_resp = await client.get(
        "/api/admin/observability/llm-traces?limit=50",
        headers=admin_headers,
    )
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] == 4

    overview = await client.get(
        "/api/admin/observability/llm-traces?kind=overview",
        headers=admin_headers,
    )
    assert overview.status_code == 200
    body = overview.json()
    assert body["total"] == 2
    assert all(i["kind"] == "overview" for i in body["items"])

    by_nb = await client.get(
        f"/api/admin/observability/llm-traces?notebook_id={nb_a.id}",
        headers=admin_headers,
    )
    assert by_nb.status_code == 200
    body = by_nb.json()
    assert body["total"] == 2
    assert all(i["notebook_id"] == nb_a.id for i in body["items"])
    assert any(i.get("notebook_title") == "NB-A" for i in body["items"])

    combo = await client.get(
        f"/api/admin/observability/llm-traces?notebook_id={nb_a.id}&kind=overview",
        headers=admin_headers,
    )
    assert combo.status_code == 200
    body = combo.json()
    assert body["total"] == 1
    assert body["items"][0]["kind"] == "overview"
    assert body["items"][0]["notebook_id"] == nb_a.id


@pytest.mark.asyncio
async def test_list_resolves_notebook_from_thread_when_notebook_id_null(
    client, admin_headers, db_session
):
    """Display/filter fallback for legacy chat traces that only stored thread_id."""
    from app.models.notebook import ChatThread

    owner = User(phone="13800000993", name="Owner2", role="user", status="active")
    owner.set_password("userpw1234")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    nb = Notebook(owner_id=owner.id, title="NB-Thread")
    db_session.add(nb)
    await db_session.commit()
    await db_session.refresh(nb)

    thread = ChatThread(notebook_id=nb.id, owner_id=owner.id)
    db_session.add(thread)
    await db_session.commit()
    await db_session.refresh(thread)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    global _TRACE_SEQ
    _TRACE_SEQ += 1
    db_session.add(
        LlmTrace(
            id=_TRACE_SEQ,
            trace_id=str(uuid4()),
            kind="chat",
            status="ok",
            notebook_id=None,
            video_id=None,
            thread_id=thread.id,
            message_id=None,
            provider="test",
            model_name="m",
            error_text=None,
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=10,
            started_at=now,
            finished_at=now,
        )
    )
    await db_session.commit()

    by_nb = await client.get(
        f"/api/admin/observability/llm-traces?notebook_id={nb.id}&kind=chat",
        headers=admin_headers,
    )
    assert by_nb.status_code == 200
    body = by_nb.json()
    assert body["total"] >= 1
    item = next(i for i in body["items"] if i["thread_id"] == thread.id)
    assert item["notebook_id"] == nb.id
    assert item.get("notebook_title") == "NB-Thread"
