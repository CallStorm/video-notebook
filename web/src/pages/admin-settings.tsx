import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  AdminLoading,
  AdminSectionCard,
} from "@/components/admin-shell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface ObsSettings {
  pipeline_logs_enabled: boolean;
  llm_traces_enabled: boolean;
  retention_days: number;
  success_sample_rate: number;
  llm_record_full: boolean;
  llm_truncate_chars: number;
  max_pipeline_run_rows: number;
  max_llm_trace_rows: number;
  langfuse_enabled: boolean;
}

export function AdminSettingsPage() {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();

  const settings = useQuery({
    queryKey: ["admin-obs-settings"],
    queryFn: () => api<ObsSettings>("/admin/observability/settings", { access: token }),
    enabled: !!token,
  });

  const [pipelineEnabled, setPipelineEnabled] = useState(false);
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [retention, setRetention] = useState(7);
  const [sample, setSample] = useState(1);
  const [full, setFull] = useState(false);
  const [trunc, setTrunc] = useState(4096);
  const [maxPipelineRows, setMaxPipelineRows] = useState(50000);
  const [maxLlmRows, setMaxLlmRows] = useState(20000);

  useEffect(() => {
    if (!settings.data) return;
    setPipelineEnabled(settings.data.pipeline_logs_enabled);
    setLlmEnabled(settings.data.llm_traces_enabled);
    setRetention(settings.data.retention_days);
    setSample(settings.data.success_sample_rate);
    setFull(settings.data.llm_record_full);
    setTrunc(settings.data.llm_truncate_chars);
    setMaxPipelineRows(settings.data.max_pipeline_run_rows);
    setMaxLlmRows(settings.data.max_llm_trace_rows);
  }, [settings.data]);

  const save = useMutation({
    mutationFn: () =>
      api<ObsSettings>("/admin/observability/settings", {
        method: "PUT",
        access: token,
        body: {
          ...(settings.data ?? { langfuse_enabled: false }),
          pipeline_logs_enabled: pipelineEnabled,
          llm_traces_enabled: llmEnabled,
          retention_days: retention,
          success_sample_rate: sample,
          llm_record_full: full,
          llm_truncate_chars: trunc,
          max_pipeline_run_rows: maxPipelineRows,
          max_llm_trace_rows: maxLlmRows,
        },
      }),
    onSuccess: (data) => qc.setQueryData(["admin-obs-settings"], data),
  });

  const purge = useMutation({
    mutationFn: () =>
      api("/admin/observability/purge", { method: "POST", access: token }),
  });

  return (
    <div className="space-y-5">
      {settings.isLoading ? <AdminLoading /> : null}
      {settings.error instanceof ApiError && (
        <p className="text-sm text-destructive">{settings.error.message}</p>
      )}

      <AdminSectionCard
        title="流水线日志"
        description="记录入队 → 抓取 → 字幕/ASR → 概览 → 向量各阶段。成功默认摘要；失败保留错误。"
      >
        <div className="space-y-3">
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-3 py-2.5">
            <input
              type="checkbox"
              className="mt-1"
              checked={pipelineEnabled}
              onChange={(e) => setPipelineEnabled(e.target.checked)}
            />
            <span>
              <span className="block text-sm font-medium">启用流水线日志</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                默认关闭。查询页见「流水线日志」。
              </span>
            </span>
          </label>
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              成功采样率
              <input
                type="number"
                min={0}
                max={1}
                step={0.1}
                className="admin-input w-24"
                value={sample}
                onChange={(e) => setSample(Number(e.target.value))}
              />
            </label>
            <label className="flex items-center gap-2">
              行数上限
              <input
                type="number"
                min={1000}
                className="admin-input w-28"
                value={maxPipelineRows}
                onChange={(e) => setMaxPipelineRows(Number(e.target.value) || 50000)}
              />
            </label>
          </div>
          <p className="text-xs text-muted-foreground">
            查看：
            <Link
              to="/admin?section=pipeline-logs"
              className="ml-1 font-medium text-primary hover:underline"
            >
              流水线日志 →
            </Link>
          </p>
        </div>
      </AdminSectionCard>

      <AdminSectionCard
        title="LLM 追踪"
        description="内建轻量追踪（类 Langfuse）。覆盖对话与来源概览。正文默认截断。"
      >
        <div className="space-y-3">
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-3 py-2.5">
            <input
              type="checkbox"
              className="mt-1"
              checked={llmEnabled}
              onChange={(e) => setLlmEnabled(e.target.checked)}
            />
            <span>
              <span className="block text-sm font-medium">启用 LLM 追踪</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                默认关闭。管理员可在「LLM 追踪」查看 prompt / completion。
              </span>
            </span>
          </label>
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-3 py-2.5">
            <input
              type="checkbox"
              className="mt-1"
              checked={full}
              onChange={(e) => setFull(e.target.checked)}
            />
            <span>
              <span className="block text-sm font-medium">记录全文</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                关闭时按截断长度保存（默认 4KB）。
              </span>
            </span>
          </label>
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              截断字符
              <input
                type="number"
                min={256}
                className="admin-input w-28"
                value={trunc}
                onChange={(e) => setTrunc(Number(e.target.value) || 4096)}
              />
            </label>
            <label className="flex items-center gap-2">
              行数上限
              <input
                type="number"
                min={1000}
                className="admin-input w-28"
                value={maxLlmRows}
                onChange={(e) => setMaxLlmRows(Number(e.target.value) || 20000)}
              />
            </label>
          </div>
          <p className="text-xs text-muted-foreground">
            查看：
            <Link
              to="/admin?section=llm-traces"
              className="ml-1 font-medium text-primary hover:underline"
            >
              LLM 追踪 →
            </Link>
          </p>
        </div>
      </AdminSectionCard>

      <AdminSectionCard
        title="保留与清理"
        description="按天滚动删除；超行数上限先删最旧。清理不挡业务请求。"
      >
        <div className="space-y-3">
          <label className="flex items-center gap-2 text-sm">
            保留天数
            <input
              type="number"
              min={1}
              max={90}
              className="admin-input w-20"
              value={retention}
              onChange={(e) => setRetention(Number(e.target.value) || 7)}
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              className="rounded-full"
              disabled={save.isPending || settings.isLoading}
              onClick={() => save.mutate()}
            >
              {save.isPending ? "保存中…" : "保存设置"}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="rounded-full"
              disabled={purge.isPending}
              onClick={() => purge.mutate()}
            >
              {purge.isPending ? "清理中…" : "立即清理过期"}
            </Button>
            {save.isSuccess ? (
              <span className="text-sm text-[hsl(var(--success))]">已保存</span>
            ) : null}
            {purge.isSuccess ? (
              <span className="text-sm text-[hsl(var(--success))]">已清理</span>
            ) : null}
          </div>
        </div>
      </AdminSectionCard>
    </div>
  );
}
