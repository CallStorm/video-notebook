import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AdminFieldLabel,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminStatusBadge,
} from "@/components/admin-shell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface ClaudeCodeRead {
  api_key_set: boolean;
  base_url: string | null;
  model_name: string;
}

interface ClaudeCodeUpdate {
  api_key: string;
  base_url: string | null;
  model_name: string;
}

async function loadConfig(access: string): Promise<ClaudeCodeRead> {
  return api<ClaudeCodeRead>("/admin/claude-code", { access });
}

async function saveConfig(access: string, body: ClaudeCodeUpdate): Promise<ClaudeCodeRead> {
  return api<ClaudeCodeRead>("/admin/claude-code", { method: "PUT", body, access });
}

export function AdminClaudePage() {
  const { access } = useAuth();
  const qc = useQueryClient();
  const config = useQuery({
    queryKey: ["admin-claude-code"],
    queryFn: () => loadConfig(access ?? ""),
    enabled: !!access,
  });
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [modelName, setModelName] = useState("");

  useEffect(() => {
    if (!config.data) return;
    setBaseUrl(config.data.base_url ?? "");
    setModelName(config.data.model_name);
    setApiKey("");
  }, [config.data]);

  const save = useMutation({
    mutationFn: () =>
      saveConfig(access ?? "", {
        api_key: apiKey,
        base_url: baseUrl.trim() ? baseUrl.trim() : null,
        model_name: modelName,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-claude-code"] }),
  });

  return (
    <div className="space-y-4">
      <AdminPageHeader
        title="Claude Code"
        description="全站共用一份运行配置。API Key 留空表示不修改已有密钥。"
        action={
          <AdminStatusBadge tone={config.data?.api_key_set ? "ok" : "warn"}>
            {config.data?.api_key_set ? "密钥已设置" : "密钥未设置"}
          </AdminStatusBadge>
        }
      />

      <AdminSectionCard
        title="连接参数"
        description="用于 Studio 智能体调用 Claude Code CLI。"
      >
        {config.isLoading ? <AdminLoading /> : null}
        <form
          className="grid grid-cols-1 gap-4 md:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <div className="space-y-1.5">
            <AdminFieldLabel hint="留空则保留原密钥">API Key</AdminFieldLabel>
            <Input
              type="password"
              autoComplete="off"
              placeholder="粘贴新的 API Key（可选）"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <AdminFieldLabel hint="可空，走默认网关">Base URL</AdminFieldLabel>
            <Input
              placeholder="例如 https://api.example.com"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <AdminFieldLabel>模型名</AdminFieldLabel>
            <Input
              placeholder="模型名"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              required
            />
          </div>
          {config.error instanceof ApiError && (
            <p className="text-sm text-destructive md:col-span-2">{config.error.message}</p>
          )}
          {save.error instanceof ApiError && (
            <p className="text-sm text-destructive md:col-span-2">{save.error.message}</p>
          )}
          <div className="md:col-span-2">
            <Button type="submit" className="rounded-full" disabled={save.isPending || !modelName.trim()}>
              {save.isPending ? "保存中…" : "保存配置"}
            </Button>
            {save.isSuccess ? (
              <span className="ml-3 text-sm text-[hsl(var(--success))]">已保存</span>
            ) : null}
          </div>
        </form>
      </AdminSectionCard>
    </div>
  );
}
