import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminFieldLabel,
} from "@/components/admin-shell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface VectorSettings {
  vector_backend: string;
  qdrant_url: string;
  qdrant_api_key: string | null;
  qdrant_api_key_set: boolean;
  qdrant_collection: string;
  index_title: boolean;
  index_description: boolean;
  index_overview: boolean;
  index_subtitles: boolean;
  index_notes: boolean;
}

interface ReindexAllResult {
  queued: number;
  message: string;
}

export function AdminVectorPage() {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();

  const config = useQuery({
    queryKey: ["admin-vector-settings"],
    queryFn: () => api<VectorSettings>("/admin/vector-settings", { access: token }),
    enabled: !!token,
  });

  const [backend, setBackend] = useState("qdrant");
  const [qdrantUrl, setQdrantUrl] = useState("http://127.0.0.1:6333");
  const [qdrantApiKey, setQdrantApiKey] = useState("");
  const [clearKey, setClearKey] = useState(false);
  const [collection, setCollection] = useState("notebooks");
  const [indexTitle, setIndexTitle] = useState(true);
  const [indexDescription, setIndexDescription] = useState(true);
  const [indexOverview, setIndexOverview] = useState(true);
  const [indexSubtitles, setIndexSubtitles] = useState(false);
  const [indexNotes, setIndexNotes] = useState(false);

  useEffect(() => {
    if (!config.data) return;
    setBackend(config.data.vector_backend || "qdrant");
    setQdrantUrl(config.data.qdrant_url || "http://127.0.0.1:6333");
    setCollection(config.data.qdrant_collection || "notebooks");
    setIndexTitle(config.data.index_title);
    setIndexDescription(config.data.index_description);
    setIndexOverview(config.data.index_overview);
    setIndexSubtitles(config.data.index_subtitles);
    setIndexNotes(config.data.index_notes);
    setQdrantApiKey("");
    setClearKey(false);
  }, [config.data]);

  const save = useMutation({
    mutationFn: () =>
      api<VectorSettings>("/admin/vector-settings", {
        method: "PUT",
        access: token,
        body: {
          vector_backend: backend.trim() || "qdrant",
          qdrant_url: qdrantUrl.trim(),
          qdrant_api_key: qdrantApiKey.trim() ? qdrantApiKey.trim() : null,
          clear_qdrant_api_key: clearKey,
          qdrant_collection: collection.trim() || "notebooks",
          index_title: indexTitle,
          index_description: indexDescription,
          index_overview: indexOverview,
          index_subtitles: indexSubtitles,
          index_notes: indexNotes,
        },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["admin-vector-settings"], data);
      setQdrantApiKey("");
      setClearKey(false);
    },
  });

  const reindexAll = useMutation({
    mutationFn: () =>
      api<ReindexAllResult>("/admin/vector-settings/reindex-all", {
        method: "POST",
        access: token,
        body: {},
      }),
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="向量配置"
        description="语义检索用：选向量后端（Qdrant）、连接地址，以及每本笔记本索引哪些字段。一期默认索引标题、描述、来源概览；字幕/笔记可开。改字段后需重新索引才生效。"
      />

      {config.isLoading ? <AdminLoading /> : null}
      {config.error instanceof ApiError && (
        <p className="text-sm text-destructive">{config.error.message}</p>
      )}

      <AdminSectionCard
        title="向量后端"
        description="向量存在 Qdrant；MySQL 只记索引状态。本地可用 compose 起 Qdrant，或 docker run -p 6333:6333 qdrant/qdrant。"
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <AdminFieldLabel hint="目前仅支持 qdrant。pending 表示尚未接库。">
              后端
            </AdminFieldLabel>
            <select
              className="admin-select h-9 w-full max-w-xs"
              value={backend}
              onChange={(e) => setBackend(e.target.value)}
            >
              <option value="qdrant">qdrant</option>
              <option value="pending">pending（未启用）</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <AdminFieldLabel hint="默认 http://127.0.0.1:6333">Qdrant URL</AdminFieldLabel>
            <Input
              value={qdrantUrl}
              onChange={(e) => setQdrantUrl(e.target.value)}
              placeholder="http://127.0.0.1:6333"
              className="max-w-xl"
            />
          </div>

          <div className="space-y-1.5">
            <AdminFieldLabel
              hint={
                config.data?.qdrant_api_key_set
                  ? "已保存密钥。留空保存则保持不变；勾选下方可清空。"
                  : "本地一般不需要。云托管 Qdrant 再填。"
              }
            >
              Qdrant API Key（可选）
            </AdminFieldLabel>
            <Input
              type="password"
              value={qdrantApiKey}
              onChange={(e) => setQdrantApiKey(e.target.value)}
              placeholder={config.data?.qdrant_api_key_set ? "••••••••（已配置）" : "可选"}
              className="max-w-xl"
              autoComplete="off"
            />
            {config.data?.qdrant_api_key_set ? (
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={clearKey}
                  onChange={(e) => setClearKey(e.target.checked)}
                />
                清空已保存的 API Key
              </label>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <AdminFieldLabel hint="Qdrant collection 名，默认 notebooks">
              Collection
            </AdminFieldLabel>
            <Input
              value={collection}
              onChange={(e) => setCollection(e.target.value)}
              className="max-w-xs"
            />
          </div>
        </div>
      </AdminSectionCard>

      <AdminSectionCard
        title="索引字段"
        description="拼成一篇文档再 embedding。一期建议开：标题 + 描述 + 概览。字幕/笔记体量大，默认关。"
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Toggle
            label="标题"
            checked={indexTitle}
            onChange={setIndexTitle}
            hint="笔记本标题"
          />
          <Toggle
            label="描述"
            checked={indexDescription}
            onChange={setIndexDescription}
            hint="笔记本描述"
          />
          <Toggle
            label="概览"
            checked={indexOverview}
            onChange={setIndexOverview}
            hint="各来源的 AI 概览与视频标题"
          />
          <Toggle
            label="字幕"
            checked={indexSubtitles}
            onChange={setIndexSubtitles}
            hint="口播字幕全文（量大，二期可用）"
          />
          <Toggle
            label="笔记"
            checked={indexNotes}
            onChange={setIndexNotes}
            hint="保存的对话笔记"
          />
        </div>
      </AdminSectionCard>

      <AdminSectionCard
        title="全量重建"
        description="给所有未删除笔记本排队重新索引。需 API 已配默认「向量」模型，且 media-worker、Qdrant 在跑。"
      >
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="outline"
            className="rounded-full"
            disabled={reindexAll.isPending}
            onClick={() => {
              if (window.confirm("确认排队全量重新索引？")) reindexAll.mutate();
            }}
          >
            {reindexAll.isPending ? "排队中…" : "全量重建索引"}
          </Button>
          {reindexAll.isSuccess ? (
            <span className="text-sm text-[hsl(var(--success))]">
              {reindexAll.data.message}
            </span>
          ) : null}
          {reindexAll.isError ? (
            <span className="text-sm text-destructive">
              {reindexAll.error instanceof ApiError
                ? reindexAll.error.message
                : "排队失败"}
            </span>
          ) : null}
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

function Toggle({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  hint?: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-3 py-2.5">
      <input
        type="checkbox"
        className="mt-1"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        <span className="block text-sm font-medium">{label}</span>
        {hint ? <span className="mt-0.5 block text-xs text-muted-foreground">{hint}</span> : null}
      </span>
    </label>
  );
}
