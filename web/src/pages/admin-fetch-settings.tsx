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

interface FetchSettings {
  max_concurrent: number;
  task_timeout_minutes: number;
  chunk_parallel_enabled: boolean;
  chunk_count: number;
  chunk_min_mb: number;
}

const CHUNK_PRESETS = [2, 4, 6, 8] as const;
const MIN_MB_PRESETS = [10, 20, 30, 50] as const;
const CONCURRENT_PRESETS = [1, 2, 4, 8] as const;

export function AdminFetchSettingsPage() {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();

  const config = useQuery({
    queryKey: ["admin-fetch-settings"],
    queryFn: () => api<FetchSettings>("/admin/fetch-settings", { access: token }),
    enabled: !!token,
  });

  const [maxConcurrent, setMaxConcurrent] = useState(2);
  const [timeoutMinutes, setTimeoutMinutes] = useState(30);
  const [chunkEnabled, setChunkEnabled] = useState(true);
  const [chunkCount, setChunkCount] = useState(4);
  const [chunkMinMb, setChunkMinMb] = useState(20);

  useEffect(() => {
    if (!config.data) return;
    setMaxConcurrent(config.data.max_concurrent);
    setTimeoutMinutes(config.data.task_timeout_minutes);
    setChunkEnabled(config.data.chunk_parallel_enabled);
    setChunkCount(config.data.chunk_count);
    setChunkMinMb(config.data.chunk_min_mb);
  }, [config.data]);

  const save = useMutation({
    mutationFn: () =>
      api<FetchSettings>("/admin/fetch-settings", {
        method: "PUT",
        access: token,
        body: {
          max_concurrent: maxConcurrent,
          task_timeout_minutes: timeoutMinutes,
          chunk_parallel_enabled: chunkEnabled,
          chunk_count: chunkCount,
          chunk_min_mb: chunkMinMb,
        },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["admin-fetch-settings"], data);
    },
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="抓取设置"
        description="控制字幕抓取任务的并发、超时，以及视频文件的分块并行下载。"
      />

      {config.isLoading ? <AdminLoading /> : null}
      {config.error instanceof ApiError && (
        <p className="text-sm text-destructive">{config.error.message}</p>
      )}

      <AdminSectionCard
        title="任务并发与超时"
        description="同时进行的「抓取 + 字幕」任务数，以及单条任务最长时间。"
      >
        <div className="space-y-5">
          <div className="space-y-2">
            <p className="text-sm font-medium">最大并发任务数 · 当前 {maxConcurrent}</p>
            <div className="flex flex-wrap gap-2">
              {CONCURRENT_PRESETS.map((n) => (
                <PresetChip
                  key={n}
                  active={maxConcurrent === n}
                  onClick={() => setMaxConcurrent(n)}
                  label={String(n)}
                />
              ))}
            </div>
            <input
              type="range"
              min={1}
              max={8}
              step={1}
              value={maxConcurrent}
              onChange={(e) => setMaxConcurrent(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          <div className="space-y-2 border-t border-border/50 pt-4">
            <p className="text-sm font-medium">任务超时 · {timeoutMinutes} 分钟</p>
            <p className="text-xs text-muted-foreground">
              整链（下载 + 字幕）共用此时限，超时将标为失败。
            </p>
            <input
              type="range"
              min={5}
              max={180}
              step={5}
              value={timeoutMinutes}
              onChange={(e) => setTimeoutMinutes(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>
        </div>
      </AdminSectionCard>

      <AdminSectionCard
        title="分块并行下载"
        description="提升视频下载速度。设置过高可能触发平台风控，建议保持推荐值。"
      >
        <div className="space-y-5">
          <label className="flex items-start gap-3 rounded-xl border border-border/50 bg-muted/15 px-3.5 py-3">
            <input
              type="checkbox"
              className="mt-1"
              checked={chunkEnabled}
              onChange={(e) => setChunkEnabled(e.target.checked)}
            />
            <span>
              <span className="block text-sm font-medium">启用分块并行下载</span>
              <span className="text-xs text-muted-foreground">
                启用后文件分成多块同时下载；仅对视频文件有效。
              </span>
            </span>
          </label>

          <div
            className={`space-y-3 border-t border-border/50 pt-4 ${
              chunkEnabled ? "" : "pointer-events-none opacity-50"
            }`}
          >
            <p className="text-sm font-medium">分块数量 · 当前 {chunkCount}</p>
            <div className="flex flex-wrap gap-2">
              {CHUNK_PRESETS.map((n) => (
                <PresetChip
                  key={n}
                  active={chunkCount === n}
                  onClick={() => setChunkCount(n)}
                  label={`${n} 块`}
                />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">推荐 4 块，平衡速度与稳定性。</p>
            <input
              type="range"
              min={2}
              max={8}
              step={1}
              value={chunkCount}
              onChange={(e) => setChunkCount(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          <div
            className={`space-y-3 border-t border-border/50 pt-4 ${
              chunkEnabled ? "" : "pointer-events-none opacity-50"
            }`}
          >
            <p className="text-sm font-medium">单块最小大小 · {chunkMinMb} MB</p>
            <p className="text-xs text-muted-foreground">
              小于此大小的文件使用单线程下载。推荐 20–50 MB。
            </p>
            <div className="flex flex-wrap gap-2">
              {MIN_MB_PRESETS.map((n) => (
                <PresetChip
                  key={n}
                  active={chunkMinMb === n}
                  onClick={() => setChunkMinMb(n)}
                  label={`${n} MB`}
                />
              ))}
            </div>
            <input
              type="range"
              min={5}
              max={100}
              step={1}
              value={chunkMinMb}
              onChange={(e) => setChunkMinMb(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>
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
        {save.isSuccess ? <span className="text-sm text-[hsl(var(--success))]">已保存</span> : null}
        {save.isError ? (
          <span className="text-sm text-destructive">
            {save.error instanceof ApiError ? save.error.message : "保存失败"}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function PresetChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
        active
          ? "bg-primary text-primary-foreground shadow-glow"
          : "bg-muted text-muted-foreground hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );
}
