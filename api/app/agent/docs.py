"""公开的 llms.txt、Skill 与安装脚本。Skill 正文不包含长期 Token。"""
from __future__ import annotations

SKILL_BODY = """# 视频笔记 Skill

把 Claude Code、Workbuddy 或 Cursor 接到「视频笔记」。用 MCP 工具按下面的顺序操作，不要调用网站的 `/api` 登录接口，也不要使用手机号登录 JWT。

Token 只放在 MCP 配置的 `Authorization: Bearer` 里。不要把 Token 写进本 Skill，不要提交到仓库。安装脚本会下载本文件并单独注册 MCP。

## 推荐链路

1. `create_notebook`，传入 `name` 和可选 `description`。同步拿到 `notebook_id`、`name`、`description`、`cover_url`。封面还没好时 `cover_url` 为 null，同时返回 `cover_job_id`。
2. 用 `get_job` 轮询 `cover_job_id`，或用 `get_notebook` 看 `cover_url`。封面大约 60 秒内完成；失败时 `get_job` 的 `error` 会说明原因（常见是还没配置封面文生图模型）。
3. 需要找视频时调用 `search`，从结果里取 `url`。
4. `add_url` 把链接放进笔记本。它只建记录并开始抓取，不会返回视频文件。
5. 轮询 `get_readiness`，直到 `ready_for_draft` 为 true（每条来源的字幕都就绪）。抓取中或字幕失败时不要调用 `generate_draft`。
6. `generate_draft` 返回 `job_id`。用 `get_job` 等到 `succeeded`，再用 `get_draft` 读正文。
7. 要看原视频用 `download_video`，要看 Studio 产物用 `list_artifacts` 然后 `get_artifact`。两者只给签名 `download_url` 和 `expires_at`。不要期望工具结果里有视频、图片或 PPT 的二进制。

思维导图和幻灯片的生成留在后续版本。已经在网页里生成的产物仍可以用 `list_artifacts` / `get_artifact` 读取。

## 调用方式

MCP：`POST /mcp`，方法 `tools/call`，`name` 与下表相同，参数放在 `arguments`。

REST：`POST /agent/v1/tools/<name>`，JSON 正文就是参数。请求头：

```
Authorization: Bearer <你的 Agent Token>
```

Token 在网页「设置 → Agent 接入」创建，明文只显示一次，可撤销，可设 30 天或 90 天过期。权限：

- `read`：搜索与全部读取
- `write_notebook`：`create_notebook`、`add_url`（也能看 `get_readiness`）
- `write_generate`：`generate_cover`、`generate_draft`

## 工具

{{TOOLS}}

## 参数备忘

- `create_notebook`：`name`（也接受 `title`）、`description`
- `generate_cover`：`notebook_id`，可选覆盖 `title` / `description`
- `add_url`：`notebook_id`、`url`
- `get_readiness` / `get_notebook` / `get_draft` / `list_artifacts`：`notebook_id`
- `get_source` / `get_video` / `download_video` / `get_subtitle`：`video_id`
- `generate_draft`：`notebook_id`；可选 `strategy_id`、`video_ids`、`note_ids`、`language`（中文或 English）、`focus`
- `get_job`：`job_id`
- `get_artifact`：`artifact_id`
- `search`：`query`，可选 `platforms`（youtube、bilibili）和 `limit_per_platform`
- `list_notebooks`：可选 `search` 或 `q`、`page`、`size`
"""

INSTALL_TEMPLATE = r"""#!/bin/sh
# 视频笔记 Agent 安装脚本。Token 只写入本机 MCP 配置，不写入 skill.md。
set -eu
TOKEN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --token)
      TOKEN="${2:-}"
      shift 2
      ;;
    --token=*)
      TOKEN="${1#--token=}"
      shift
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 2
      ;;
  esac
done
if [ -z "$TOKEN" ]; then
  echo "用法: curl -fsSL __ORIGIN__/agent/install.sh | sh -s -- --token vn_agent_…" >&2
  exit 1
fi
case "$TOKEN" in
  vn_agent_*) ;;
  *)
    echo "Token 应以 vn_agent_ 开头。不要使用登录 JWT。" >&2
    exit 1
    ;;
esac
ORIGIN="__ORIGIN__"
DEST="${VIDEO_NOTEBOOK_HOME:-$HOME/.video-notebook}"
mkdir -p "$DEST"
curl -fsSL "$ORIGIN/agent/skill.md" -o "$DEST/skill.md"
if grep -F -- "$TOKEN" "$DEST/skill.md" >/dev/null 2>&1; then
  echo "拒绝安装：skill.md 里出现了 Token" >&2
  exit 1
fi
umask 077
if command -v python3 >/dev/null 2>&1; then
  VN_TOKEN="$TOKEN" VN_ORIGIN="$ORIGIN" VN_DEST="$DEST" python3 - <<'PY'
import json
import os
from pathlib import Path

token = os.environ["VN_TOKEN"]
origin = os.environ["VN_ORIGIN"].rstrip("/")
dest = Path(os.environ["VN_DEST"])
server = {
    "url": origin + "/mcp",
    "headers": {"Authorization": "Bearer " + token},
}
fragment = {"mcpServers": {"video-notebook": server}}
frag_path = dest / "mcp.fragment.json"
frag_path.write_text(json.dumps(fragment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.chmod(frag_path, 0o600)
cursor = Path.home() / ".cursor" / "mcp.json"
cursor.parent.mkdir(parents=True, exist_ok=True)
data = {}
if cursor.exists():
    try:
        loaded = json.loads(cursor.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = {}
servers = data.get("mcpServers")
if not isinstance(servers, dict):
    servers = {}
servers["video-notebook"] = server
data["mcpServers"] = servers
cursor.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.chmod(cursor, 0o600)
print("已安装 Skill（不含 Token）：", dest / "skill.md")
print("已注册 Cursor MCP：", cursor)
print("Token 只写在 MCP 配置里。")
PY
else
  printf '%s\n' "{\"mcpServers\":{\"video-notebook\":{\"url\":\"${ORIGIN}/mcp\",\"headers\":{\"Authorization\":\"Bearer ${TOKEN}\"}}}}" > "$DEST/mcp.fragment.json"
  chmod 600 "$DEST/mcp.fragment.json"
  echo "已安装 Skill（不含 Token）：$DEST/skill.md"
  echo "已写入 MCP 片段：$DEST/mcp.fragment.json"
  echo "请把片段合并进 Cursor 或 Claude Code 的 MCP 配置。不要把 Token 写进 Skill。"
fi
"""

LLMS_INTRO = """# 视频笔记

> 给编程 Agent 用的门面。不要把整站 /api 和登录 JWT 交给 Agent。

认证：`Authorization: Bearer vn_agent_…`（在设置页创建，明文只显示一次）。登录 JWT 会被拒绝。

- [Skill]({origin}/agent/skill.md)：工具链。先创建笔记本，再等封面；加链接后等字幕就绪，再生成底稿。
- [MCP]({origin}/mcp)：HTTP JSON-RPC，工具名与 REST 相同。
- [REST]({origin}/agent/v1/tools/<name>)：POST JSON 参数。
- [OpenAPI]({origin}/agent/openapi.json)
- [安装]({origin}/agent/install.sh)：`curl -fsSL …/agent/install.sh | sh -s -- --token <TOKEN>`。Token 写入本机 MCP 配置，不写入 Skill。

媒体只通过签名 URL 下载，工具结果里没有二进制。

## 工具
"""


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
    if any(char in safe for char in "\"'`\\\n\r$"):
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
