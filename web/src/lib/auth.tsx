/**
 * 登录态管理（v1 简化版：localStorage 存 token）。
 * 真要持久 SSO/OAuth 等 v2 再说。
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
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

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(() => readPersisted());
  const navigate = useNavigate();

  useEffect(() => {
    persist(state);
  }, [state]);

  const logout = useCallback(() => {
    clear();
    setState({ user: null, access: null, refresh: null });
    // 把跳转推到下个 tick，避免在 React 渲染中调用 navigate
    setTimeout(() => navigate("/login", { replace: true }), 0);
  }, [navigate]);

  const login = useCallback((next: AuthState) => setState(next), []);
  const setAccess = useCallback((access: string) => {
    setState((prev) => ({ ...prev, access }));
  }, []);

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
 * 误以为没设上。plain object 走 fetch 的 HeadersInit 也能被识别。
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
