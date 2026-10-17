import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface SkillRead {
  id: number;
  name: string;
  description: string | null;
  version: string | null;
  storage_path: string;
  file_count: number;
  size_bytes: number;
  uploaded_by: number;
  created_at: string | null;
  updated_at: string | null;
}

interface SkillUpdate {
  name?: string;
  description?: string | null;
  version?: string | null;
}

async function listSkills(access: string): Promise<SkillRead[]> {
  return api<SkillRead[]>("/admin/skills", { access });
}

async function uploadSkill(access: string, file: File): Promise<SkillRead> {
  const body = new FormData();
  body.append("file", file);
  return api<SkillRead>("/admin/skills", { method: "POST", body, access });
}

async function updateSkill(access: string, id: number, body: SkillUpdate): Promise<SkillRead> {
  return api<SkillRead>(`/admin/skills/${id}`, { method: "PATCH", body, access });
}

async function deleteSkill(access: string, id: number): Promise<void> {
  await api(`/admin/skills/${id}`, { method: "DELETE", access, raw: true });
}

async function downloadSkill(access: string, skill: SkillRead): Promise<void> {
  const response = await api<Response>(`/admin/skills/${skill.id}/download`, {
    access,
    raw: true,
  });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${skill.name || `skill-${skill.id}`}.zip`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN");
}

export default function AdminSkillsPage() {
  const { user, access, logout } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState<SkillRead | null>(null);
  const [meta, setMeta] = useState({ name: "", description: "", version: "" });

  const list = useQuery({
    queryKey: ["admin-skills"],
    queryFn: () => listSkills(access ?? ""),
    enabled: !!access,
  });

  const upload = useMutation({
    mutationFn: (file: File) => uploadSkill(access ?? "", file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-skills"] });
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  const saveMeta = useMutation({
    mutationFn: () =>
      updateSkill(access ?? "", editing!.id, {
        name: meta.name.trim(),
        description: meta.description.trim() || null,
        version: meta.version.trim() || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-skills"] });
      setEditing(null);
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteSkill(access ?? "", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-skills"] }),
  });

  const download = useMutation({
    mutationFn: (skill: SkillRead) => downloadSkill(access ?? "", skill),
  });

  return (
    <Layout
      rightSlot={
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span>{user?.name}</span>
          <Link to="/" className="hover:text-foreground">
            返回前台
          </Link>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              logout();
              navigate("/", { replace: true });
            }}
          >
            登出
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        <div>
          <Link to="/admin" className="text-sm text-muted-foreground hover:text-foreground">
            返回后台
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight">技能</h1>
          <p className="text-sm text-muted-foreground">上传 zip，改元数据，下载或删除。</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>上传技能</CardTitle>
            <CardDescription>根目录或单层文件夹内需包含 SKILL.md，上限 32MB。</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="flex flex-wrap items-center gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                const file = fileRef.current?.files?.[0];
                if (file) upload.mutate(file);
              }}
            >
              <Input ref={fileRef} type="file" accept=".zip" required />
              <Button type="submit" disabled={upload.isPending}>
                {upload.isPending ? "上传中…" : "上传"}
              </Button>
            </form>
            {upload.error instanceof ApiError && (
              <p className="mt-2 text-sm text-destructive">{upload.error.message}</p>
            )}
          </CardContent>
        </Card>

        {editing && (
          <Card>
            <CardHeader>
              <CardTitle>编辑元数据</CardTitle>
              <CardDescription>技能 #{editing.id}</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="grid grid-cols-1 gap-3 md:grid-cols-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  saveMeta.mutate();
                }}
              >
                <Input
                  placeholder="名称"
                  value={meta.name}
                  onChange={(e) => setMeta((m) => ({ ...m, name: e.target.value }))}
                  required
                />
                <Input
                  placeholder="版本"
                  value={meta.version}
                  onChange={(e) => setMeta((m) => ({ ...m, version: e.target.value }))}
                />
                <Input
                  placeholder="说明"
                  value={meta.description}
                  onChange={(e) => setMeta((m) => ({ ...m, description: e.target.value }))}
                />
                <div className="flex gap-2 md:col-span-3">
                  <Button type="submit" disabled={saveMeta.isPending}>
                    {saveMeta.isPending ? "保存中…" : "保存"}
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setEditing(null)}>
                    取消
                  </Button>
                </div>
              </form>
              {saveMeta.error instanceof ApiError && (
                <p className="mt-2 text-sm text-destructive">{saveMeta.error.message}</p>
              )}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle>技能列表</CardTitle>
            <CardDescription>共 {list.data?.length ?? "—"} 条。</CardDescription>
          </CardHeader>
          <CardContent>
            {list.isLoading && <p className="text-sm text-muted-foreground">加载中…</p>}
            {list.error instanceof ApiError && (
              <p className="text-sm text-destructive">{list.error.message}</p>
            )}
            {remove.error instanceof ApiError && (
              <p className="mb-3 text-sm text-destructive">{remove.error.message}</p>
            )}
            {download.error instanceof ApiError && (
              <p className="mb-3 text-sm text-destructive">{download.error.message}</p>
            )}
            {list.data && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="py-2 pr-4">名称</th>
                      <th className="py-2 pr-4">版本</th>
                      <th className="py-2 pr-4">大小</th>
                      <th className="py-2 pr-4">上传时间</th>
                      <th className="py-2 pr-4">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data.map((skill) => (
                      <tr key={skill.id} className="border-b">
                        <td className="py-2 pr-4">{skill.name}</td>
                        <td className="py-2 pr-4">{skill.version ?? "—"}</td>
                        <td className="py-2 pr-4">{formatBytes(skill.size_bytes)}</td>
                        <td className="py-2 pr-4 text-muted-foreground">
                          {formatDateTime(skill.created_at)}
                        </td>
                        <td className="py-2 pr-4">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditing(skill);
                                setMeta({
                                  name: skill.name,
                                  description: skill.description ?? "",
                                  version: skill.version ?? "",
                                });
                              }}
                            >
                              编辑
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => download.mutate(skill)}
                              disabled={download.isPending}
                            >
                              下载
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                if (confirm(`删除技能「${skill.name}」？`)) remove.mutate(skill.id);
                              }}
                              disabled={remove.isPending}
                            >
                              删除
                            </Button>
                          </div>
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
    </Layout>
  );
}
