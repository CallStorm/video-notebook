# 对外 Agent 接入说明

面向 WorkBuddy、Claude Code、Cursor 等客户端，用 Agent Token + Skill + MCP 操作影知（视频搜索、建笔记本、加片、知识底稿），**不要**把整站 `/api` 或登录 JWT 交给 Agent。

详细步骤与截图见 [功能说明 · 对外 Agent](features.md#对外-agentworkbuddy--claude-code--cursor-等)。

## 推荐对话节奏

1. 后台创建 Token → 把安装命令发给当前客户端 Agent，由其自装 Skill / MCP。
2. 只提「搜某某主题」时：Agent 只搜索并汇总，然后停下。
3. 你点名要入库的链接后：再创建笔记本并 `add_url`，系统自动抓取字幕。
4. 全部来源字幕就绪后，你再说「生成底稿」：才调用 `generate_draft`。

后端会硬拦截：笔记本内只要还有抓取中或字幕未就绪的来源，就不能生成底稿。
