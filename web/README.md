# video-notebook · Web

Vite 6 + React 18 + TypeScript + Tailwind 3 + shadcn/ui (new-york) + React Router 6 + TanStack Query 5.

## 开发

```bash
cd web
npm install
npm run dev
# 默认 http://localhost:5173
```

Vite proxy 已配：浏览器访问 `/api/*` 转发到 `127.0.0.1:8000`（uvicorn 起的 api）。
详见 [`vite.config.ts`](./vite.config.ts)。

## 目录速览

```
src/
├── main.tsx              # Vite 入口
├── App.tsx               # QueryClientProvider
├── router.tsx            # 路由
├── styles/globals.css    # Tailwind + 设计令牌
├── lib/
│   ├── api.ts            # fetch 封装 + ApiError
│   └── utils.ts          # cn
├── components/
│   ├── ui/               # shadcn: button / card / input
│   ├── layout.tsx
│   ├── login-form.tsx
│   └── health-gate.tsx
└── pages/
    ├── home.tsx
    ├── login.tsx
    ├── discover.tsx
    ├── admin.tsx
    └── notebook-placeholder.tsx
```

## 后续阶段计划
详见仓库根 [`docs/superpowers/specs/2026-10-16-video-notebook-design.md`](../docs/superpowers/specs/2026-10-16-video-notebook-design.md)。
