# 对外 Agent

能力、接入步骤和截图见 [功能说明 · 对外 Agent](features.md#对外-agent)。

Token 在网页 **设置 → Agent 接入** 创建，形如 `vn_agent_…`，放在 `Authorization: Bearer` 里。不要把登录 JWT 交给 Agent。

默认只搜索并停下。建笔记本、加链接、生成底稿都要用户再说一次。笔记本里只要还有来源在抓取或字幕未就绪，就不能开始生成底稿。
