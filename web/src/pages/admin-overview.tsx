import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
} from "@/components/admin-shell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface OverviewSettings {
  auto_generate_after_subtitle: boolean;
  prompt_text: string;
  is_custom_prompt: boolean;
  default_prompt: string;
}

export function AdminOverviewPage() {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();

  const config = useQuery({
    queryKey: ["admin-overview-settings"],
    queryFn: () =>
      api<OverviewSettings>("/admin/overview-settings", { access: token }),
    enabled: !!token,
  });

  const [autoGen, setAutoGen] = useState(true);
  const [prompt, setPrompt] = useState("");

  useEffect(() => {
    if (!config.data) return;
    setAutoGen(config.data.auto_generate_after_subtitle);
    setPrompt(config.data.prompt_text);
  }, [config.data]);

  const save = useMutation({
    mutationFn: () =>
      api<OverviewSettings>("/admin/overview-settings", {
        method: "PUT",
        access: token,
        body: {
          auto_generate_after_subtitle: autoGen,
          prompt_text: prompt,
        },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["admin-overview-settings"], data);
      setPrompt(data.prompt_text);
      setAutoGen(data.auto_generate_after_subtitle);
    },
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="来源概览"
        description="字幕完成后是否自动用默认聊天模型生成概览，以及可自定义的提示词。默认提示词参考了 Open Notebook 的 Simple Summary：稠密、完整句子、只输出正文。"
      />

      {config.isLoading ? <AdminLoading /> : null}
      {config.error instanceof ApiError && (
        <p className="text-sm text-destructive">{config.error.message}</p>
      )}

      <AdminSectionCard
        title="自动生成"
        description="开启后，每个来源在字幕首次成功（或仍为 pending/失败空文）时自动写概览。手动「重新生成」仍会重跑字幕并刷新概览。"
      >
        <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-3 py-2.5">
          <input
            type="checkbox"
            className="mt-1"
            checked={autoGen}
            onChange={(e) => setAutoGen(e.target.checked)}
          />
          <span>
            <span className="block text-sm font-medium">
              字幕完成后自动生成概览
            </span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              默认开启。关闭后仅保留手动「重新生成」。已有 pending 概览不会自动回填，需点一次重新生成。
            </span>
          </span>
        </label>
      </AdminSectionCard>

      <AdminSectionCard
        title="概览提示词"
        description="发给聊天模型的说明文字（纯文本，不做模板渲染）。留空保存即恢复内置默认。字幕正文会附在提示词后面。"
      >
        <textarea
          className="admin-textarea min-h-[220px] font-mono text-[13px] leading-relaxed"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          spellCheck={false}
          aria-label="概览提示词"
        />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className="rounded-full"
            onClick={() => {
              if (config.data?.default_prompt) {
                setPrompt(config.data.default_prompt);
              }
            }}
          >
            恢复默认
          </Button>
          {config.data?.is_custom_prompt ? (
            <span className="text-xs text-muted-foreground">当前为自定义提示词</span>
          ) : (
            <span className="text-xs text-muted-foreground">当前为内置默认</span>
          )}
        </div>
      </AdminSectionCard>

      <div className="flex items-center gap-3">
        <Button
          type="button"
          className="rounded-full"
          disabled={save.isPending || config.isLoading}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "保存中…" : "保存设置"}
        </Button>
        {save.isSuccess ? (
          <span className="text-sm text-[hsl(var(--success))]">已保存</span>
        ) : null}
        {save.isError ? (
          <span className="text-sm text-destructive">
            {save.error instanceof ApiError ? save.error.message : "保存失败"}
          </span>
        ) : null}
      </div>
    </div>
  );
}
