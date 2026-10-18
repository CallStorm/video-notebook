# Collections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Authors can create collections, edit membership from either side, open a collection detail page, and add a notebook to one or more collections from the home card menu.

**Architecture:** Two tables (`collections`, `collection_notebooks`) owned by the current user. Membership is synced with full-replace `PUT` endpoints. The home「集合」tab lists collections; a detail route shows notebooks inside one collection; two dialogs cover edit-collection and add-to-collection.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest, React 18, Vite, TanStack Query, existing home card / dialog patterns.

**Spec:** `docs/superpowers/specs/2026-10-18-collections-design.md`

## Global Constraints

- Collections are author-only; no sharing.
- Non-owner access returns 404 (not 403).
- Blank collection name → 400「名称不能为空」.
- `PUT` membership bodies are the full desired set; empty arrays clear membership.
- Soft-deleted notebooks (`deleted_at` set) are ignored in counts and lists.
- New collection default icon is `null` (UI shows folder). `Remove emoji` / `PATCH icon=""` clears icon.
- Same owner may have duplicate collection names.
- Work in the primary checkout `/Users/huzhongzhong/Developer/personal/video-notebook`, not the detached worktree.
- Migration is `0013_collections`, `down_revision = "0012"`. Do not rewrite 0010–0012.
- Do not commit or push unless the user asks.

## 文件地图

| 文件 | 职责 |
|---|---|
| `api/app/models/collection.py` | `Collection`、`CollectionNotebook` |
| `api/alembic/versions/0013_collections.py` | 建表 |
| `api/app/schemas/collection.py` | 请求/响应模型 |
| `api/app/services/collections.py` | CRUD 与成员同步 |
| `api/app/routes/collections.py` | `/api/collections…` |
| `api/app/routes/notebooks.py` | 增加 `/notebooks/{id}/collections` |
| `api/app/routes/__init__.py` | 挂载 collections router |
| `api/tests/conftest.py` | import 新模型 |
| `api/tests/test_collections.py` | API 测试 |
| `web/src/components/collection-edit-dialog.tsx` | New / Edit collection 弹窗 |
| `web/src/components/add-to-collection-dialog.tsx` | Add to collection 弹窗 |
| `web/src/components/collection-card-menu.tsx` | 集合卡片更多菜单 |
| `web/src/components/notebook-card-menu.tsx` | 启用 Add to collection |
| `web/src/pages/home.tsx` | 集合 tab 列表 |
| `web/src/pages/collection.tsx` | 集合详情 |
| `web/src/router.tsx` | `/collections/:id` |

---

### Task 1: 表与迁移

**Files:**
- Create: `api/app/models/collection.py`
- Create: `api/alembic/versions/0013_collections.py`
- Modify: `api/tests/conftest.py`（import `Collection`, `CollectionNotebook`）
- Test: `api/tests/test_collections_schema.py`

**Interfaces:**
- Consumes: `Base`, `TimestampMixin`, `BigInt` 写法同 `api/app/models/notebook.py`
- Produces: `Collection(id, owner_id, name, icon)`, `CollectionNotebook(collection_id, notebook_id, added_at)` 联合主键

- [ ] **Step 1: Write the failing test**

```python
from app.db.base import Base
from app.models.collection import Collection, CollectionNotebook  # noqa: F401


def test_collection_tables_exist():
    names = set(Base.metadata.tables)
    assert {"collections", "collection_notebooks"} <= names
    cols = Base.metadata.tables["collections"].c
    assert {"id", "owner_id", "name", "icon"} <= {c.name for c in cols}
    link = Base.metadata.tables["collection_notebooks"].c
    assert {"collection_id", "notebook_id", "added_at"} <= {c.name for c in link}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_collections_schema.py --no-cov -q`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: Write models and migration**

`Collection`: `name` String(255) not null；`icon` String(16) nullable；`owner_id` indexed.  
`CollectionNotebook`: FK cascade on collection delete；`notebook_id` FK to notebooks；`added_at` server default `func.now()`.  
Alembic `0013_collections.py` creates both tables.

- [ ] **Step 4: Import models in conftest; run test**

Run: `cd api && uv run pytest tests/test_collections_schema.py --no-cov -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/models/collection.py api/alembic/versions/0013_collections.py api/tests/conftest.py api/tests/test_collections_schema.py
git commit -m "Add collections tables and migration."
```

