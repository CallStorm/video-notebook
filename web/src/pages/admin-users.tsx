import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AdminEmptyState,
  AdminFieldLabel,
  AdminLoading,
  AdminSectionCard,
  AdminStatusBadge,
  AdminTableShell,
} from "@/components/admin-shell";

interface UserRow {
  id: number;
  phone: string;
  name: string;
  role: string;
  status: string;
  created_at: string;
  last_login_at: string | null;
}

interface UserListResponse {
  items: UserRow[];
  total: number;
  page: number;
  size: number;
}

async function listUsers(access: string, search: string): Promise<UserListResponse> {
  return api<UserListResponse>(`/admin/users?search=${encodeURIComponent(search)}`, { access });
}

interface CreateInput {
  phone: string;
  name: string;
  password: string;
  role: "user" | "admin";
}

async function createUser(access: string, body: CreateInput): Promise<UserRow> {
  return api<UserRow>("/admin/users", { method: "POST", body, access });
}

async function setDisabled(access: string, id: number, status: "active" | "disabled"): Promise<void> {
  await api(`/admin/users/${id}/${status === "active" ? "enable" : "disable"}`, {
    method: "POST",
    access,
    raw: true,
  });
}

const ROLE_LABEL: Record<string, string> = {
  user: "普通用户",
  admin: "管理员",
};

export function AdminUsersPage() {
  const { access } = useAuth();
  const qc = useQueryClient();
  const [search, setSearch] = useState<string>("");
  const [form, setForm] = useState<CreateInput>({
    phone: "",
    name: "",
    password: "",
    role: "user",
  });

  const list = useQuery({
    queryKey: ["admin-users", search],
    queryFn: () => listUsers(access ?? "", search),
    enabled: !!access,
  });

  const create = useMutation({
    mutationFn: (input: CreateInput) => createUser(access ?? "", input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      setForm({ phone: "", name: "", password: "", role: "user" });
    },
  });

  const flip = useMutation({
    mutationFn: ({ id, status }: { id: number; status: "active" | "disabled" }) =>
      setDisabled(access ?? "", id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  return (
    <div className="space-y-5">
      <AdminSectionCard title="新建账号" description="手机号作为登录名，初始密码至少 8 位。">
        <form
          className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate(form);
          }}
        >
          <div className="space-y-1.5">
            <AdminFieldLabel>手机号</AdminFieldLabel>
            <Input
              placeholder="11 位手机号"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1.5">
            <AdminFieldLabel>姓名</AdminFieldLabel>
            <Input
              placeholder="显示名称"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1.5">
            <AdminFieldLabel>初始密码</AdminFieldLabel>
            <Input
              placeholder="不少于 8 位"
              type="password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              required
              minLength={8}
            />
          </div>
          <div className="space-y-1.5">
            <AdminFieldLabel>角色</AdminFieldLabel>
            <select
              className="admin-select"
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as "user" | "admin" }))}
            >
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>
          <div className="md:col-span-2 lg:col-span-4">
            <Button type="submit" className="rounded-full" disabled={create.isPending}>
              {create.isPending ? "创建中…" : "创建账号"}
            </Button>
            {create.error instanceof ApiError && (
              <p className="mt-2 text-sm text-destructive">
                {create.error.code}: {create.error.message}
              </p>
            )}
          </div>
        </form>
      </AdminSectionCard>

      <AdminSectionCard
        title="账号列表"
        description={`共 ${list.data?.total ?? "—"} 条`}
        action={
          <Input
            className="w-44 sm:w-56"
            placeholder="搜索手机号 / 姓名"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        }
      >
        {list.isLoading && <AdminLoading />}
        {list.error instanceof ApiError && (
          <p className="text-sm text-destructive">
            {list.error.code}: {list.error.message}
          </p>
        )}
        {list.data && list.data.items.length === 0 ? (
          <AdminEmptyState title="暂无账号" description="可用上方表单创建第一个账号。" />
        ) : null}
        {list.data && list.data.items.length > 0 ? (
          <AdminTableShell>
            <thead>
              <tr>
                <th>手机号</th>
                <th>姓名</th>
                <th>角色</th>
                <th>状态</th>
                <th>最近登录</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((u) => (
                <tr key={u.id}>
                  <td className="font-mono text-xs">{u.phone}</td>
                  <td className="font-medium">{u.name}</td>
                  <td>
                    <AdminStatusBadge tone={u.role === "admin" ? "info" : "idle"}>
                      {ROLE_LABEL[u.role] ?? u.role}
                    </AdminStatusBadge>
                  </td>
                  <td>
                    <AdminStatusBadge tone={u.status === "active" ? "ok" : "warn"}>
                      {u.status === "active" ? "启用" : "已禁用"}
                    </AdminStatusBadge>
                  </td>
                  <td className="text-muted-foreground text-xs">
                    {u.last_login_at
                      ? new Date(u.last_login_at).toLocaleString("zh-CN")
                      : "—"}
                  </td>
                  <td>
                    {u.status === "active" ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-full"
                        onClick={() => flip.mutate({ id: u.id, status: "disabled" })}
                        disabled={flip.isPending}
                      >
                        禁用
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-full"
                        onClick={() => flip.mutate({ id: u.id, status: "active" })}
                        disabled={flip.isPending}
                      >
                        启用
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </AdminTableShell>
        ) : null}
      </AdminSectionCard>
    </div>
  );
}
