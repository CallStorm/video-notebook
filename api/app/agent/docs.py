"""公开的 llms.txt、Skill 与安装脚本。Skill 正文不包含长期 Token。"""
from __future__ import annotations

SKILL_BODY = '---\nname: video-notebook\ndescription: >-\n  视频笔记 Agent：用 MCP 在 YouTube/Bilibili 搜索视频、按用户明确指令建笔记本/加链接，\n  等全部来源字幕就绪后再生成知识底稿；支持签名 URL 取原视频与 Studio 产物。\n  接到「视频笔记」相关请求时使用。默认停步：未获明确指令时禁止把搜索、入库、生成串成流水线。\n  不要用网站 /api 登录或手机号 JWT。\n---\n\n# 视频笔记 Skill\n\n把当前 Agent 客户端（Claude Code、WorkBuddy、Cursor 等）接到「视频笔记」。用 MCP 工具操作，不要调用网站的 `/api` 登录接口，也不要使用手机号登录 JWT。\n\n**默认停步：未获用户明确指令时，禁止把搜索、入库、生成底稿串成一条自动流水线。**\n\nToken 只放在 MCP 配置的 `Authorization: Bearer` 里。不要把 Token 写进本 Skill，不要提交到仓库。运行 `install.sh --token …` 后，把脚本打印的 MCP JSON 注册到**你当前客户端**，并把本 Skill 装进该客户端的 skills 目录。\n\n搜索平台仅为 **YouTube / Bilibili**（不支持抖音）。用户提到抖音时，应说明平台限制，改用 YouTube/Bilibili 搜索相近内容，并等用户确认后再入库。\n\n## 推荐链路（逐步、等人确认）\n\n1. **澄清意图**：若用户只说「找视频 / 搜一下 / 推荐」，默认只做搜索与总结，不要主动建笔记本或生成底稿。\n2. **仅搜索时**：只调用 `search`（YouTube/Bilibili）。汇总标题、链接、为何相关后 **立刻 STOP**，把结果交给用户选择。此时禁止 `create_notebook` / `add_url` / `generate_draft` / `generate_cover`，除非用户在后续消息里明确要求。\n3. **明确要求收集/加入笔记本时**：再 `create_notebook`（若尚无）+ 对用户选定或明确确认的 URL 调用 `add_url`。不要替用户擅自加入搜索结果里的全部链接。\n4. **加入后**：轮询 `get_readiness`，向用户汇报进度。`ready_for_draft` 为 false（仍有抓取中或字幕未就绪）时 **不要** 调用 `generate_draft`；直接说明哪些来源未就绪。\n5. **明确要求生成底稿/知识稿时**：先确认 `get_readiness` 的 `ready_for_draft=true`，再调用 `generate_draft`。后端也会硬拦截未就绪来源。`generate_draft` 立刻返回 `job_id`（= Studio 底稿 `task_id`）；用 `get_job` 等到 `succeeded`，再用 **`get_draft`** 读正文。\n   - 底稿**任务**在网页「产物」和 `list_artifacts`（format_key=`knowledge_draft`）；**正文**在「知识」页，用 `get_draft`。\n   - `list_artifacts` 里的底稿条目是任务卡片（含 status），不是全文。\n6. 要看原视频用 `download_video`；要看 Studio 产物用 `list_artifacts` 然后 `get_artifact`。两者只给签名 `download_url` 和 `expires_at`。不要期望工具结果里有视频、图片或 PPT 的二进制。\n\n可选：建本后可用 `get_job` 查看封面任务，或 `get_notebook` 看 `cover_url`；封面失败常见原因是未配置封面文生图模型。思维导图和幻灯片的生成留在后续版本。\n\n## 调用方式\n\nMCP：`POST /mcp`，方法 `tools/call`，`name` 与下表相同，参数放在 `arguments`。\n\nREST：`POST /agent/v1/tools/<name>`，JSON 正文就是参数。请求头：\n\n```\nAuthorization: Bearer <你的 Agent Token>\n```\n\nToken 在网页「设置 → Agent 接入」创建，明文只显示一次，可撤销，可设 30 天或 90 天过期。权限：\n\n- `read`：搜索与全部读取\n- `write_notebook`：`create_notebook`、`add_url`（也能看 `get_readiness`）\n- `write_generate`：`generate_cover`、`generate_draft`\n\n## 工具\n\n{{TOOLS}}\n\n## 参数备忘\n\n- `create_notebook`：`name`（也接受 `title`）、`description`\n- `generate_cover`：`notebook_id`，可选覆盖 `title` / `description`\n- `add_url`：`notebook_id`、`url`\n- `get_readiness` / `get_notebook` / `get_draft` / `list_artifacts`：`notebook_id`\n- `get_source` / `get_video` / `download_video` / `get_subtitle`：`video_id`\n- `generate_draft`：`notebook_id`；可选 `strategy_id`、`video_ids`、`note_ids`、`language`（中文或 English）、`focus`。调用前必须 `ready_for_draft=true`\n- `get_job`：`job_id`\n- `get_artifact`：`artifact_id`\n- `search`：`query`，可选 `platforms`（youtube、bilibili）和 `limit_per_platform`\n- `list_notebooks`：可选 `search` 或 `q`、`page`、`size`\n'

