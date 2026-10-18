"""Admin skill upload / download / delete API."""
from __future__ import annotations

import io
import zipfile

import pytest
import pytest_asyncio

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.studio import Agent
from app.models.user import User

_OVERSIZE = 32 * 1024 * 1024 + 1


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buf.getvalue()


@pytest_asyncio.fixture
async def admin_headers(db_session) -> dict[str, str]:
    admin = User(phone="13800000900", name="Admin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    token, _ = create_access_token(admin.id, role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _isolate_skills_root(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    root.mkdir()
    monkeypatch.setattr(get_settings(), "skills_root", root)
    return root


async def test_upload_requires_skill_md(client, admin_headers):
    bad = _zip({"README.md": "nope"})
    response = await client.post(
        "/api/admin/skills",
        headers=admin_headers,
        files={"file": ("skill.zip", bad, "application/zip")},
    )
    assert response.status_code == 400


async def test_upload_single_folder_and_reject_traversal(client, admin_headers):
    good = _zip({"officecli-pptx/SKILL.md": "---\nname: officecli-pptx\n---\n"})
    created = await client.post(
        "/api/admin/skills",
        headers=admin_headers,
        files={"file": ("skill.zip", good, "application/zip")},
    )
    assert created.status_code == 201
    assert created.json()["name"] == "officecli-pptx"
    slipped = _zip({"../SKILL.md": "x"})
    rejected = await client.post(
        "/api/admin/skills",
        headers=admin_headers,
        files={"file": ("bad.zip", slipped, "application/zip")},
    )
    assert rejected.status_code == 400


async def test_upload_rejects_oversized_zip(client, admin_headers):
    skills_root = get_settings().skills_root
    before = {p.name for p in skills_root.iterdir()}
    payload = b"x" * _OVERSIZE
    response = await client.post(
        "/api/admin/skills",
        headers=admin_headers,
        files={"file": ("huge.zip", payload, "application/zip")},
    )
    assert response.status_code == 400
    after = {p.name for p in skills_root.iterdir()}
    assert after == before


async def test_download_contains_original_skill_md(client, admin_headers):
    body = "---\nname: officecli-pptx\n---\noriginal skill text\n"
    good = _zip({"officecli-pptx/SKILL.md": body})
    created = await client.post(
        "/api/admin/skills",
        headers=admin_headers,
        files={"file": ("skill.zip", good, "application/zip")},
    )
    assert created.status_code == 201
    skill_id = created.json()["id"]
    downloaded = await client.get(
        f"/api/admin/skills/{skill_id}/download",
        headers=admin_headers,
    )
    assert downloaded.status_code == 200
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as zf:
        names = zf.namelist()
        skill_md = next(name for name in names if name.rstrip("/").endswith("SKILL.md"))
        assert zf.read(skill_md).decode() == body


async def test_delete_skill_in_use_returns_409(client, admin_headers, db_session):
    good = _zip({"officecli-pptx/SKILL.md": "---\nname: officecli-pptx\n---\n"})
    created = await client.post(
        "/api/admin/skills",
        headers=admin_headers,
        files={"file": ("skill.zip", good, "application/zip")},
    )
    assert created.status_code == 201
    skill_id = created.json()["id"]
    db_session.add(
        Agent(
            name="引用技能的智能体",
            skill_id=skill_id,
            system_prompt="写出导图",
            updated_by=1,
        )
    )
    await db_session.commit()
    removed = await client.delete(
        f"/api/admin/skills/{skill_id}",
        headers=admin_headers,
    )
    assert removed.status_code == 409


async def test_list_skills_requires_admin(client, db_session):
    user = User(phone="13900000900", name="User", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role="user")
    response = await client.get(
        "/api/admin/skills",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
