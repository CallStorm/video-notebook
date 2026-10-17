/**
 * 简易 fetch wrapper：
 * - 默认 baseURL = `/api`（vite proxy 已透传到 127.0.0.1:8000）
 * - 失败统一抛 ApiError，方便 TanStack Query / ErrorBoundary 捕获
 *
 * 故意不做「401 → 自动登出 + 跳 /login」：与 RequireAuth 配合会形成死循环
 * （/admin → onUnauthorized → /login → /admin → ...）。改为把 401 暴露给 UI
 * 让用户主动 logout / 重新登录。
 */
import { authedHeaders } from "@/lib/auth";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ApiInit extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** 不返回包装，直接读 Response */
  raw?: boolean;
  access?: string | null;
}

export async function api<T = unknown>(
  path: string,
  init: ApiInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");
  const auth = authedHeaders(init.access ?? null);
  for (const [k, v] of Object.entries(auth)) {
    headers.set(k, v);
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers,
    body:
      init.body === undefined
        ? undefined
        : init.body instanceof FormData
          ? init.body
          : JSON.stringify(init.body),
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      /* empty */
    }
    const code = (payload as { code?: string } | null)?.code ?? `http_${response.status}`;
    const message =
      (payload as { message?: string } | null)?.message ?? response.statusText;
    throw new ApiError(response.status, code, message, payload);
  }

  if (init.raw) {
    return response as unknown as T;
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
