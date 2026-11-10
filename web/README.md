# 影知 · PC 网页

Vite 6 + React 18 + TypeScript + Tailwind 3 + shadcn/ui + React Router 6 + TanStack Query 5。

产品能力见 [功能说明 · PC](../docs/features.md#pc)。本地如何把 API 和网页一起跑起来，见 [本地部署与开发](../docs/development.md)。

## 开发

```bash
cd web
npm install
npm run dev
# 默认 http://localhost:5173
```

Vite 已把浏览器的 `/api/*` 代理到 `127.0.0.1:8000`。详见 [`vite.config.ts`](./vite.config.ts)。
