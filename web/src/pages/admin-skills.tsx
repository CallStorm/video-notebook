import { useRef, useState } from "react";
import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AdminEmptyState,
  AdminFieldLabel,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminTableShell,
} from "@/components/admin-shell";
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

export function AdminSkillsPanel() {
  const { access } = useAuth();
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
    <div className="space-y-5">
      <AdminPageHeader
        title="技能包"
        description="上传含 SKILL.md 的 zip，供智能体绑定。单包上限 32MB。"
      />

      <AdminSectionCard
        title="上传技能"
        description="根目录或单层文件夹内需包含 SKILL.md。"
      >
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const file = fileRef.current?.files?.[0];
            if (file) upload.mutate(file);
          }}
        >
          <div className="min-w-[16rem] flex-1 space-y-1.5">
            <AdminFieldLabel>选择 zip 文件</AdminFieldLabel>
            <Input ref={fileRef} type="file" accept=".zip" required />
          </div>
          <Button type="submit" className="rounded-full" disabled={upload.isPending}>
            {upload.isPending ? "上传中…" : "上传"}
          </Button>
        </form>
        {upload.error instanceof ApiError && (
          <p className="mt-2 text-sm text-destructive">{upload.error.message}</p>
        )}
      </AdminSectionCard>

      {editing && (
        <AdminSectionCard title="编辑元数据" description={`技能 #${editing.id}`}>
          <form
            className="grid grid-cols-1 gap-3 md:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              saveMeta.mutate();
            }}
          >
            <div className="space-y-1.5">
              <AdminFieldLabel>名称</AdminFieldLabel>
              <Input
                placeholder="名称"
                value={meta.name}
                onChange={(e) => setMeta((m) => ({ ...m, name: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <AdminFieldLabel>版本</AdminFieldLabel>
              <Input
                placeholder="版本"
                value={meta.version}
                onChange={(e) => setMeta((m) => ({ ...m, version: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <AdminFieldLabel>说明</AdminFieldLabel>
              <Input
                placeholder="说明"
                value={meta.description}
                onChange={(e) => setMeta((m) => ({ ...m, description: e.target.value }))}
              />
            </div>
            <div className="flex gap-2 md:col-span-3">
              <Button type="submit" className="rounded-full" disabled={saveMeta.isPending}>
                {saveMeta.isPending ? "保存中…" : "保存"}
              </Button>
              <Button type="button" variant="ghost" className="rounded-full" onClick={() => setEditing(null)}>
                取消
              </Button>
            </div>
          </form>
          {saveMeta.error instanceof ApiError && (
            <p className="mt-2 text-sm text-destructive">{saveMeta.error.message}</p>
          )}
        </AdminSectionCard>
      )}

      <AdminSectionCard title="技能列表" description={`共 ${list.data?.length ?? "—"} 条`}>
        {list.isLoading && <AdminLoading />}
        {list.error instanceof ApiError && (
          <p className="text-sm text-destructive">{list.error.message}</p>
        )}
        {remove.error instanceof ApiError && (
          <p className="mb-3 text-sm text-destructive">{remove.error.message}</p>
        )}
        {download.error instanceof ApiError && (
          <p className="mb-3 text-sm text-destructive">{download.error.message}</p>
        )}
        {list.data && list.data.length === 0 ? (
          <AdminEmptyState title="还没有技能" description="上传第一个 zip 技能包即可绑定到智能体。" />
        ) : null}
        {list.data && list.data.length > 0 ? (
          <AdminTableShell>
            <thead>
              <tr>
                <th>名称</th>
                <th>版本</th>
                <th>大小</th>
                <th>上传时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((skill) => (
                <tr key={skill.id}>
                  <td>
                    <div className="font-medium">{skill.name}</div>
                    {skill.description ? (
                      <div className="mt-0.5 max-w-xs truncate text-xs text-muted-foreground">
                        {skill.description}
                      </div>
                    ) : null}
                  </td>
                  <td className="text-muted-foreground">{skill.version ?? "—"}</td>
                  <td className="tabular-nums text-muted-foreground">{formatBytes(skill.size_bytes)}</td>
                  <td className="text-xs text-muted-foreground">{formatDateTime(skill.created_at)}</td>
                  <td>
                    <div className="flex flex-wrap gap-1.5">
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-full"
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
                        className="rounded-full"
                        onClick={() => download.mutate(skill)}
                        disabled={download.isPending}
                      >
                        下载
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-full text-destructive hover:text-destructive"
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
          </AdminTableShell>
        ) : null}
      </AdminSectionCard>
    </div>
  );
}

/** 兼容旧链接 → 后台 Tab */
export default function AdminSkillsPage() {
  return <Navigate to="/admin" replace />;
}