INSTALL_TEMPLATE = '#!/bin/sh\n# 视频笔记 Agent 安装脚本。\n# 不向任何客户端（Cursor / WorkBuddy / Claude Code 等）硬写 mcp.json。\n# 下载 Skill 缓存，打印 MCP JSON 与指令，由「正在执行本脚本的 Agent」按本客户端规范自装。\nset -eu\nTOKEN=""\nwhile [ $# -gt 0 ]; do\n  case "$1" in\n    --token)\n      TOKEN="${2:-}"\n      shift 2\n      ;;\n    --token=*)\n      TOKEN="${1#--token=}"\n      shift\n      ;;\n    -h|--help)\n      echo "用法: curl -fsSL __ORIGIN__/agent/install.sh | sh -s -- --token vn_agent_…"\n      echo "输出 MCP JSON + Skill 路径/URL，请当前 Agent 自行注册到本客户端；不写入 ~/.cursor/mcp.json 等固定路径。"\n      exit 0\n      ;;\n    *)\n      echo "未知参数: $1" >&2\n      exit 2\n      ;;\n  esac\ndone\nif [ -z "$TOKEN" ]; then\n  echo "用法: curl -fsSL __ORIGIN__/agent/install.sh | sh -s -- --token vn_agent_…" >&2\n  exit 1\nfi\ncase "$TOKEN" in\n  vn_agent_*) ;;\n  *)\n    echo "Token 应以 vn_agent_ 开头。不要使用登录 JWT。" >&2\n    exit 1\n    ;;\nesac\nORIGIN="__ORIGIN__"\nDEST="${VIDEO_NOTEBOOK_HOME:-$HOME/.video-notebook}"\nmkdir -p "$DEST"\ncurl -fsSL "$ORIGIN/agent/skill.md" -o "$DEST/skill.md"\nif grep -F -- "$TOKEN" "$DEST/skill.md" >/dev/null 2>&1; then\n  echo "拒绝安装：skill.md 里出现了 Token" >&2\n  exit 1\nfi\numask 077\nFRAG="$DEST/mcp.fragment.json"\nif command -v python3 >/dev/null 2>&1; then\n  MCP_JSON="$(\n    VN_TOKEN="$TOKEN" VN_ORIGIN="$ORIGIN" VN_DEST="$DEST" python3 - <<\'PY\'\nimport json\nimport os\nfrom pathlib import Path\n\ntoken = os.environ["VN_TOKEN"]\norigin = os.environ["VN_ORIGIN"].rstrip("/")\ndest = Path(os.environ["VN_DEST"])\nserver = {\n    "url": origin + "/mcp",\n    "headers": {"Authorization": "Bearer " + token},\n}\nfragment = {"mcpServers": {"video-notebook": server}}\nfrag_path = dest / "mcp.fragment.json"\nfrag_path.write_text(json.dumps(fragment, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")\nos.chmod(frag_path, 0o600)\nprint(json.dumps(fragment, ensure_ascii=False, indent=2))\nPY\n  )"\nelse\n  MCP_JSON=$(printf "%s\\n" "{\\"mcpServers\\":{\\"video-notebook\\":{\\"url\\":\\"${ORIGIN}/mcp\\",\\"headers\\":{\\"Authorization\\":\\"Bearer ${TOKEN}\\"}}}}")\n  printf "%s\\n" "$MCP_JSON" > "$FRAG"\n  chmod 600 "$FRAG"\nfi\n\ncat <<EOF\n=== video-notebook agent install ===\nstatus: ready_for_agent_self_install\norigin: ${ORIGIN}\nskill_url: ${ORIGIN}/agent/skill.md\nskill_path: ${DEST}/skill.md\nskill_suggested_dir_name: video-notebook\nmcp_url: ${ORIGIN}/mcp\nmcp_server_name: video-notebook\nmcp_fragment_path: ${FRAG}\ntoken_in_skill: no\n\n--- BEGIN MCP_JSON ---\n${MCP_JSON}\n--- END MCP_JSON ---\n\n## 给正在执行本脚本的 Agent（必做）\n\n1. 把上面 MCP_JSON 注册到**你当前客户端**的 MCP 配置（按本客户端规范合并 mcpServers.video-notebook；不要假定是 Cursor，也不要只写 ~/.cursor/mcp.json）。\n2. 把 Skill 装进**你当前客户端**的 skills 目录：建议目录名 video-notebook，文件名按客户端要求用 SKILL.md 或 skill.md。内容来自 skill_path 或重新下载 skill_url。\n3. Token 只保留在 MCP 的 Authorization: Bearer（或客户端等价密钥位）。禁止写入 Skill、禁止提交仓库、禁止在回复里完整回显 Token。\n4. 注册后按客户端需要重载/新建会话，确认能看到 video-notebook 工具（如 create_notebook、search、add_url、get_readiness、generate_draft）。\n\n## 人工兜底（仅当 Agent 无法写配置时）\n\n把 MCP_JSON 粘贴进当前客户端的「配置 MCP / MCP servers」界面；再把 skill_path 对应内容导入或复制到该客户端的 skills 目录。本地还存了一份片段：mcp_fragment_path（含 Token，勿外传）。\nEOF\n'

