# 集合（Collections）设计

日期：2026-10-18  
状态：待确认  
范围：作者自用集合的 CRUD、集合详情、从笔记本更多菜单加入一个或多个集合。不做共享、Discover、复杂图标选择器。

## 1. 目标

- 用户可以创建、重命名、删除自己的集合，并管理集合图标（清空 emoji）。
- 一个笔记本可以属于零个或多个集合；一个集合可以包含零个或多个笔记本。
- 首页「集合」页与参考图一致：列表、详情、编辑弹窗、笔记本「Add to collection」弹窗。

## 2. 非目标

- 集合多人共享或协作。
- Discover 公开列表。
- 完整 emoji / 图标选择器；新建用默认文件夹图标，菜单提供「Remove emoji」清空。
- 从集合详情里「移出集合」的单独入口（可通过编辑集合或 Add to collection 取消勾选完成）。

## 3. 数据模型

### 3.1 `collections`

| 列 | 说明 |
|---|---|
| `id` | PK |
| `owner_id` | FK → users，索引 |
| `name` | 必填，trim 后非空，最长 255 |
| `icon` | 可空字符串；空或 null 表示无自定义 emoji，前端显示默认文件夹图标 |
| `created_at` / `updated_at` | TimestampMixin |

仅作者可见。删除集合时级联删除 `collection_notebooks` 行，不删笔记本。

同一 `owner_id` 下 `name` **不**做唯一约束（允许同名）；UI 不强制去重。

### 3.2 `collection_notebooks`

| 列 | 说明 |
|---|---|
| `collection_id` | FK → collections，联合主键 |
| `notebook_id` | FK → notebooks，联合主键 |
| `added_at` | 加入时间 |

约束：

- 笔记本必须属于当前用户（与集合 `owner_id` 相同），写入时服务端校验。
- 笔记本软删（`deleted_at` 非空）后：列表与计数忽略；清理任务可选，本轮不强制扫表。

Alembic revision：`0013_collections`，`down_revision = 0012`。

## 4. API

前缀 `/api`，均需登录。非所有者一律 404（不泄露存在性）。

### 4.1 集合

```
GET    /collections
POST   /collections                         { name, icon? }
GET    /collections/{id}
PATCH  /collections/{id}                    { name?, icon? }   # icon 传 "" 或 null 清空
DELETE /collections/{id}
PUT    /collections/{id}/notebooks          { notebook_ids: number[] }  # 全量同步该集合成员
```

`GET /collections` 每项：

```json
{
  "id": 1,
  "name": "分类1",
  "icon": null,
  "notebook_count": 1,
  "created_at": "..."
}
```

`GET /collections/{id}` 另含 `notebooks: NotebookSummary[]`（与首页卡片字段对齐：id, title, icon, updated_at, source_count, is_pinned 等已有摘要）。

`PUT .../notebooks`：以请求体为该集合的完整成员集合。空数组清空。非法或非本人 notebook_id → 400。

### 4.2 笔记本 ↔ 集合

```
GET  /notebooks/{id}/collections            → { collection_ids: number[] }
PUT  /notebooks/{id}/collections            { collection_ids: number[] }  # 全量同步该笔记所在集合
```

`PUT` 只改该笔记的归属；不影响集合内其他笔记。非法或非本人 collection_id → 400。

### 4.3 错误

- 名称空白：400「名称不能为空」。
- 集合 / 笔记本不存在或不属于本人：404。
- 未登录：401。

## 5. 前端

### 5.1 集合列表（首页 tab「集合」或路由 `/collections`）

- 标题「My collections」，右上「+ New collection」。
- 卡片：默认文件夹图标或 `icon`、名称、`N notebook` / `N notebooks`、更多菜单。
- 更多：Edit → 打开编辑弹窗；Delete → 确认后删除；Remove emoji → `PATCH icon=""`。
- 点卡片进入详情。

与现有 `home.tsx` 的 `collections` tab 打通；去掉 Phase 12 占位。

### 5.2 新建 / 编辑弹窗

参考 Edit collection 图：

- 标题「New collection」或「Edit collection」。
- Collection name*。
- Notebooks (n) + 搜索「Search notebooks…」。
- 列出当前用户的笔记本（图标 + 标题 + checkbox）；编辑时预勾选已在集合内的。
- Cancel / Save → `POST` 或 `PATCH` + `PUT .../notebooks`。

新建也可先 `POST` 空成员再 `PUT notebooks`，或 `POST` 后紧跟 `PUT`；一次 Save 完成。

### 5.3 集合详情

- 返回箭头、文件夹图标、集合名；可选 Edit 打开同一编辑弹窗。
- 网格展示该集合内笔记本卡片（复用首页卡片与 `NotebookCardMenu`）。

### 5.4 Add to collection（笔记本更多菜单）

启用现有 `Add to collection` 项（去掉 Phase 12 disabled）：

- 弹窗标题「Add to collection」。
- 顶部条：笔记本图标 + 标题。
- 「Select collections (n)」+「+ Create new」（行内创建名称后加入列表并勾选，Save 时若尚无 id 则先 `POST`）。
- 集合列表：文件夹图标 + 名称 + checkbox；已加入的预勾选。
- Cancel / Save → `PUT /notebooks/{id}/collections` 按勾选全量同步。

### 5.5 文案

UI 可与参考图一致使用英文按钮文案（Add to collection、Save、Cancel、Edit、Delete、Remove emoji、New collection）；产品中文语境下集合名由用户自定。

## 6. 权限与一致性

- 所有读写限定 `owner_id == current_user.id`。
- 全量 `PUT` 在单事务内：先删多余关系，再插入缺失关系。
- 并发：后写覆盖；不做版本号。

## 7. 测试

API（pytest）：

- 创建 / 列表 / 改名 / 清空 icon / 删除集合。
- `PUT` 集合 notebooks：加入、清空、拒绝他人笔记本。
- `PUT` 笔记本 collections：多选同步、拒绝他人集合。
- 非所有者 404。

前端：手工验收列表、详情、两弹窗与菜单项；typecheck。

## 8. 验收标准

1. 可新建集合并在列表看到卡片与计数。
2. 编辑集合可改名并勾选笔记本，详情与计数一致。
3. 集合更多菜单可删除、可 Remove emoji。
4. 笔记本更多菜单可打开 Add to collection，多选保存后再次打开勾选状态正确。
5. 弹窗内 Create new 可新建并勾选后一并保存。
