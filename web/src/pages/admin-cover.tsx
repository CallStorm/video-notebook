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
  image_prompt_system: string;
  image_prompt_user: string;
  image_size: string;
  is_custom_image_system: boolean;
  is_custom_image_user: boolean;
  default_image_prompt_system: string;
  default_image_prompt_user: string;
  default_image_size: string;
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

  const [imageSystem, setImageSystem] = useState("");
  const [imageUser, setImageUser] = useState("");
  const [imageSize, setImageSize] = useState("512x768");

  useEffect(() => {
    if (!config.data) return;
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
          image_prompt_system: imageSystem,
          image_prompt_user: imageUser,
          image_size: imageSize,
        },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["admin-cover-settings"], data);
      setImageSystem(data.image_prompt_system);
      setImageUser(data.image_prompt_user);
      setImageSize(data.image_size);
    },
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="封面生成"
        description="仅文生图。MiniMax 走 /v1/image_generation（模型 image-01）；其它 OpenAI 兼容网关走 /v1/images/generations。"
      />

      {config.isLoading ? <AdminLoading /> : null}
      {config.error instanceof ApiError && (
        <p className="text-sm text-destructive">{config.error.message}</p>
      )}

      <AdminSectionCard
        title="出图说明"
        description="请到「模型配置」为「封面文生图」绑定出图模型。不要把聊天模型绑到此角色。"
      >
        <p className="text-xs text-muted-foreground">
          MiniMax：同一凭证下新增模型{" "}
          <code className="rounded bg-muted px-1">image-01</code>
          。SiliconFlow / OpenAI：用{" "}
          <code className="rounded bg-muted px-1">FLUX</code> /{" "}
          <code className="rounded bg-muted px-1">Kolors</code> /{" "}
          <code className="rounded bg-muted px-1">dall-e-3</code>。
        </p>
      </AdminSectionCard>

      <AdminSectionCard
        title="出图尺寸"
        description="小竖版封面。MiniMax 可用 512x768 或 3:4；OpenAI 兼容网关传 WxH。"
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
