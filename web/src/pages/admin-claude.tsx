import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
    <Card>
      <CardHeader>
        <CardTitle>Claude Code</CardTitle>
        <CardDescription>
          全站一份。API Key 留空表示不修改。已设置：{config.data?.api_key_set ? "是" : "否"}。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid grid-cols-1 gap-3 md:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <Input
            type="password"
            autoComplete="off"
            placeholder="API Key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <Input
            placeholder="Base URL，可空"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
          <Input
            className="md:col-span-2"
            placeholder="模型名"
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            required
          />
          {config.error instanceof ApiError && (
            <p className="text-sm text-destructive md:col-span-2">{config.error.message}</p>
          )}
          {save.error instanceof ApiError && (
            <p className="text-sm text-destructive md:col-span-2">{save.error.message}</p>
          )}
          <div>
            <Button type="submit" disabled={save.isPending || !modelName.trim()}>
              {save.isPending ? "保存中…" : "保存"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
