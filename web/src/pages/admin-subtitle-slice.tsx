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

interface SubtitleSliceSettings {
  max_slice_seconds: number;
  min_slice_ms: number;
  silence_noise_db: number;
  silence_min_duration_s: number;
  min_silence_for_cut_ms: number;
}

const MAX_SLICE_PRESETS = [18, 30, 45, 60] as const;
const MIN_SLICE_PRESETS = [400, 600, 1000, 1500] as const;
const NOISE_PRESETS = [-40, -35, -32, -28] as const;
const SILENCE_DUR_PRESETS = [0.2, 0.3, 0.5, 0.8] as const;
const CUT_SILENCE_PRESETS = [150, 200, 300, 500] as const;

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

export function AdminSubtitleSlicePage() {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();

  const config = useQuery({
    queryKey: ["admin-subtitle-slice-settings"],
    queryFn: () =>
      api<SubtitleSliceSettings>("/admin/subtitle-slice-settings", { access: token }),
    enabled: !!token,
  });

  const [maxSliceSeconds, setMaxSliceSeconds] = useState(30);
  const [minSliceMs, setMinSliceMs] = useState(600);
  const [silenceNoiseDb, setSilenceNoiseDb] = useState(-32);
  const [silenceMinDurationS, setSilenceMinDurationS] = useState(0.3);
  const [minSilenceForCutMs, setMinSilenceForCutMs] = useState(200);

  useEffect(() => {
    if (!config.data) return;
    setMaxSliceSeconds(config.data.max_slice_seconds);
    setMinSliceMs(config.data.min_slice_ms);
    setSilenceNoiseDb(config.data.silence_noise_db);
    setSilenceMinDurationS(config.data.silence_min_duration_s);
    setMinSilenceForCutMs(config.data.min_silence_for_cut_ms);
  }, [config.data]);

  const save = useMutation({
    mutationFn: () =>
      api<SubtitleSliceSettings>("/admin/subtitle-slice-settings", {
        method: "PUT",
        access: token,
        body: {
          max_slice_seconds: clamp(Math.round(maxSliceSeconds), 8, 60),
          min_slice_ms: clamp(Math.round(minSliceMs), 200, 3000),
          silence_noise_db: clamp(silenceNoiseDb, -50, -20),
          silence_min_duration_s: clamp(silenceMinDurationS, 0.1, 1.0),
          min_silence_for_cut_ms: clamp(Math.round(minSilenceForCutMs), 100, 800),
        },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["admin-subtitle-slice-settings"], data);
    },
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="语音切片"
        description="控制 ASR 转写前如何按静音切段。尽量在句间停顿切开，减少一句话被硬切成两段。仅影响之后的转写；已有字幕需重新生成。"
      />

      {config.isLoading ? <AdminLoading /> : null}
      {config.error instanceof ApiError && (
        <p className="text-sm text-destructive">{config.error.message}</p>
      )}

      <AdminSectionCard
        title="片段长度"
        description="单段上限与下限。上限越大，越少硬切半句；太长则单次请求更慢。"
      >
        <div className="space-y-5">
          <div className="space-y-2">
            <p className="text-sm font-medium">单段上限（秒）· 当前 {maxSliceSeconds}</p>
            <p className="text-xs text-muted-foreground">
              默认 30。一口气超过此长度仍会硬切。范围 8–60。
            </p>
            <div className="flex flex-wrap gap-2">
              {MAX_SLICE_PRESETS.map((n) => (
                <PresetChip
                  key={n}
                  active={maxSliceSeconds === n}
                  onClick={() => setMaxSliceSeconds(n)}
                  label={`${n}s`}
                />
              ))}
            </div>
            <input
              type="range"
              min={8}
              max={60}
              step={1}
              value={maxSliceSeconds}
              onChange={(e) => setMaxSliceSeconds(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          <div className="space-y-2 border-t border-border/50 pt-4">
            <p className="text-sm font-medium">单段下限（毫秒）· 当前 {minSliceMs}</p>
            <p className="text-xs text-muted-foreground">
              避免切出过短碎渣。默认 600。范围 200–3000。
            </p>
            <div className="flex flex-wrap gap-2">
              {MIN_SLICE_PRESETS.map((n) => (
                <PresetChip
                  key={n}
                  active={minSliceMs === n}
                  onClick={() => setMinSliceMs(n)}
                  label={`${n}ms`}
                />
              ))}
            </div>
            <input
              type="range"
              min={200}
              max={3000}
              step={50}
              value={minSliceMs}
              onChange={(e) => setMinSliceMs(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>
        </div>
      </AdminSectionCard>

      <AdminSectionCard
        title="静音判定"
        description="ffmpeg silencedetect 的灵敏度。越敏感，越容易在短停顿处按句切开。"
      >
        <div className="space-y-5">
          <div className="space-y-2">
            <p className="text-sm font-medium">静音判定音量（dB）· 当前 {silenceNoiseDb}</p>
            <p className="text-xs text-muted-foreground">
              更小（如 -40）更敏感，短停顿也当静音；更大（如 -28）更钝、句子更粘。默认 -32。范围 -50～-20。
            </p>
            <div className="flex flex-wrap gap-2">
              {NOISE_PRESETS.map((n) => (
                <PresetChip
                  key={n}
                  active={silenceNoiseDb === n}
                  onClick={() => setSilenceNoiseDb(n)}
                  label={`${n} dB`}
                />
              ))}
            </div>
            <input
              type="range"
              min={-50}
              max={-20}
              step={1}
              value={silenceNoiseDb}
              onChange={(e) => setSilenceNoiseDb(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          <div className="space-y-2 border-t border-border/50 pt-4">
            <p className="text-sm font-medium">
              静音最短时长（秒）· 当前 {silenceMinDurationS.toFixed(1)}
            </p>
            <p className="text-xs text-muted-foreground">
              停顿短于此值不算静音。略降（如 0.2）更容易在句间短停切开。默认 0.3。范围 0.1–1.0。
            </p>
            <div className="flex flex-wrap gap-2">
              {SILENCE_DUR_PRESETS.map((n) => (
                <PresetChip
                  key={n}
                  active={Math.abs(silenceMinDurationS - n) < 0.01}
                  onClick={() => setSilenceMinDurationS(n)}
                  label={`${n}s`}
                />
              ))}
            </div>
            <input
              type="range"
              min={0.1}
              max={1.0}
              step={0.1}
              value={silenceMinDurationS}
              onChange={(e) => setSilenceMinDurationS(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          <div className="space-y-2 border-t border-border/50 pt-4">
            <p className="text-sm font-medium">切点最短静音（毫秒）· 当前 {minSilenceForCutMs}</p>
            <p className="text-xs text-muted-foreground">
              静音区间够长才在其中点下刀。略降更容易按句切开。默认 200。范围 100–800。
            </p>
            <div className="flex flex-wrap gap-2">
              {CUT_SILENCE_PRESETS.map((n) => (
                <PresetChip
                  key={n}
                  active={minSilenceForCutMs === n}
                  onClick={() => setMinSilenceForCutMs(n)}
                  label={`${n}ms`}
                />
              ))}
            </div>
            <input
              type="range"
              min={100}
              max={800}
              step={10}
              value={minSilenceForCutMs}
              onChange={(e) => setMinSilenceForCutMs(Number(e.target.value))}
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
