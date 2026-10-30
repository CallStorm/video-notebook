import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useAuth, type AuthUser } from "@/lib/auth";

interface LoginRequest {
  phone: string;
  password: string;
}

interface LoginResponse {
  access: string;
  refresh: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

async function apiLogin(body: LoginRequest): Promise<LoginResponse> {
  return api<LoginResponse>("/auth/login", { method: "POST", body });
}

export function LoginForm() {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const { login: setAuth } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/";

  const mutation = useMutation<LoginResponse, ApiError, LoginRequest>({
    mutationFn: apiLogin,
    onSuccess: (data) => {
      setAuth({ user: data.user, access: data.access, refresh: data.refresh });
      navigate(next, { replace: true });
    },
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({ phone, password });
  };

  return (
    <div className="login-glass-card w-full max-w-sm p-7">
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="phone" className="text-sm font-medium">
            手机号
          </label>
          <Input
            id="phone"
            name="phone"
            type="tel"
            autoComplete="username"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="13800000000"
            className="h-11 rounded-xl border-border/60 bg-background/55 backdrop-blur-sm"
            required
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="password" className="text-sm font-medium">
            密码
          </label>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-11 rounded-xl border-border/60 bg-background/55 backdrop-blur-sm"
            required
          />
        </div>
        {mutation.error instanceof ApiError && (
          <p className="rounded-xl bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {mutation.error.message}
          </p>
        )}
        <Button
          type="submit"
          disabled={mutation.isPending}
          className="login-btn-shine h-11 w-full rounded-full text-sm font-semibold shadow-glow"
        >
          {mutation.isPending ? "登录中…" : "登录"}
        </Button>
      </form>
    </div>
  );
}