---

### Task 2: 集合 CRUD API

**Files:**
- Create: `api/app/schemas/collection.py`
- Create: `api/app/services/collections.py`
- Create: `api/app/routes/collections.py`
- Modify: `api/app/routes/__init__.py`
- Test: `api/tests/test_collections.py`

**Interfaces:**
- Consumes: `get_current_user`, `BadRequestError`, `NotFoundError`, `Collection` model
- Produces:
  - `CollectionRead`: `{ id, name, icon, notebook_count, created_at, updated_at }`
  - `CollectionDetail`: `CollectionRead` + `notebooks: list[NotebookRead]`（复用 `app.schemas.notebook.NotebookRead`，`source_count`/`note_count` 与列表一致）
  - Routes: `GET/POST /collections`, `GET/PATCH/DELETE /collections/{id}`

- [ ] **Step 1: Write failing API tests**

```python
async def test_create_list_patch_delete_collection(client, owner_headers):
    created = await client.post(
        "/api/collections",
        headers=owner_headers,
        json={"name": "  分类1  "},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "分类1"
    assert body["icon"] is None
    assert body["notebook_count"] == 0

    listed = await client.get("/api/collections", headers=owner_headers)
    assert listed.status_code == 200
    assert any(row["id"] == body["id"] for row in listed.json())

    patched = await client.patch(
        f"/api/collections/{body['id']}",
        headers=owner_headers,
        json={"name": "分类壹", "icon": "📁"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "分类壹"
    assert patched.json()["icon"] == "📁"

    cleared = await client.patch(
        f"/api/collections/{body['id']}",
        headers=owner_headers,
        json={"icon": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["icon"] is None

    blank = await client.post(
        "/api/collections",
        headers=owner_headers,
        json={"name": "   "},
    )
    assert blank.status_code == 400

    deleted = await client.delete(f"/api/collections/{body['id']}", headers=owner_headers)
    assert deleted.status_code == 204
    missing = await client.get(f"/api/collections/{body['id']}", headers=owner_headers)
    assert missing.status_code == 404


async def test_outsider_cannot_see_collection(client, owner_headers, outsider_headers):
    created = await client.post(
        "/api/collections",
        headers=owner_headers,
        json={"name": "私有"},
    )
    cid = created.json()["id"]
    assert (await client.get(f"/api/collections/{cid}", headers=outsider_headers)).status_code == 404
```

Fixtures mirror `test_studio_tasks.py` owner / outsider headers. List response may be a bare `list` (prefer) or `{ items: [...] }` — pick **bare list** for simplicity and match the test above.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && uv run pytest tests/test_collections.py --no-cov -q`  
Expected: FAIL

- [ ] **Step 3: Implement schemas, service, routes**

Service helpers:

```python
async def get_owned_collection(session, user_id: int, collection_id: int) -> Collection:
    ...

def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise BadRequestError("名称不能为空")
    return cleaned[:255]
```

`PATCH`: if `icon` is `""` or `None` when the field is explicitly sent as empty string, store `None`. Use a model with `icon: str | None = None` and treat missing vs empty: only update icon when the key is present; empty string → null.

`notebook_count`: count join rows where notebook `deleted_at IS NULL`.

- [ ] **Step 4: Run tests**

Run: `cd api && uv run pytest tests/test_collections.py --no-cov -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/schemas/collection.py api/app/services/collections.py api/app/routes/collections.py api/app/routes/__init__.py api/tests/test_collections.py
git commit -m "Add collection CRUD API."
```

---

### Task 3: 成员同步 API

**Files:**
- Modify: `api/app/services/collections.py`
- Modify: `api/app/routes/collections.py`
- Modify: `api/app/routes/notebooks.py`
- Modify: `api/app/schemas/collection.py`
- Modify: `api/tests/test_collections.py`

**Interfaces:**
- Produces:
  - `PUT /collections/{id}/notebooks` body `{ notebook_ids: number[] }` → `CollectionDetail`
  - `GET /notebooks/{id}/collections` → `{ collection_ids: number[] }`
  - `PUT /notebooks/{id}/collections` body `{ collection_ids: number[] }` → `{ collection_ids: number[] }`

- [ ] **Step 1: Write failing tests**

```python
async def test_sync_collection_notebooks(client, db_session, owner, owner_headers, outsider_headers):
    # create two owned notebooks + one outsider notebook; create collection
    # PUT notebook_ids [a, b] → detail.notebooks ids match, notebook_count == 2
    # PUT [] → count 0
    # PUT [outsider_nb] → 400
    # outsider PUT owner collection → 404


