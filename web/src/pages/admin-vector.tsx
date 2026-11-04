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
  index_conclusions: boolean;
  index_draft: boolean;
  chunk_card_chars: number;
  chunk_subtitles_chars: number;
  chunk_notes_chars: number;
  chunk_conclusions_chars: number;
  chunk_draft_chars: number;
  chunk_overlap_chars: number;
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
  const [indexSubtitles, setIndexSubtitles] = useState(true);
  const [indexNotes, setIndexNotes] = useState(true);
  const [indexConclusions, setIndexConclusions] = useState(true);
  const [indexDraft, setIndexDraft] = useState(true);
  const [chunkCard, setChunkCard] = useState(6000);
  const [chunkSubtitles, setChunkSubtitles] = useState(6000);
  const [chunkNotes, setChunkNotes] = useState(6000);
  const [chunkConclusions, setChunkConclusions] = useState(6000);
  const [chunkDraft, setChunkDraft] = useState(6000);
  const [chunkOverlap, setChunkOverlap] = useState(200);

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
    setIndexConclusions(config.data.index_conclusions);
    setIndexDraft(config.data.index_draft);
    setChunkCard(config.data.chunk_card_chars ?? 6000);
    setChunkSubtitles(config.data.chunk_subtitles_chars ?? 6000);
    setChunkNotes(config.data.chunk_notes_chars ?? 6000);
    setChunkConclusions(config.data.chunk_conclusions_chars ?? 6000);
    setChunkDraft(config.data.chunk_draft_chars ?? 6000);
    setChunkOverlap(config.data.chunk_overlap_chars ?? 200);
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
          index_conclusions: indexConclusions,
          index_draft: indexDraft,
          chunk_card_chars: chunkCard,
          chunk_subtitles_chars: chunkSubtitles,
          chunk_notes_chars: chunkNotes,
          chunk_conclusions_chars: chunkConclusions,
          chunk_draft_chars: chunkDraft,
          chunk_overlap_chars: chunkOverlap,
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
        description="语义检索用：选向量后端（Qdrant）、连接地址，以及哪些内容写入索引。每一类单独成段，超过切割字数再切开。默认全部索引。保存字段开关或切割参数后会自动排队重建；笔记、底稿、标题这些内容一变也会自动索引。"
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
        description="每一类各写自己的向量。关掉某一项后，保存会按新字段重新索引现有笔记本。"
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
            hint="口播字幕全文"
          />
          <Toggle
            label="笔记"
            checked={indexNotes}
            onChange={setIndexNotes}
            hint="笔记标题和正文"
          />
          <Toggle
            label="我的结论"
            checked={indexConclusions}
            onChange={setIndexConclusions}
            hint="知识底稿里手写的结论"
          />
          <Toggle
            label="底稿"
            checked={indexDraft}
            onChange={setIndexDraft}
            hint="主题、概念、要点、收获和待问"
          />
        </div>
      </AdminSectionCard>

      <AdminSectionCard
        title="分段"
        description="某一类超过切割字数才切开，相邻段重叠一段，避免一句话正好被切断。建议 6000 字以内，再长可能被向量模型拒绝。改完保存后，现有笔记本会排队按新长度重建。"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <ChunkField
            label="简介"
            hint="标题、描述、概览放在一起。多个来源超长时按来源再切。"
            value={chunkCard}
            onChange={setChunkCard}
          />
          <ChunkField
            label="字幕"
            hint="每个来源单独成段，超长再按这个字数切开。"
            value={chunkSubtitles}
            onChange={setChunkSubtitles}
          />
          <ChunkField
            label="笔记"
            hint="一条笔记一段，超长再切这一条。"
            value={chunkNotes}
            onChange={setChunkNotes}
          />
          <ChunkField
            label="我的结论"
            hint="全部结论放在一起，超长再切。"
            value={chunkConclusions}
            onChange={setChunkConclusions}
          />
          <ChunkField
            label="底稿"
            hint="主题、概念、要点、收获和待问。超长再切底稿。"
            value={chunkDraft}
            onChange={setChunkDraft}
          />
          <ChunkField
            label="重叠"
            hint="相邻两段重复的字数。必须小于每一类的切割字数。"
            value={chunkOverlap}
            onChange={setChunkOverlap}
            min={0}
            max={2000}
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

function ChunkField({
  label,
  hint,
  value,
  onChange,
  min = 500,
  max = 10000,
}: {
  label: string;
  hint: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <div className="space-y-1.5">
      <AdminFieldLabel hint={hint}>{label}</AdminFieldLabel>
      <Input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const next = Number(e.target.value);
          if (Number.isFinite(next)) onChange(Math.round(next));
        }}
        className="max-w-xs"
      />
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
  hint,
  disabled = false,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  hint?: string;
  disabled?: boolean;
}) {
  return (
    <label
      className={`flex items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-3 py-2.5 ${
        disabled ? "cursor-not-allowed opacity-80" : "cursor-pointer"
      }`}
    >
      <input
        type="checkbox"
        className="mt-1"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        <span className="block text-sm font-medium">{label}</span>
        {hint ? <span className="mt-0.5 block text-xs text-muted-foreground">{hint}</span> : null}
      </span>
    </label>
  );
}
