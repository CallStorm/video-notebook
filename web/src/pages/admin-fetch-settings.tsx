import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
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
    <div className="space-y-8">
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">任务并发与超时</h2>
          <p className="text-sm text-muted-foreground">
            控制同时进行的「抓取 + 字幕」任务数，以及单条任务的最长时间。
          </p>
        </div>

        {config.error instanceof ApiError && (
          <p className="text-sm text-destructive">{config.error.message}</p>
        )}

        <div className="space-y-4 rounded-2xl border border-border/60 bg-card/80 p-4">
          <div className="space-y-2">
            <p className="text-sm font-medium">最大并发任务数 (当前: {maxConcurrent})</p>
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
            <p className="text-sm font-medium">任务超时: {timeoutMinutes} 分钟</p>
            <p className="text-xs text-muted-foreground">整链（下载 + 字幕）共用此时限，超时将标为失败。</p>
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
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">分块并行下载</h2>
          <p className="text-sm text-muted-foreground">
            配置文件下载时的并发参数，以获得更快的下载速度。注意不要设置过高以免触发服务器风控。
          </p>
        </div>

        <div className="space-y-4 rounded-2xl border border-border/60 bg-card/80 p-4">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1"
              checked={chunkEnabled}
              onChange={(e) => setChunkEnabled(e.target.checked)}
            />
            <span>
              <span className="block text-sm font-medium">启用分块并行下载</span>
              <span className="text-xs text-muted-foreground">
                启用后，文件将被分成多块同时下载，可显著提升下载速度。仅对视频文件有效。
              </span>
            </span>
          </label>

          <div className={`space-y-3 border-t border-border/50 pt-4 ${chunkEnabled ? "" : "opacity-50 pointer-events-none"}`}>
            <p className="text-sm font-medium">分块数量 (当前: {chunkCount})</p>
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
            <p className="text-xs text-muted-foreground">
              推荐值: 4 块（平衡速度和稳定性）。更多分块可能导致服务器限流
            </p>
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

          <div className={`space-y-3 border-t border-border/50 pt-4 ${chunkEnabled ? "" : "opacity-50 pointer-events-none"}`}>
            <p className="text-sm font-medium">单块最小大小: {chunkMinMb} MB</p>
            <p className="text-xs text-muted-foreground">
              小于此大小的文件将使用单线程下载。推荐设置: 20-50 MB
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
      </section>

      <div className="flex items-center gap-3">
        <Button
          type="button"
          className="rounded-full"
          disabled={save.isPending || config.isLoading}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "保存中…" : "保存"}
        </Button>
        {save.isSuccess ? <span className="text-sm text-emerald-700">已保存</span> : null}
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
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
        active
          ? "bg-primary text-primary-foreground"
          : "bg-muted text-muted-foreground hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );
}
