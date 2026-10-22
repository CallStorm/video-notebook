# video-notebook

Web 版 NotebookLM 风格的**视频知识工作台**：把视频抓进来、出字幕、可对话、可做思维导图 / PPT。系统内部使用。

## 功能

- [笔记本与来源](docs/features.md#笔记本与来源) — 上传 / URL 抓取、字幕、概览
- [对话](docs/features.md#对话) — 基于勾选来源的问答（含引用）
- [Studio](docs/features.md#studio) — 思维导图、幻灯片（Skills / Agents）
- [发现与聚合搜索](docs/features.md#发现与聚合搜索) — 站内发现、跨平台搜视频
- [集合与权限](docs/features.md#集合与权限) — Collections、账号、外观皮肤
- [管理后台](docs/features.md#管理后台) — 模型、抓取与网络、向量、账号

更细的产品说明见 [需求文档](docs/requirements.md)。

## 快速开始

### Docker 一键（推荐）

```bash
cp .env.example .env          # 已有 .env 勿覆盖；改掉默认密码与密钥
docker compose up -d --build  # 或 make up
```

- Web：http://127.0.0.1:8080
- API 文档：http://127.0.0.1:8000/docs

首次登录用 `.env` 里的 `SEED_ADMIN_*`。完整说明见 [部署](docs/deployment.md)。

### 本地开发

```bash
cp .env.example .env
make middleware    # mysql + redis + qdrant
make migrate
make api           # :8000
make web           # :5173
make media-worker  # 抓取 / 字幕 / 向量
make worker        # Studio
```

前置与细节见 [开发环境](docs/development.md)。

## 文档

| 文档 | 内容 |
|------|------|
| [功能说明](docs/features.md) | 按功能点介绍现状 |
| [架构](docs/architecture.md) | 组件、数据流、双 Worker |
| [部署](docs/deployment.md) | Compose 拓扑、环境变量、卷、FAQ |
| [开发](docs/development.md) | Makefile、依赖、本地启动 |
| [需求](docs/requirements.md) | 产品功能面与 SaaS 子需求 |
| [设计规格](docs/superpowers/specs/2026-10-16-video-notebook-design.md) | 详细设计（历史规格，部分已演进） |