async def test_sync_notebook_collections(client, owner_headers):
    # two collections + one notebook
    # PUT collection_ids [c1, c2] → GET returns both
    # PUT [c1] → only c1
    # PUT [foreign_collection] → 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && uv run pytest tests/test_collections.py --no-cov -q`  
Expected: FAIL on new cases

- [ ] **Step 3: Implement sync in one transaction**

```python
async def set_collection_notebooks(session, user_id, collection_id, notebook_ids: list[int]) -> Collection:
    collection = await get_owned_collection(...)
    owned = await load_owned_notebook_ids(session, user_id, notebook_ids)  # deleted_at is null
    if set(owned) != set(notebook_ids):
        raise BadRequestError("笔记本无效")
    # delete links not in set; insert missing; commit
    ...


async def set_notebook_collections(session, user_id, notebook_id, collection_ids: list[int]) -> list[int]:
    notebook = await get_owned_notebook(...)  # 404 if missing/deleted/not owner
    owned_cols = await load_owned_collection_ids(...)
    if set(owned_cols) != set(collection_ids):
        raise BadRequestError("集合无效")
    # replace links for this notebook_id only
    ...
```

Reuse existing notebook list serialization for detail notebooks (same fields as `GET /notebooks`).

- [ ] **Step 4: Run tests**

Run: `cd api && uv run pytest tests/test_collections.py --no-cov -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/services/collections.py api/app/routes/collections.py api/app/routes/notebooks.py api/app/schemas/collection.py api/tests/test_collections.py
git commit -m "Sync collection and notebook membership with PUT."
```

---

### Task 4: 集合列表与卡片菜单

**Files:**
- Create: `web/src/components/collection-card-menu.tsx`
- Modify: `web/src/pages/home.tsx`（替换 collections placeholder）
- Test: `cd web && npm run typecheck`

**Interfaces:**
- Consumes: `GET /collections`, `DELETE /collections/{id}`, `PATCH /collections/{id}`
- Produces: collections tab showing cards; menu Edit / Delete / Remove emoji

- [ ] **Step 1: Add API helpers and replace placeholder in home**

Types:

```ts
interface Collection {
  id: number;
  name: string;
  icon: string | null;
  notebook_count: number;
  created_at: string | null;
  updated_at: string | null;
}
```

When `tab === "collections"`, fetch `/collections`, show header「My collections」+「+ New collection」button (opens dialog stub or state for Task 5), grid of cards. Click card → `navigate(`/collections/${id}`)`.

`CollectionCardMenu`: portal menu like `notebook-card-menu.tsx` with Edit / Delete / Remove emoji.

- [ ] **Step 2: Wire mutations**

- Delete: confirm「删除这个集合？」then `DELETE`, invalidate query.
- Remove emoji: `PATCH { icon: "" }`.
- Edit: set editing collection id for Task 5 dialog (can leave TODO callback that sets state).

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/src/components/collection-card-menu.tsx web/src/pages/home.tsx
git commit -m "Show collections on the home tab."
```

---

### Task 5: New / Edit collection 弹窗

**Files:**
- Create: `web/src/components/collection-edit-dialog.tsx`
- Modify: `web/src/pages/home.tsx`
- Test: `cd web && npm run typecheck`

**Interfaces:**
- Consumes: `GET /notebooks`, `POST/PATCH /collections`, `PUT /collections/{id}/notebooks`, optional `GET /collections/{id}` for edit preload
- Produces: dialog matching Edit collection screenshot

- [ ] **Step 1: Build dialog**

Props:

```ts
{
  open: boolean;
  mode: "create" | "edit";
  collectionId: number | null;
  access: string;
  onClose: () => void;
  onSaved: () => void;
}
```

UI: name input; 「Notebooks (n)」; search filter client-side on notebook titles; checkbox list from `GET /notebooks` items (ignore deleted — API already); Cancel / Save.

Save create:

1. `POST /collections` `{ name }`
2. `PUT /collections/{id}/notebooks` `{ notebook_ids }`

Save edit:

1. `PATCH /collections/{id}` `{ name }`
2. `PUT /collections/{id}/notebooks` `{ notebook_ids }`

- [ ] **Step 2: Hook from home New + Edit menu**

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/src/components/collection-edit-dialog.tsx web/src/pages/home.tsx
git commit -m "Add new and edit collection dialog."
```

