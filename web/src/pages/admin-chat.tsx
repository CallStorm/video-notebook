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

interface ChatSettings {
  history_limit: number;
  default_history_limit: number;
}

const PRESETS = [4, 6, 8, 12, 16, 20] as const;

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

export function AdminChatPage() {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();

  const config = useQuery({
    queryKey: ["admin-chat-settings"],
    queryFn: () => api<ChatSettings>("/admin/chat-settings", { access: token }),
    enabled: !!token,
  });

  const [historyLimit, setHistoryLimit] = useState(8);

  useEffect(() => {
    if (!config.data) return;
    setHistoryLimit(config.data.history_limit);
  }, [config.data]);

  const save = useMutation({
    mutationFn: () =>
      api<ChatSettings>("/admin/chat-settings", {
        method: "PUT",
        access: token,
        body: {
          history_limit: clamp(Math.round(historyLimit), 2, 20),
        },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["admin-chat-settings"], data);
    },
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="对话设置"
        description="控制笔记本 Chat 每次提问携带的历史轮数。勾选来源的字幕全文每轮都会带上，不会因超限被截断。"
      />

      {config.isLoading ? <AdminLoading /> : null}
      {config.error instanceof ApiError && (
        <p className="text-sm text-destructive">{config.error.message}</p>
      )}

      <AdminSectionCard
        title="历史轮数"
        description="一轮 = 一次用户提问 + 对应助手回答。超上下文预算时会从最旧的一轮开始丢弃，勾选字幕全文始终保留。"
      >
        <div className="space-y-2">
          <p className="text-sm font-medium">最近保留 · 当前 {historyLimit} 轮</p>
          <p className="text-xs text-muted-foreground">
            默认 {config.data?.default_history_limit ?? 8}（可用环境变量 CHAT_HISTORY_LIMIT
            覆盖种子值）。范围 2–20。
          </p>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setHistoryLimit(n)}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
                  historyLimit === n
                    ? "bg-primary text-primary-foreground shadow-glow"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
          <input
            type="range"
            min={2}
            max={20}
            step={1}
            value={historyLimit}
            onChange={(e) => setHistoryLimit(Number(e.target.value))}
            className="w-full accent-primary"
          />
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
