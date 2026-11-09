# 影知 Videnote · 微信小程序

Taro 4 + React + TypeScript，目标平台 weapp。

## 开发

```bash
cd miniapp
npm install
npm run build:weapp
```

用微信开发者工具打开本目录（`project.config.json` 的 `miniprogramRoot` 指向 `dist/`）。

开发期请关闭「校验合法域名」；`project.private.config.json` 已默认 `urlCheck: false`。

## 连接配置

小程序内「连接设置 / 我的」填写：

- Server URL：手机/模拟器能访问的后端，如 `http://192.168.x.x:8000`（不要用 localhost）
- Agent Token：网页设置页创建，`vn_agent_` 开头；请求头 `Authorization: Bearer …`，勿写入 URL/日志

接口：`POST {server}/agent/v1/tools/<name>`

## CLI 打开 / 预览

```bat
"C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat" open --project "C:\Users\Administrator\Desktop\video-notebook\miniapp"
"C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat" preview --project "C:\Users\Administrator\Desktop\video-notebook\miniapp" --qr-format image --qr-output "C:\Users\Administrator\Desktop\video-notebook\miniapp\preview-qr.png"
```

首次需在开发者工具扫码登录；不要自动 submit 审核。

## 产品说明

抖音收集演示与截图见 [docs/miniapp.md](../docs/miniapp.md)。