---

### Task 6: 集合详情页

**Files:**
- Create: `web/src/pages/collection.tsx`
- Modify: `web/src/router.tsx`
- Test: `cd web && npm run typecheck`

**Interfaces:**
- Consumes: `GET /collections/{id}`
- Produces: back link, title, notebook grid reusing home card components / menu

- [ ] **Step 1: Page + route**

`/collections/:id` under `RequireAuth`. Header: back to home with collections tab preferred (`/?tab=collections` or `navigate(-1)` + home tab state). Edit button opens same `CollectionEditDialog`.

Reuse notebook card rendering from home (extract small presentational pieces if needed, or duplicate thinly to avoid large refactor).

- [ ] **Step 2: Typecheck**

Run: `cd web && npm run typecheck`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/collection.tsx web/src/router.tsx web/src/pages/home.tsx
git commit -m "Add collection detail page."
```

---

### Task 7: Add to collection 弹窗

**Files:**
- Create: `web/src/components/add-to-collection-dialog.tsx`
- Modify: `web/src/components/notebook-card-menu.tsx`
- Modify: `web/src/pages/home.tsx`（及 collection 详情若复用菜单）
- Test: `cd web && npm run typecheck`

**Interfaces:**
- Consumes: `GET /collections`, `GET /notebooks/{id}/collections`, `POST /collections`, `PUT /notebooks/{id}/collections`
- Produces: enabled menu item + dialog from screenshots

- [ ] **Step 1: Enable menu item**

Remove `disabled` / Phase 12 hint. Add `onAddToCollection: (id: number) => void`.

- [ ] **Step 2: Dialog**

- Header + notebook chip (icon + title).
- 「Select collections (n)」+「+ Create new」: prompt or inline input; on submit `POST /collections` then add id to checked set (or keep local pending name and create on Save — prefer create immediately so checkbox has a real id).
- Checkbox list of collections; preload checked from `GET /notebooks/{id}/collections`.
- Save → `PUT /notebooks/{id}/collections` `{ collection_ids }`; invalidate collections list queries.

- [ ] **Step 3: Wire on home and collection detail**

- [ ] **Step 4: Typecheck**

Run: `cd web && npm run typecheck`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/components/add-to-collection-dialog.tsx web/src/components/notebook-card-menu.tsx web/src/pages/home.tsx web/src/pages/collection.tsx
git commit -m "Add notebooks to collections from the card menu."
```

---

### Task 8: 手工验收

- [ ] **Step 1: Migrate**

Run: `cd api && uv run alembic upgrade head`  
Expected: head `0013`

- [ ] **Step 2: Browser checklist**

1. 集合 tab：新建集合，卡片计数 0。
2. Edit：勾选笔记本，Save；详情与计数一致。
3. Remove emoji / Delete 菜单可用。
4. 笔记本更多 → Add to collection：多选、Create new、Save；再打开勾选正确。
5. 非所有者：不要用第二账号打穿（API 测试已覆盖）。

- [ ] **Step 3: Full API suite smoke**

Run: `cd api && uv run pytest tests/test_collections.py tests/test_collections_schema.py --no-cov -q`  
Expected: PASS

---

## Spec coverage

| Spec 项 | Task |
|---|---|
| tables + 0013 | 1 |
| collection CRUD + icon clear | 2 |
| PUT collection notebooks / notebook collections | 3 |
| list + card menu | 4 |
| New/Edit dialog | 5 |
| detail page | 6 |
| Add to collection dialog | 7 |
| manual acceptance | 8 |

## Placeholder / consistency check

- Bare list for `GET /collections` used consistently in tests and frontend.
- `NotebookRead` reused for detail notebooks.
- Empty icon → `null` on both PATCH collection and Remove emoji.
