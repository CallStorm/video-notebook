import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Bell,
  Copy,
  KeyRound,
  LayoutGrid,
  Search,
  TriangleAlert,
  UserRound,
} from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { UserMenu } from "@/components/user-menu";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Section = "account" | "agent" | "notify";

interface AgentToken {
  id: number;
  name: string;
  scopes: string[];
  created_at: string | null;
  expires_at: string | null;
  status: "active" | "revoked" | "expired";
}

interface CreatedToken {
  token: AgentToken;
  plaintext: string;
  install_command: string;
  mcp_url: string;
  skill_url: string;
  llms_url: string;
}

interface ConnectInfo {
  mcp_url: string;
  skill_url: string;
  llms_url: string;
}

const SCOPE_OPTIONS = [
  { id: "read", label: "读取" },
  { id: "write_notebook", label: "新建与加链接" },
  { id: "write_generate", label: "触发生成" },
] as const;

function sectionFrom(params: URLSearchParams): Section {
  const raw = params.get("section");
  if (raw === "account" || raw === "notify") return raw;
  return "agent";
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const normalized = iso.includes("T") ? iso : iso.replace(" ", "T");
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return iso.slice(0, 16);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

async function copyText(text: string): Promise<void> {
  try {
    await Promise.race([
      navigator.clipboard.writeText(text),
      new Promise((_, reject) => {
        window.setTimeout(() => reject(new Error("clipboard timeout")), 800);
      }),
    ]);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "true");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
}

export default function SettingsPage() {
  const { access, logout } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const section = sectionFrom(params);
  const [query, setQuery] = useState("");
  const token = access ?? "";

  return (
    <div className="page-ambient min-h-screen">
      <AppHeader
        active="mine"
        afterNav={
          <form
            className="flex justify-end"
            onSubmit={(event) => {
              event.preventDefault();
              const q = query.trim();
              navigate(q ? `/?search=${encodeURIComponent(q)}` : "/");
            }}
          >
            <div className="relative w-full max-w-xs">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索笔记本"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="h-9 rounded-full border border-border/70 bg-card/90 pl-9 shadow-soft"
              />
            </div>
          </form>
        }
        rightSlot={
          <>
            <Button
              type="button"
              size="icon"
              variant="outline"
              className="hidden h-9 w-9 rounded-full md:inline-flex"
              title="我的笔记本"
              onClick={() => navigate("/")}
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <UserMenu
              onLogout={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            />
          </>
        }
      />

      <div className="flex w-full items-start gap-4 px-6 py-6 lg:px-8">
        <aside className="w-52 shrink-0 rounded-2xl border border-border/70 bg-card p-3 shadow-soft">
          <nav className="space-y-1" aria-label="设置">
            <SideItem
              active={section === "account"}
              icon={<UserRound className="h-4 w-4" />}
              label="账号"
              onClick={() => setParams({ section: "account" })}
            />
            <SideItem
              active={section === "agent"}
              icon={<KeyRound className="h-4 w-4" />}
              label="Agent 接入"
              onClick={() => setParams({ section: "agent" })}
            />
            <SideItem
              active={section === "notify"}
              icon={<Bell className="h-4 w-4" />}
              label="通知"
              onClick={() => setParams({ section: "notify" })}
            />
          </nav>
        </aside>

        <section className="min-w-0 flex-1">
          {section === "account" ? <AccountPanel token={token} /> : null}
          {section === "agent" ? <AgentPanel token={token} /> : null}
          {section === "notify" ? <NotifyPanel /> : null}
        </section>
      </div>
    </div>
  );
}

function SideItem({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium transition " +
        (active
          ? "bg-primary text-primary-foreground shadow-soft"
          : "text-foreground/80 hover:bg-muted")
      }
    >
      {icon}
      {label}
    </button>
  );
}

function AccountPanel({ token }: { token: string }) {
  const { user, access, refresh, login } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const saveName = useMutation({
    mutationFn: () =>
      api<{ name: string }>("/users/me", {
        method: "PATCH",
        access: token,
        body: { name: name.trim() },
      }),
    onSuccess: (data) => {
      if (user && access && refresh) {
        login({
          user: { ...user, name: data.name },
          access,
          refresh,
        });
      }
      setError(null);
      setMessage("名称已保存");
    },
    onError: (err) => {
      setMessage(null);
      setError(err instanceof ApiError ? err.message : "保存失败");
    },
  });

  const changePassword = useMutation({
    mutationFn: () =>
      api("/users/me/change_password", {
        method: "POST",
        access: token,
        body: { old_password: oldPassword, new_password: newPassword },
      }),
    onSuccess: () => {
      setOldPassword("");
      setNewPassword("");
      setError(null);
      setMessage("密码已更新");
    },
    onError: (err) => {
      setMessage(null);
      setError(err instanceof ApiError ? err.message : "修改失败");
    },
  });

  return (
    <div className="rounded-2xl border border-border/70 bg-card p-6 shadow-soft">
      <h1 className="text-xl font-semibold">账号</h1>
      <p className="mt-1 text-sm text-muted-foreground">登录身份与密码。Agent 不要使用这里的登录 JWT。</p>
      <div className="mt-6 max-w-md space-y-4">
        <label className="block text-sm">
          <span className="mb-1.5 block text-muted-foreground">手机号</span>
          <Input value={user?.phone ?? ""} readOnly />
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block text-muted-foreground">名称</span>
          <Input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <Button
          type="button"
          disabled={!name.trim() || saveName.isPending}
          onClick={() => saveName.mutate()}
        >
          保存名称
        </Button>
        <div className="border-t border-border/70 pt-4">
          <div className="mb-3 text-sm font-medium">修改密码</div>
          <div className="space-y-3">
            <Input
              type="password"
              placeholder="当前密码"
              value={oldPassword}
              onChange={(event) => setOldPassword(event.target.value)}
            />
            <Input
              type="password"
              placeholder="新密码（至少 8 位）"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <Button
              type="button"
              variant="outline"
              disabled={!oldPassword || newPassword.length < 8 || changePassword.isPending}
              onClick={() => changePassword.mutate()}
            >
              更新密码
            </Button>
          </div>
        </div>
        {message ? <p className="text-sm text-emerald-600">{message}</p> : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </div>
    </div>
  );
}

function NotifyPanel() {
  return (
    <div className="rounded-2xl border border-border/70 bg-card p-6 shadow-soft">
      <h1 className="text-xl font-semibold">通知</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        通知偏好还没开放。生成完成、抓取失败等提醒会在后续版本出现在这里。
      </p>
    </div>
  );
}

function AgentPanel({ token }: { token: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [revealed, setRevealed] = useState<CreatedToken | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const tokens = useQuery({
    queryKey: ["agent-tokens"],
    queryFn: () => api<{ items: AgentToken[] }>("/users/me/agent-tokens", { access: token }),
    enabled: !!token,
  });
  const connect = useQuery({
    queryKey: ["agent-connect"],
    queryFn: () => api<ConnectInfo>("/users/me/agent-connect", { access: token }),
    enabled: !!token,
  });

  const revoke = useMutation({
    mutationFn: (id: number) =>
      api<AgentToken>(`/users/me/agent-tokens/${id}/revoke`, {
        method: "POST",
        access: token,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agent-tokens"] }),
  });

  const items = tokens.data?.items ?? [];
  const docs = {
    mcp_url: revealed?.mcp_url || connect.data?.mcp_url || "",
    skill_url: revealed?.skill_url || connect.data?.skill_url || "",
    llms_url: revealed?.llms_url || connect.data?.llms_url || "",
  };

  async function onCopy(key: string, text: string) {
    await copyText(text);
    setCopied(key);
    window.setTimeout(() => setCopied((current) => (current === key ? null : current)), 1600);
  }

  return (
    <div className="rounded-2xl border border-border/70 bg-card p-6 shadow-soft">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Agent 接入</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            把安装命令发给当前 Agent；由它按本客户端规范自装 Skill 与 MCP（不硬写 Cursor）
          </p>
        </div>
        {items.length > 0 ? (
          <Button type="button" onClick={() => setOpen(true)}>
            创建 Token
          </Button>
        ) : null}
      </div>

      {tokens.isLoading ? (
        <p className="py-16 text-center text-sm text-muted-foreground">加载中…</p>
      ) : null}
      {tokens.error instanceof ApiError ? (
        <p className="mt-4 text-sm text-destructive">{tokens.error.message}</p>
      ) : null}

      {!tokens.isLoading && items.length === 0 && !revealed ? (
        <div className="flex min-h-[420px] flex-col">
          <div className="flex flex-1 flex-col items-center justify-center py-10">
            <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <KeyRound className="h-8 w-8" />
            </div>
            <p className="mb-4 text-base font-medium">还没有 Agent Token</p>
            <Button type="button" onClick={() => setOpen(true)}>
              创建 Token
            </Button>
          </div>
          <Hints />
        </div>
      ) : null}

      {(items.length > 0 || revealed) && !tokens.isLoading ? (
        <div className="mt-5 space-y-4">
          {revealed ? (
            <>
              <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <TriangleAlert className="h-4 w-4 shrink-0" />
                Token 仅显示一次，请立即复制
              </div>
              <div className="rounded-xl border border-border/70 p-4">
                <div className="text-sm font-medium">Token 信息</div>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <code className="rounded-md bg-muted px-2 py-1 font-mono text-sm">
                    {revealed.plaintext}
                  </code>
                  <Button type="button" size="sm" onClick={() => onCopy("token", revealed.plaintext)}>
                    <Copy className="h-3.5 w-3.5" />
                    {copied === "token" ? "已复制" : "复制"}
                  </Button>
                </div>
              </div>
              <div className="rounded-xl border border-border/70 p-4">
                <div className="mb-3 text-sm font-medium">一键接入</div>
                <pre className="overflow-x-auto rounded-lg bg-zinc-950 px-4 py-3 font-mono text-xs text-zinc-100">
                  {revealed.install_command}
                </pre>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button type="button" size="sm" onClick={() => onCopy("install", revealed.install_command)}>
                    {copied === "install" ? "已复制" : "复制安装命令"}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => docs.mcp_url && onCopy("mcp", docs.mcp_url)}
                  >
                    {copied === "mcp" ? "已复制" : "复制 MCP 地址"}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => docs.skill_url && window.open(docs.skill_url, "_blank", "noopener")}
                  >
                    打开说明
                  </Button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-sm text-primary">
                  <DocLink href={docs.llms_url} label="llms.txt" />
                  <span className="text-muted-foreground">·</span>
                  <DocLink href={docs.skill_url} label="skill.md" />
                  <span className="text-muted-foreground">·</span>
                  <DocLink href={docs.mcp_url} label="MCP" />
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-wrap gap-2 text-sm text-primary">
              <DocLink href={docs.llms_url} label="llms.txt" />
              <span className="text-muted-foreground">·</span>
              <DocLink href={docs.skill_url} label="skill.md" />
              <span className="text-muted-foreground">·</span>
              <DocLink href={docs.mcp_url} label="MCP" />
            </div>
          )}

          <div className="overflow-x-auto rounded-xl border border-border/70">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-muted/40 text-left text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">名称</th>
                  <th className="px-4 py-3 font-medium">创建时间</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-t border-border/70">
                    <td className="px-4 py-3">{item.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{formatDateTime(item.created_at)}</td>
                    <td className="px-4 py-3">
                      <TokenStatus status={item.status} />
                    </td>
                    <td className="px-4 py-3">
                      {item.status === "active" ? (
                        <button
                          type="button"
                          className="text-destructive hover:underline disabled:opacity-50"
                          disabled={revoke.isPending}
                          onClick={() => {
                            if (window.confirm(`撤销「${item.name}」？撤销后立即失效。`)) {
                              revoke.mutate(item.id);
                            }
                          }}
                        >
                          撤销
                        </button>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Hints />
        </div>
      ) : null}

      <CreateTokenDialog
        open={open}
        token={token}
        onClose={() => setOpen(false)}
        onCreated={(created) => {
          setRevealed(created);
          setOpen(false);
          qc.invalidateQueries({ queryKey: ["agent-tokens"] });
        }}
      />
    </div>
  );
}

function Hints() {
  return (
    <div className="text-sm text-muted-foreground">
      <div className="mb-1 font-medium text-foreground">提示：</div>
      <ul className="list-disc space-y-1 pl-5">
        <li>Token 只显示一次，可撤销；不要用登录 JWT</li>
        <li>把安装命令发给正在用的 Agent（WorkBuddy / Cursor / Claude Code 等）</li>
        <li>脚本只打印 MCP JSON 与 Skill 地址，由该 Agent 按本客户端规范自装</li>
        <li>不要指望脚本写入 ~/.cursor/mcp.json；Token 也不写入 Skill</li>
      </ul>
    </div>
  );
}

function TokenStatus({ status }: { status: AgentToken["status"] }) {
  if (status === "active") {
    return <span className="text-emerald-600">● 有效</span>;
  }
  if (status === "expired") {
    return <span className="text-amber-600">● 已过期</span>;
  }
  return <span className="text-muted-foreground">● 已撤销</span>;
}

function DocLink({ href, label }: { href: string; label: string }) {
  if (!href) return <span>{label}</span>;
  return (
    <a href={href} target="_blank" rel="noreferrer" className="hover:underline">
      {label}
    </a>
  );
}

function CreateTokenDialog({
  open,
  token,
  onClose,
  onCreated,
}: {
  open: boolean;
  token: string;
  onClose: () => void;
  onCreated: (created: CreatedToken) => void;
}) {
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["read", "write_notebook", "write_generate"]);
  const [expires, setExpires] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName("");
    setScopes(["read", "write_notebook", "write_generate"]);
    setExpires("");
    setError(null);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const create = useMutation({
    mutationFn: () =>
      api<CreatedToken>("/users/me/agent-tokens", {
        method: "POST",
        access: token,
        body: {
          name: name.trim() || null,
          scopes,
          expires_in_days: expires ? Number(expires) : null,
        },
      }),
    onSuccess: (data) => onCreated(data),
    onError: (err) => setError(err instanceof ApiError ? err.message : "创建失败"),
  });

  if (!open) return null;

  function toggle(id: string) {
    setScopes((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-labelledby="create-agent-token-title"
        className="w-full max-w-lg rounded-2xl bg-card p-6 shadow-xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id="create-agent-token-title" className="text-lg font-semibold">
          创建 Agent Token
        </h2>
        <form
          className="mt-5 space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (!scopes.length || create.isPending) return;
            create.mutate();
          }}
        >
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              名称 <span className="font-normal text-muted-foreground">（选填）</span>
            </span>
            <Input
              value={name}
              placeholder="例如 Workbuddy"
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <fieldset>
            <legend className="mb-2 text-sm font-medium">权限</legend>
            <div className="space-y-2">
              {SCOPE_OPTIONS.map((option) => (
                <label key={option.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-primary"
                    checked={scopes.includes(option.id)}
                    onChange={() => toggle(option.id)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">过期</span>
            <select
              className="flex h-10 w-full rounded-xl border border-input bg-background px-3 text-sm"
              value={expires}
              onChange={(event) => setExpires(event.target.value)}
            >
              <option value="">不过期</option>
              <option value="30">30 天</option>
              <option value="90">90 天</option>
            </select>
          </label>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" onClick={onClose}>
              取消
            </Button>
            <Button type="submit" disabled={!scopes.length || create.isPending}>
              {create.isPending ? "创建中…" : "创建并显示 Token"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
