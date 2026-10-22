/**
 * 登录态管理（v1 简化版：localStorage 存 token）。
 * 真要持久 SSO/OAuth 等 v2 再说。
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

export interface AuthUser {
  id: number;
  phone: string;
  name: string;
  role: "user" | "admin";
}

interface AuthState {
  user: AuthUser | null;
  access: string | null;
  refresh: string | null;
}

interface AuthContextValue extends AuthState {
  login: (state: AuthState) => void;
  logout: () => void;
  setAccess: (access: string) => void;
}

const STORAGE_KEY = "vnb.auth.v1";

function readPersisted(): AuthState {
  if (typeof window === "undefined") {
    return { user: null, access: null, refresh: null };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { user: null, access: null, refresh: null };
    return JSON.parse(raw) as AuthState;
  } catch {
    return { user: null, access: null, refresh: null };
  }
}

function persist(state: AuthState) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function clear() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}

/** api.ts 用的会话桥：读最新 token、写 refresh 结果、鉴权失败清会话并跳登录 */
export interface AuthSessionBridge {
  getSnapshot: () => AuthState;
  applyTokens: (access: string, refresh: string) => void;
  clearSessionAndRedirectToLogin: () => void;
}

let sessionBridge: AuthSessionBridge | null = null;

export function getAuthSessionBridge(): AuthSessionBridge | null {
  return sessionBridge;
}

/** 无 React 树时也能读到持久化会话（refresh 单飞 / 冷启动） */
export function readAuthSnapshot(): AuthState {
  return sessionBridge?.getSnapshot() ?? readPersisted();
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(() => readPersisted());
  const stateRef = useRef(state);
  stateRef.current = state;
  const navigate = useNavigate();

  useEffect(() => {
    persist(state);
  }, [state]);

  const logout = useCallback(() => {
    clear();
    setState({ user: null, access: null, refresh: null });
    // 把跳转推到下一 tick，避免在 React 渲染中调用 navigate
    setTimeout(() => navigate("/login", { replace: true }), 0);
  }, [navigate]);

  const login = useCallback((next: AuthState) => setState(next), []);
  const setAccess = useCallback((access: string) => {
    setState((prev) => ({ ...prev, access }));
  }, []);

  useEffect(() => {
    sessionBridge = {
      getSnapshot: () => stateRef.current,
      applyTokens: (access, refresh) => {
        setState((prev) => {
          const next = { ...prev, access, refresh };
          persist(next);
          return next;
        });
      },
      clearSessionAndRedirectToLogin: () => {
        clear();
        setState({ user: null, access: null, refresh: null });
        const next = typeof window !== "undefined"
          ? `${window.location.pathname}${window.location.search}`
          : "/";
        const target =
          next.startsWith("/login")
            ? "/login"
            : `/login?next=${encodeURIComponent(next || "/")}`;
        setTimeout(() => navigate(target, { replace: true }), 0);
      },
    };
    return () => {
      sessionBridge = null;
    };
  }, [navigate]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout, setAccess }),
    [state, login, logout, setAccess],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}

/**
 * 给 fetch 调用方用：自动带上 Authorization。
 *
 * 返回 plain object 而非 Headers 实例：Object.entries(Headers) === [] 会让调用方
 * 误以为没设上。plain object 作为 fetch 的 HeadersInit 也能被识别。
 */
export function authedHeaders(
  access: string | null,
  extra: HeadersInit = {},
): Record<string, string> {
  const out: Record<string, string> = {};
  if (extra instanceof Headers) {
    extra.forEach((v, k) => {
      out[k] = v;
    });
  } else if (Array.isArray(extra)) {
    for (const [k, v] of extra) out[k] = v;
  } else {
    Object.assign(out, extra);
  }
  if (access) {
    out["Authorization"] = `Bearer ${access}`;
  }
  return out;
}
