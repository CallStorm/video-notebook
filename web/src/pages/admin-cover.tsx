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

interface CoverSettings {
  mode: "image" | "svg";
  prompt_system: string;
  prompt_user: string;
  temperature: number;
  force_keyword_motif: boolean;
  fallback_on_error: boolean;
  image_prompt_system: string;
  image_prompt_user: string;
  image_size: string;
  is_custom_system: boolean;
  is_custom_user: boolean;
  is_custom_image_system: boolean;
  is_custom_image_user: boolean;
  default_prompt_system: string;
  default_prompt_user: string;
  default_temperature: number;
  default_image_prompt_system: string;
  default_image_prompt_user: string;
  default_image_size: string;
  default_mode: string;
}

export function AdminCoverPage() {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();

  const config = useQuery({
    queryKey: ["admin-cover-settings"],
    queryFn: () =>
      api<CoverSettings>("/admin/cover-settings", { access: token }),
    enabled: !!token,
  });

  const [mode, setMode] = useState<"image" | "svg">("image");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [temperature, setTemperature] = useState(0.5);
  const [forceKeyword, setForceKeyword] = useState(true);
  const [fallbackOnError, setFallbackOnError] = useState(false);
  const [imageSystem, setImageSystem] = useState("");
  const [imageUser, setImageUser] = useState("");
  const [imageSize, setImageSize] = useState("512x768");

  useEffect(() => {
    if (!config.data) return;
    setMode(config.data.mode);
    setSystemPrompt(config.data.prompt_system);
    setUserPrompt(config.data.prompt_user);
    setTemperature(config.data.temperature);
    setForceKeyword(config.data.force_keyword_motif);
    setFallbackOnError(config.data.fallback_on_error);
    setImageSystem(config.data.image_prompt_system);
    setImageUser(config.data.image_prompt_user);
    setImageSize(config.data.image_size);
  }, [config.data]);

  const save = useMutation({
    mutationFn: () =>
      api<CoverSettings>("/admin/cover-settings", {
        method: "PUT",
        access: token,
        body: {
          mode,
          prompt_system: systemPrompt,
          prompt_user: userPrompt,
          temperature,
          force_keyword_motif: forceKeyword,
          fallback_on_error: fallbackOnError,
          image_prompt_system: imageSystem,
          image_prompt_user: imageUser,
          image_size: imageSize,
        },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["admin-cover-settings"], data);
      setMode(data.mode);
      setSystemPrompt(data.prompt_system);
      setUserPrompt(data.prompt_user);
      setTemperature(data.temperature);
      setForceKeyword(data.force_keyword_motif);
      setFallbackOnError(data.fallback_on_error);
      setImageSystem(data.image_prompt_system);
      setImageUser(data.image_prompt_user);
      setImageSize(data.image_size);
    },
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="封面生成"
        description="默认真实文生图。MiniMax 走 /v1/image_generation（模型 image-01）；其它 OpenAI 兼容网关走 /v1/images/generations。也可切回 SVG。"
      />

      {config.isLoading ? <AdminLoading /> : null}
      {config.error instanceof ApiError && (
        <p className="text-sm text-destructive">{config.error.message}</p>
      )}

      <AdminSectionCard
        title="生成模式"
        description="image = 真出图并保存到本地 storage；svg = 文本 LLM 产出 gen:v3 配色 token（旧逻辑）。"
      >
        <div className="flex flex-wrap gap-2">
          {(
            [
              ["image", "文生图（推荐）"],
              ["svg", "参数化 SVG"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={`rounded-full border px-3 py-1.5 text-sm ${
                mode === value
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border/60 bg-card/60 text-muted-foreground"
              }`}
              onClick={() => setMode(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          MiniMax：在同一凭证下新增模型{" "}
          <code className="rounded bg-muted px-1">image-01</code>
          ，绑到「封面文生图」（接口 /v1/image_generation）。SiliconFlow / OpenAI：用{" "}
          <code className="rounded bg-muted px-1">FLUX</code> /{" "}
          <code className="rounded bg-muted px-1">Kolors</code> /{" "}
          <code className="rounded bg-muted px-1">dall-e-3</code>
          （接口 /v1/images/generations）。不要把聊天模型绑到此角色。
        </p>
      </AdminSectionCard>

      {mode === "image" ? (
        <>
          <AdminSectionCard
            title="出图尺寸"
            description="小竖版封面。MiniMax 可用 512x768 或 3:4；OpenAI 兼容网关传 WxH。不要用过大的正方形。"
          >
            <input
              className="admin-input w-40 font-mono"
              value={imageSize}
              onChange={(e) => setImageSize(e.target.value)}
              placeholder="512x768"
              aria-label="文生图尺寸"
            />
            <span className="ml-2 text-xs text-muted-foreground">
              默认 {config.data?.default_image_size ?? "512x768"}
            </span>
          </AdminSectionCard>

          <AdminSectionCard
            title="文生图 System 提示词"
            description="风格约束（会与 User 拼成一条 prompt）。留空保存即恢复内置默认。"
          >
            <textarea
              className="admin-textarea min-h-[160px] font-mono text-[13px] leading-relaxed"
              value={imageSystem}
              onChange={(e) => setImageSystem(e.target.value)}
              spellCheck={false}
              aria-label="文生图 System 提示词"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                className="rounded-full"
                onClick={() => {
                  if (config.data?.default_image_prompt_system) {
                    setImageSystem(config.data.default_image_prompt_system);
                  }
                }}
              >
                恢复默认
              </Button>
              {config.data?.is_custom_image_system ? (
                <span className="text-xs text-muted-foreground">当前为自定义</span>
              ) : (
                <span className="text-xs text-muted-foreground">当前为内置默认</span>
              )}
            </div>
          </AdminSectionCard>

          <AdminSectionCard
            title="文生图 User 提示词模板"
            description="支持 {title}、{description}。描述为空时替换为「（无）」。"
          >
            <textarea
              className="admin-textarea min-h-[120px] font-mono text-[13px] leading-relaxed"
              value={imageUser}
              onChange={(e) => setImageUser(e.target.value)}
              spellCheck={false}
              aria-label="文生图 User 提示词"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                className="rounded-full"
                onClick={() => {
                  if (config.data?.default_image_prompt_user) {
                    setImageUser(config.data.default_image_prompt_user);
                  }
                }}
              >
                恢复默认
              </Button>
              {config.data?.is_custom_image_user ? (
                <span className="text-xs text-muted-foreground">当前为自定义</span>
              ) : (
                <span className="text-xs text-muted-foreground">当前为内置默认</span>
              )}
            </div>
          </AdminSectionCard>
        </>
      ) : (
        <>
          <AdminSectionCard
            title="SVG 生成参数"
            description="温度建议 0.4～0.6。关闭「失败回退」时，模型失败会返回明确错误。"
          >
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm">
                Temperature
                <input
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  className="admin-input w-24"
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                />
                <span className="text-xs text-muted-foreground">
                  默认 {config.data?.default_temperature ?? 0.5}
                </span>
              </label>
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-3 py-2.5">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={forceKeyword}
                  onChange={(e) => setForceKeyword(e.target.checked)}
                />
                <span>
                  <span className="block text-sm font-medium">强制关键词 motif</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    名称命中美食/科技等规则时，强制使用对应纹样。
                  </span>
                </span>
              </label>
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-3 py-2.5">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={fallbackOnError}
                  onChange={(e) => setFallbackOnError(e.target.checked)}
                />
                <span>
                  <span className="block text-sm font-medium">失败时回退本地底稿</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    默认关闭。开启后 LLM 失败仍返回名称驱动的确定性样式。
                  </span>
                </span>
              </label>
            </div>
          </AdminSectionCard>

          <AdminSectionCard
            title="SVG System 提示词"
            description="发给文本 LLM 的系统说明。留空保存即恢复内置默认。"
          >
            <textarea
              className="admin-textarea min-h-[200px] font-mono text-[13px] leading-relaxed"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              spellCheck={false}
              aria-label="封面 System 提示词"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                className="rounded-full"
                onClick={() => {
                  if (config.data?.default_prompt_system) {
                    setSystemPrompt(config.data.default_prompt_system);
                  }
                }}
              >
                恢复默认
              </Button>
              {config.data?.is_custom_system ? (
                <span className="text-xs text-muted-foreground">当前为自定义</span>
              ) : (
                <span className="text-xs text-muted-foreground">当前为内置默认</span>
              )}
            </div>
          </AdminSectionCard>

          <AdminSectionCard
            title="SVG User 提示词模板"
            description="支持占位符 {title}、{description}。"
          >
            <textarea
              className="admin-textarea min-h-[140px] font-mono text-[13px] leading-relaxed"
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              spellCheck={false}
              aria-label="封面 User 提示词"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                className="rounded-full"
                onClick={() => {
                  if (config.data?.default_prompt_user) {
                    setUserPrompt(config.data.default_prompt_user);
                  }
                }}
              >
                恢复默认
              </Button>
              {config.data?.is_custom_user ? (
                <span className="text-xs text-muted-foreground">当前为自定义</span>
              ) : (
                <span className="text-xs text-muted-foreground">当前为内置默认</span>
              )}
            </div>
          </AdminSectionCard>
        </>
      )}

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
