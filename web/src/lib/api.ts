/**
 * 简版 fetch wrapper：
 * - 默认 baseURL = `/api`（vite proxy 已透传到 127.0.0.1:8000）
 * - 失败统一抛 ApiError，方便 TanStack Query / ErrorBoundary 捕获
 * - 401：先用 refresh 换新 access（单飞），成功则重试原请求一次；
 *   refresh 也失败则清本地会话并跳转 /login（保留 next）
 */
import {
  authedHeaders,
  getAuthSessionBridge,
  readAuthSnapshot,
} from "@/lib/auth";

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
  /** 不返回包装，直接拿 Response */
  raw?: boolean;
  access?: string | null;
  /** 内部：401 refresh 后重试标记，避免死循环 */
  _retried?: boolean;
}

function isAuthPath(path: string): boolean {
  return (
    path.startsWith("/auth/login") ||
    path.startsWith("/auth/refresh") ||
    path.startsWith("/auth/logout")
  );
}

let refreshInFlight: Promise<string | null> | null = null;

/**
 * 用 refresh token 换一对新 token。并发 401 共享同一次 refresh。
 * 成功返回新 access；失败返回 null（调用方应清会话）。
 */
export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const snap = readAuthSnapshot();
    if (!snap.refresh) return null;

    try {
      const response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh: snap.refresh }),
      });
      if (!response.ok) return null;
      const data = (await response.json()) as {
        access?: string;
        refresh?: string;
      };
      if (!data.access || !data.refresh) return null;
      const bridge = getAuthSessionBridge();
      if (bridge) {
        bridge.applyTokens(data.access, data.refresh);
      } else if (typeof window !== "undefined") {
        const next = { ...snap, access: data.access, refresh: data.refresh };
        window.localStorage.setItem("vnb.auth.v1", JSON.stringify(next));
      }
      return data.access;
    } catch {
      return null;
    }
  })().finally(() => {
    refreshInFlight = null;
  });

  return refreshInFlight;
}

function clearSessionAndRedirectToLogin(): void {
  const bridge = getAuthSessionBridge();
  if (bridge) {
    bridge.clearSessionAndRedirectToLogin();
    return;
  }
  if (typeof window !== "undefined") {
    window.localStorage.removeItem("vnb.auth.v1");
    const next = `${window.location.pathname}${window.location.search}`;
    const target = next.startsWith("/login")
      ? "/login"
      : `/login?next=${encodeURIComponent(next || "/")}`;
    window.location.assign(target);
  }
}

/**
 * 供裸 fetch（如 SSE）在收到 401 时复用：尝试 refresh，成功返回新 access；
 * 失败则清会话跳登录并返回 null。
 */
export async function recoverAccessAfter401(): Promise<string | null> {
  const access = await refreshAccessToken();
  if (access) return access;
  clearSessionAndRedirectToLogin();
  return null;
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

  const access =
    init.access !== undefined && init.access !== null
      ? init.access
      : readAuthSnapshot().access;
  const auth = authedHeaders(access ?? null);
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
    const code =
      (payload as { code?: string } | null)?.code ?? `http_${response.status}`;
    const message =
      (payload as { message?: string } | null)?.message ?? response.statusText;

    if (response.status === 401 && !isAuthPath(path)) {
      if (!init._retried) {
        const newAccess = await refreshAccessToken();
        if (newAccess) {
          return api<T>(path, { ...init, access: newAccess, _retried: true });
        }
      }
      clearSessionAndRedirectToLogin();
    }

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