LLMS_INTRO = '# 视频笔记\n\n> 给编程 Agent 用的门面。不要把整站 /api 和登录 JWT 交给 Agent。\n\n认证：`Authorization: Bearer vn_agent_…`（在设置页创建，明文只显示一次）。登录 JWT 会被拒绝。\n\n- [Skill]({origin}/agent/skill.md)：工具链。默认先搜索并停步等人确认；仅在用户明确要求时入库与生成底稿（须全部字幕就绪）。\n- [MCP]({origin}/mcp)：HTTP JSON-RPC，工具名与 REST 相同。\n- [REST]({origin}/agent/v1/tools/<name>)：POST JSON 参数。\n- [OpenAPI]({origin}/agent/openapi.json)\n- [安装]({origin}/agent/install.sh)：`curl -fsSL …/agent/install.sh | sh -s -- --token <TOKEN>`。脚本下载 Skill 缓存并打印 MCP JSON；由**正在执行的 Agent**按本客户端规范自装 Skill 与 MCP，不硬写 ~/.cursor/mcp.json。Token 不写入 Skill。\n\n媒体只通过签名 URL 下载，工具结果里没有二进制。\n\n## 工具\n'

def skill_markdown() -> str:
    from app.agent.facade import TOOLS

    lines = [f"- `{tool.name}`：{tool.description}" for tool in TOOLS]
    return SKILL_BODY.replace("{{TOOLS}}", "\n".join(lines)).strip() + "\n"


def llms_text(origin: str) -> str:
    from app.agent.facade import TOOLS

    base = origin.rstrip("/")
    body = LLMS_INTRO.format(origin=base)
    lines = [f"- {tool.name}: {tool.description}" for tool in TOOLS]
    return body + "\n".join(lines) + "\n"


def install_script(origin: str) -> str:
    safe = origin.rstrip("/")
    forbidden = set(['"', "'", "`", chr(92), chr(10), chr(13), "$"])
    if any(char in safe for char in forbidden):
        safe = "http://127.0.0.1:8000"
    return INSTALL_TEMPLATE.replace("__ORIGIN__", safe)


def openapi_document(origin: str) -> dict:
    from app.agent.facade import TOOLS

    paths = {}
    for tool in TOOLS:
        paths[f"/agent/v1/tools/{tool.name}"] = {
            "post": {
                "operationId": tool.name,
                "summary": tool.description,
                "tags": ["agent"],
                "security": [{"agentToken": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": tool.model.model_json_schema()}
                    },
                },
                "responses": {"200": {"description": "工具结果（JSON，不含媒体二进制）"}},
            }
        }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "视频笔记 Agent API",
            "version": "0.1.0",
            "description": "Bearer vn_agent_ Token。不要使用登录 JWT。",
        },
        "servers": [{"url": origin.rstrip("/")}],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "agentToken": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "vn_agent",
                }
            }
        },
    }
