# Studio 插件约定

Studio 能力以磁盘插件形式存在，类似 Claude Code skill/plugin：每个能力一个目录，平台只负责发现、启用/停用、入队与工作区注入。

## 目录

```
api/app/studio/plugins/
  DESIGN.md
  registry.py          # 扫描本目录，加载 plugin.json
  <plugin_id>/
    plugin.json        # 元数据 + 表单 + 超时等
    system.md          # 系统提示（角色与约束）
    instructions.md    # 产物格式说明（注入 prompt）
    skill/             # 可选：一个或多个 Claude skill 目录
      <skill-name>/
        SKILL.md
        ...
web/src/studio/plugins/
  registry.ts          # format_key -> ResultView
  <plugin_id>/
    ResultView.tsx     # 该能力专属结果展示
```

## plugin.json 字段

| 字段 | 说明 |
|------|------|
| id | 与目录名、`format_key` 一致，如 `mind_map` |
| name / icon / version | 展示用 |
| enabled_by_default | 首次 seed 时是否启用 |
| timeout_seconds | Claude 超时 |
| skill | `skill/` 下要注入的子目录名；可省略 |
| extensions | 主产物允许后缀 |
| preferred_names | 无 MANIFEST 时的优选文件名 |
| form | 生成表单（language / sources / text / select） |

## 新增第 4 个插件（步骤）

1. 在 `api/app/studio/plugins/<id>/` 建目录
2. 写 `plugin.json`、`system.md`、`instructions.md`
3. 若需工具链，在 `skill/<name>/` 放 `SKILL.md`（及脚本）
4. 默认用 extensions + MANIFEST 接受产物；特殊校验可扩展 formats
5. 前端 `web/src/studio/plugins/<id>/ResultView.tsx` + 在 `registry.ts` 注册
6. 重启 `make api`（seed 同步到 DB）与 studio-worker
7. 管理后台 Studio 工作台里**启用**该插件
8. 到笔记本 Studio 面板生成验证

## 平台职责（薄）

- 扫描插件、把启用状态持久化到 `studio_capabilities`（按 format_key）
- 工作台只允许启用/停用，不在页面新建能力、不上传 skill、不绑定智能体
- Runner：按插件拷贝 skill → 注入 instructions + system → 跑 Claude → `accept_outputs`

## 与旧「智能体 / 技能上传」的关系

- Studio 插件自带 skill 与 system，不再依赖管理台「新建智能体」或「上传技能」
- 全局仍使用 Claude Code 连接配置（API Key / 模型）
- 旧的 agents/skills 管理页可保留给非 Studio 用途，但 Studio 流程不再读取它们
