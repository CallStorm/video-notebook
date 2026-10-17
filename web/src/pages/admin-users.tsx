import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>新建账号</CardTitle>
          <CardDescription>仅管理员可创建账号。</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate(form);
            }}
          >
            <Input
              placeholder="手机号"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              required
            />
            <Input
              placeholder="姓名"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
            <Input
              placeholder="初始密码（≥8 位）"
              type="password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              required
              minLength={8}
            />
            <select
              className="h-10 rounded-md border border-input bg-background px-3 text-sm"
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as "user" | "admin" }))}
            >
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
            <div className="md:col-span-2 lg:col-span-4">
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "创建中…" : "创建"}
              </Button>
              {create.error instanceof ApiError && (
                <p className="mt-2 text-sm text-destructive">
                  {create.error.code}: {create.error.message}
                </p>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>账号列表</CardTitle>
          <CardDescription>共 {list.data?.total ?? "—"} 条。</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4">
            <Input
              placeholder="按手机号 / 姓名搜索"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {list.isLoading && <p className="text-sm text-muted-foreground">加载中…</p>}
          {list.error instanceof ApiError && (
            <p className="text-sm text-destructive">
              {list.error.code}: {list.error.message}
            </p>
          )}
          {list.data && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4">手机号</th>
                    <th className="py-2 pr-4">姓名</th>
                    <th className="py-2 pr-4">角色</th>
                    <th className="py-2 pr-4">状态</th>
                    <th className="py-2 pr-4">最近登录</th>
                    <th className="py-2 pr-4">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.items.map((u) => (
                    <tr key={u.id} className="border-b">
                      <td className="py-2 pr-4 font-mono">{u.phone}</td>
                      <td className="py-2 pr-4">{u.name}</td>
                      <td className="py-2 pr-4">{u.role}</td>
                      <td className="py-2 pr-4">{u.status}</td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {u.last_login_at ?? "—"}
                      </td>
                      <td className="py-2 pr-4">
                        {u.status === "active" ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => flip.mutate({ id: u.id, status: "disabled" })}
                            disabled={flip.isPending}
                          >
                            禁用
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
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
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
