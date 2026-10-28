import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  AdminEmptyState,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminStatusBadge,
  AdminTableShell,
} from "@/components/admin-shell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface CapabilityRead {
  id: number;
  name: string;
  icon: string | null;
  format_key: string;
  enabled: boolean;
  is_builtin: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface PluginRead {
  id: string;
  name: string;
  icon: string | null;
  version: string;
  skill: string | null;
  timeout_seconds: number;
}

async function listCapabilities(access: string): Promise<CapabilityRead[]> {
  return api<CapabilityRead[]>("/admin/studio/capabilities", { access });
}

async function listPlugins(access: string): Promise<PluginRead[]> {
  return api<PluginRead[]>("/admin/studio/plugins", { access });
}

async function enableCapability(access: string, id: number): Promise<CapabilityRead> {
  return api<CapabilityRead>(`/admin/studio/capabilities/${id}/enable`, {
    access,
    method: "POST",
  });
}

async function disableCapability(access: string, id: number): Promise<CapabilityRead> {
  return api<CapabilityRead>(`/admin/studio/capabilities/${id}/disable`, {
    access,
    method: "POST",
  });
}

/** Embedded in /admin Studio section — enable/disable plugins only. */
export function AdminStudioPanel() {
  const { access } = useAuth();
  const qc = useQueryClient();

  const caps = useQuery({
    queryKey: ["admin-studio-capabilities"],
    queryFn: () => listCapabilities(access ?? ""),
    enabled: !!access,
  });
  const plugins = useQuery({
    queryKey: ["admin-studio-plugins"],
    queryFn: () => listPlugins(access ?? ""),
    enabled: !!access,
  });

  const toggle = useMutation({
    mutationFn: ({ id, enable }: { id: number; enable: boolean }) =>
      enable ? enableCapability(access ?? "", id) : disableCapability(access ?? "", id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-studio-capabilities"] });
    },
  });

  const pluginById = new Map((plugins.data ?? []).map((p) => [p.id, p]));
  const err =
    (caps.error instanceof ApiError && caps.error.message) ||
    (plugins.error instanceof ApiError && plugins.error.message) ||
    (toggle.error instanceof ApiError && toggle.error.message) ||
    null;

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Studio 工作台"
        description="能力来自磁盘插件目录 api/app/studio/plugins/。此处只负责启用或停用；新增能力请按插件约定开发。"
      />

      {err ? (
        <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {err}
        </p>
      ) : null}

      <AdminSectionCard title="已发现的插件">
        {plugins.isLoading || caps.isLoading ? (
          <AdminLoading />
        ) : (caps.data ?? []).length === 0 ? (
          <AdminEmptyState text="尚未同步到任何插件。确认 api/app/studio/plugins/ 下有插件目录，并重启 API。" />
        ) : (
          <AdminTableShell>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="px-3 py-2 font-medium">能力</th>
                  <th className="px-3 py-2 font-medium">插件 ID</th>
                  <th className="px-3 py-2 font-medium">版本</th>
                  <th className="px-3 py-2 font-medium">超时</th>
                  <th className="px-3 py-2 font-medium">状态</th>
                  <th className="px-3 py-2 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {(caps.data ?? []).map((cap) => {
                  const plugin = pluginById.get(cap.format_key);
                  return (
                    <tr key={cap.id} className="border-b last:border-0">
                      <td className="px-3 py-2">
                        <span className="mr-1">{cap.icon ?? "📦"}</span>
                        {cap.name}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                        {cap.format_key}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {plugin ? (
                          <>v{plugin.version}</>
                        ) : (
                          <span className="text-amber-600">磁盘插件缺失</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {plugin ? `${plugin.timeout_seconds}s` : "—"}
                      </td>
                      <td className="px-3 py-2">
                        <AdminStatusBadge tone={cap.enabled ? "ok" : "idle"}>
                          {cap.enabled ? "启用" : "停用"}
                        </AdminStatusBadge>
                      </td>
                      <td className="px-3 py-2 text-right">
                        {cap.enabled ? (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={toggle.isPending}
                            onClick={() => toggle.mutate({ id: cap.id, enable: false })}
                          >
                            停用
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            disabled={toggle.isPending || !plugin}
                            onClick={() => toggle.mutate({ id: cap.id, enable: true })}
                          >
                            启用
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </AdminTableShell>
        )}
      </AdminSectionCard>

      <p className="text-xs text-muted-foreground">
        新增能力：按 <code className="rounded bg-muted px-1">api/app/studio/plugins/DESIGN.md</code>{" "}
        添加插件目录，重启 API 与 studio-worker 后在此启用。
      </p>
    </div>
  );
}

/** 兼容旧链接 → 后台 Tab */
export default function AdminStudioPage() {
  return <Navigate to="/admin?section=studio&tab=studio" replace />;
}