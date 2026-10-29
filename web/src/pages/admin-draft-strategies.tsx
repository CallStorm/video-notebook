import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  AdminEmptyState,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminStatusBadge,
  AdminTableShell,
} from "@/components/admin-shell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Kind = "deep_read" | "action" | "glossary" | "compare" | "custom";
type ModelRef = "inherit" | "claude_code" | "chat";
type GlobalModelRef = "claude_code" | "chat";

interface Settings {
  default_prefix: string;
  default_model_ref: GlobalModelRef;
  output_schema: Record<string, unknown>;
  kind_labels: Record<string, string>;
}

interface Strategy {
  id: number;
  name: string;
  title: string;
  description: string;
  kind: Kind;
  prompt: string;
  apply_default: boolean;
  enabled: boolean;
  suggested_model: ModelRef;
  min_sources: number;
  is_builtin: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface PlaygroundResult {
  strategy_id: number;
  model_used: string;
  model_note: string | null;
  raw_text: string;
  preview: Record<string, unknown> | null;
  parse_ok: boolean;
  parse_error: string | null;
}

const MODEL_LABELS: Record<ModelRef, string> = {
  inherit: "继承全局",
  claude_code: "Claude Code 全局模型",
  chat: "对话模型",
};

const GLOBAL_MODEL_LABELS: Record<GlobalModelRef, string> = {
  claude_code: "Claude Code 全局模型",
  chat: "对话模型（default chat）",
};

type View =
  | { mode: "list" }
  | { mode: "edit"; id: number | "new" }
  | { mode: "playground"; id: number };

export function AdminDraftStrategiesPanel() {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();
  const [view, setView] = useState<View>({ mode: "list" });

  const settingsQ = useQuery({
    queryKey: ["admin-draft-strategy-settings"],
    queryFn: () => api<Settings>("/admin/draft-strategies/settings", { access: token }),
    enabled: !!token,
  });

  const listQ = useQuery({
    queryKey: ["admin-draft-strategies"],
    queryFn: () => api<Strategy[]>("/admin/draft-strategies", { access: token }),
    enabled: !!token,
  });

  const err =
    (settingsQ.error instanceof ApiError && settingsQ.error.message) ||
    (listQ.error instanceof ApiError && listQ.error.message) ||
    null;

  if (view.mode === "edit") {
    return (
      <StrategyEditor
        strategyId={view.id}
        settings={settingsQ.data}
        onBack={() => {
          void qc.invalidateQueries({ queryKey: ["admin-draft-strategies"] });
          setView({ mode: "list" });
        }}
        onPlayground={(id) => setView({ mode: "playground", id })}
      />
    );
  }

  if (view.mode === "playground") {
    return (
      <PlaygroundPanel
        strategyId={view.id}
        settings={settingsQ.data}
        onBack={() => setView({ mode: "edit", id: view.id })}
        onClose={() => setView({ mode: "list" })}
      />
    );
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="底稿策略"
        description="配置知识底稿的全局前缀、默认模型与可复用策略（提示词）。生成底稿功能将读取此处策略；本页可试跑预览 JSON，不会写入笔记本。"
        action={
          <Button
            type="button"
            className="rounded-full"
            onClick={() => setView({ mode: "edit", id: "new" })}
          >
            新建策略
          </Button>
        }
      />

      {err ? (
        <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {err}
        </p>
      ) : null}

      <GlobalPrefixCard settingsQ={settingsQ} token={token} />

      <AdminSectionCard
        title="策略列表"
        description="内置四套不可删除，可停用或改提示词。全局仅一条「默认」。"
      >
        {listQ.isLoading ? (
          <AdminLoading />
        ) : (listQ.data ?? []).length === 0 ? (
          <AdminEmptyState
            title="暂无策略"
            description="重启 API 或刷新后应自动种子内置四套。"
          />
        ) : (
          <StrategyTable
            rows={listQ.data ?? []}
            kindLabels={settingsQ.data?.kind_labels ?? {}}
            token={token}
            onEdit={(id) => setView({ mode: "edit", id })}
            onPlayground={(id) => setView({ mode: "playground", id })}
          />
        )}
      </AdminSectionCard>
    </div>
  );
}

function GlobalPrefixCard({
  settingsQ,
  token,
}: {
  settingsQ: ReturnType<typeof useQuery<Settings>>;
  token: string;
}) {
  const qc = useQueryClient();
  const [prefix, setPrefix] = useState("");
  const [modelRef, setModelRef] = useState<GlobalModelRef>("claude_code");

  useEffect(() => {
    if (!settingsQ.data) return;
    setPrefix(settingsQ.data.default_prefix);
    setModelRef(settingsQ.data.default_model_ref);
  }, [settingsQ.data]);

  const save = useMutation({
    mutationFn: () =>
      api<Settings>("/admin/draft-strategies/settings", {
        method: "PUT",
        access: token,
        body: { default_prefix: prefix, default_model_ref: modelRef },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["admin-draft-strategy-settings"], data);
    },
  });

  return (
    <AdminSectionCard
      title="全局前缀"
      description="拼在所有策略 Prompt 之前：禁臆造、时间锚点、输出契约等。策略正文不必重复这些硬规则。"
    >
      {settingsQ.isLoading ? (
        <AdminLoading />
      ) : (
        <div className="space-y-4">
          <textarea
            className="admin-textarea min-h-[160px] font-mono text-[13px] leading-relaxed"
            value={prefix}
            onChange={(e) => setPrefix(e.target.value)}
            spellCheck={false}
            aria-label="全局前缀"
          />
          <div className="flex flex-wrap items-end gap-4">
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">默认模型引用</span>
              <select
                className="admin-input block min-w-[14rem]"
                value={modelRef}
                onChange={(e) => setModelRef(e.target.value as GlobalModelRef)}
              >
                {(Object.keys(GLOBAL_MODEL_LABELS) as GlobalModelRef[]).map((k) => (
                  <option key={k} value={k}>
                    {GLOBAL_MODEL_LABELS[k]}
                  </option>
                ))}
              </select>
            </label>
            <Button
              type="button"
              className="rounded-full"
              disabled={save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? "保存中…" : "保存全局设置"}
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
      )}
    </AdminSectionCard>
  );
}

function StrategyTable({
  rows,
  kindLabels,
  token,
  onEdit,
  onPlayground,
}: {
  rows: Strategy[];
  kindLabels: Record<string, string>;
  token: string;
  onEdit: (id: number) => void;
  onPlayground: (id: number) => void;
}) {
  const qc = useQueryClient();

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Strategy> }) =>
      api<Strategy>(`/admin/draft-strategies/${id}`, {
        method: "PUT",
        access: token,
        body,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-draft-strategies"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) =>
      api<{ ok: boolean }>(`/admin/draft-strategies/${id}`, {
        method: "DELETE",
        access: token,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-draft-strategies"] });
    },
  });

  return (
    <AdminTableShell>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="px-3 py-2 font-medium">名称</th>
            <th className="px-3 py-2 font-medium">类型</th>
            <th className="px-3 py-2 font-medium">推荐模型</th>
            <th className="px-3 py-2 font-medium">默认</th>
            <th className="px-3 py-2 font-medium">启用</th>
            <th className="px-3 py-2 font-medium text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b last:border-0">
              <td className="px-3 py-2">
                <div className="font-medium">{row.title}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {row.description || row.name}
                  {row.is_builtin ? " · 内置" : ""}
                  {row.min_sources > 1 ? ` · ≥${row.min_sources} 来源` : ""}
                </div>
              </td>
              <td className="px-3 py-2">
                <AdminStatusBadge tone="info">
                  {kindLabels[row.kind] ?? row.kind}
                </AdminStatusBadge>
              </td>
              <td className="px-3 py-2 text-muted-foreground">
                {MODEL_LABELS[row.suggested_model]}
              </td>
              <td className="px-3 py-2">
                <input
                  type="checkbox"
                  checked={row.apply_default}
                  disabled={patch.isPending}
                  onChange={(e) =>
                    patch.mutate({ id: row.id, body: { apply_default: e.target.checked } })
                  }
                  aria-label={`${row.title} 设为默认`}
                />
              </td>
              <td className="px-3 py-2">
                <input
                  type="checkbox"
                  checked={row.enabled}
                  disabled={patch.isPending}
                  onChange={(e) =>
                    patch.mutate({ id: row.id, body: { enabled: e.target.checked } })
                  }
                  aria-label={`${row.title} 启用`}
                />
              </td>
              <td className="px-3 py-2 text-right">
                <div className="flex flex-wrap justify-end gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onEdit(row.id)}
                  >
                    编辑
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onPlayground(row.id)}
                  >
                    试跑
                  </Button>
                  {!row.is_builtin ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-destructive"
                      disabled={remove.isPending}
                      onClick={() => {
                        if (window.confirm(`删除策略「${row.title}」？`)) {
                          remove.mutate(row.id);
                        }
                      }}
                    >
                      删除
                    </Button>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {patch.isError || remove.isError ? (
        <p className="mt-2 text-sm text-destructive">
          {(patch.error instanceof ApiError && patch.error.message) ||
            (remove.error instanceof ApiError && remove.error.message) ||
            "操作失败"}
        </p>
      ) : null}
    </AdminTableShell>
  );
}

function StrategyEditor({
  strategyId,
  settings,
  onBack,
  onPlayground,
}: {
  strategyId: number | "new";
  settings: Settings | undefined;
  onBack: () => void;
  onPlayground: (id: number) => void;
}) {
  const { access } = useAuth();
  const token = access ?? "";
  const isNew = strategyId === "new";

  const detailQ = useQuery({
    queryKey: ["admin-draft-strategy", strategyId],
    queryFn: () =>
      api<Strategy>(`/admin/draft-strategies/${strategyId}`, { access: token }),
    enabled: !!token && !isNew,
  });

  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState<Kind>("custom");
  const [prompt, setPrompt] = useState("");
  const [applyDefault, setApplyDefault] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [suggestedModel, setSuggestedModel] = useState<ModelRef>("inherit");
  const [minSources, setMinSources] = useState(1);
  const [isBuiltin, setIsBuiltin] = useState(false);

  useEffect(() => {
    if (isNew) {
      setName("");
      setTitle("");
      setDescription("");
      setKind("custom");
      setPrompt("");
      setApplyDefault(false);
      setEnabled(true);
      setSuggestedModel("inherit");
      setMinSources(1);
      setIsBuiltin(false);
      return;
    }
    const row = detailQ.data;
    if (!row) return;
    setName(row.name);
    setTitle(row.title);
    setDescription(row.description);
    setKind(row.kind);
    setPrompt(row.prompt);
    setApplyDefault(row.apply_default);
    setEnabled(row.enabled);
    setSuggestedModel(row.suggested_model);
    setMinSources(row.min_sources);
    setIsBuiltin(row.is_builtin);
  }, [detailQ.data, isNew]);

  const save = useMutation({
    mutationFn: async () => {
      if (isNew) {
        return api<Strategy>("/admin/draft-strategies", {
          method: "POST",
          access: token,
          body: {
            name,
            title,
            description,
            kind,
            prompt,
            apply_default: applyDefault,
            enabled,
            suggested_model: suggestedModel,
            min_sources: minSources,
          },
        });
      }
      const body: Record<string, unknown> = {
        title,
        description,
        prompt,
        apply_default: applyDefault,
        enabled,
        suggested_model: suggestedModel,
        min_sources: minSources,
      };
      if (!isBuiltin) {
        body.name = name;
        body.kind = kind;
      }
      return api<Strategy>(`/admin/draft-strategies/${strategyId}`, {
        method: "PUT",
        access: token,
        body,
      });
    },
    onSuccess: (row) => {
      if (isNew) {
        onPlayground(row.id);
      } else {
        onBack();
      }
    },
  });

  const schemaText = useMemo(
    () => JSON.stringify(settings?.output_schema ?? {}, null, 2),
    [settings?.output_schema],
  );

  if (!isNew && detailQ.isLoading) {
    return (
      <div className="space-y-4">
        <Button type="button" variant="outline" className="rounded-full" onClick={onBack}>
          ← 返回列表
        </Button>
        <AdminLoading />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button type="button" variant="outline" className="rounded-full" onClick={onBack}>
          ← 返回列表
        </Button>
        <div className="flex flex-wrap gap-2">
          {!isNew && typeof strategyId === "number" ? (
            <Button
              type="button"
              variant="outline"
              className="rounded-full"
              onClick={() => onPlayground(strategyId)}
            >
              试跑
            </Button>
          ) : null}
          <Button
            type="button"
            className="rounded-full"
            disabled={save.isPending || !title.trim() || (isNew && !name.trim())}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "保存中…" : isNew ? "创建并试跑" : "保存"}
          </Button>
        </div>
      </div>

      <AdminPageHeader
        title={isNew ? "新建策略" : `编辑 · ${title || name}`}
        description={
          isBuiltin
            ? "内置策略可改提示词与开关，不可改 name/类型，不可删除。"
            : "自定义策略需输出统一底稿 JSON；schema 见右侧只读框。"
        }
      />

      {save.isError ? (
        <p className="text-sm text-destructive">
          {save.error instanceof ApiError ? save.error.message : "保存失败"}
        </p>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <AdminSectionCard title="字段">
          <div className="space-y-3">
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">name（稳定键）</span>
              <input
                className="admin-input w-full font-mono text-sm"
                value={name}
                disabled={isBuiltin}
                onChange={(e) => setName(e.target.value)}
                placeholder="my_strategy"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">标题</span>
              <input
                className="admin-input w-full"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">说明</span>
              <input
                className="admin-input w-full"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">类型</span>
              <select
                className="admin-input w-full"
                value={kind}
                disabled={isBuiltin}
                onChange={(e) => setKind(e.target.value as Kind)}
              >
                {Object.entries(settings?.kind_labels ?? {
                  deep_read: "精读",
                  action: "行动",
                  glossary: "词典",
                  compare: "对比",
                  custom: "自定义",
                }).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">推荐模型</span>
              <select
                className="admin-input w-full"
                value={suggestedModel}
                onChange={(e) => setSuggestedModel(e.target.value as ModelRef)}
              >
                {(Object.keys(MODEL_LABELS) as ModelRef[]).map((k) => (
                  <option key={k} value={k}>
                    {MODEL_LABELS[k]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">最少来源数</span>
              <input
                type="number"
                min={1}
                max={20}
                className="admin-input w-28"
                value={minSources}
                onChange={(e) => setMinSources(Number(e.target.value) || 1)}
              />
            </label>
            <div className="flex flex-wrap gap-4 pt-1 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={applyDefault}
                  onChange={(e) => setApplyDefault(e.target.checked)}
                />
                设为默认
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                />
                启用
              </label>
            </div>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">策略 Prompt</span>
              <textarea
                className="admin-textarea min-h-[240px] font-mono text-[13px] leading-relaxed"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                spellCheck={false}
              />
            </label>
          </div>
        </AdminSectionCard>

        <AdminSectionCard
          title="统一输出契约（只读）"
          description="所有策略必须产出此 JSON shape；不可在策略里改字段名。"
        >
          <pre className="admin-textarea max-h-[28rem] overflow-auto whitespace-pre-wrap font-mono text-[12px] leading-relaxed">
            {schemaText}
          </pre>
        </AdminSectionCard>
      </div>
    </div>
  );
}

function PlaygroundPanel({
  strategyId,
  settings,
  onBack,
  onClose,
}: {
  strategyId: number;
  settings: Settings | undefined;
  onBack: () => void;
  onClose: () => void;
}) {
  const { access } = useAuth();
  const token = access ?? "";
  const [sourceText, setSourceText] = useState(
    "（试跑示例）\n[00:12] 今天讲灰度发布的三个原则。\n[01:05] 先小流量验证，再全量切换。\n[02:40] 做好回滚预案。",
  );
  const [videoId, setVideoId] = useState("");
  const [modelOverride, setModelOverride] = useState<ModelRef | "">("");
  const [result, setResult] = useState<PlaygroundResult | null>(null);

  const detailQ = useQuery({
    queryKey: ["admin-draft-strategy", strategyId],
    queryFn: () =>
      api<Strategy>(`/admin/draft-strategies/${strategyId}`, { access: token }),
    enabled: !!token,
  });

  const run = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { strategy_id: strategyId };
      const vid = videoId.trim();
      if (vid) {
        body.video_id = Number(vid);
      } else {
        body.source_text = sourceText;
      }
      if (modelOverride) body.model_override = modelOverride;
      return api<PlaygroundResult>("/admin/draft-strategies/playground", {
        method: "POST",
        access: token,
        body,
      });
    },
    onSuccess: (data) => setResult(data),
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          <Button type="button" variant="outline" className="rounded-full" onClick={onBack}>
            ← 返回编辑
          </Button>
          <Button type="button" variant="ghost" className="rounded-full" onClick={onClose}>
            关闭到列表
          </Button>
        </div>
        <Button
          type="button"
          className="rounded-full"
          disabled={run.isPending}
          onClick={() => run.mutate()}
        >
          {run.isPending ? "试跑中…" : "试跑"}
        </Button>
      </div>

      <AdminPageHeader
        title={`试跑 · ${detailQ.data?.title ?? `#${strategyId}`}`}
        description="调用默认聊天模型，拼接全局前缀 + 策略 Prompt + 输出契约。结果不入库。"
      />

      <div className="grid gap-5 lg:grid-cols-2">
        <AdminSectionCard title="输入">
          <div className="space-y-3">
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">
                video_id（可选；填写则忽略下方粘贴文本）
              </span>
              <input
                className="admin-input w-full font-mono"
                value={videoId}
                onChange={(e) => setVideoId(e.target.value)}
                placeholder="例如 21"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">或粘贴字幕片段</span>
              <textarea
                className="admin-textarea min-h-[220px] font-mono text-[13px]"
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                spellCheck={false}
                disabled={!!videoId.trim()}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">模型覆盖（可选）</span>
              <select
                className="admin-input w-full"
                value={modelOverride}
                onChange={(e) => setModelOverride(e.target.value as ModelRef | "")}
              >
                <option value="">策略推荐 / 继承</option>
                {(Object.keys(MODEL_LABELS) as ModelRef[]).map((k) => (
                  <option key={k} value={k}>
                    {MODEL_LABELS[k]}
                  </option>
                ))}
              </select>
            </label>
            {run.isError ? (
              <p className="text-sm text-destructive">
                {run.error instanceof ApiError ? run.error.message : "试跑失败"}
              </p>
            ) : null}
          </div>
        </AdminSectionCard>

        <AdminSectionCard title="JSON 预览">
          {!result ? (
            <p className="text-sm text-muted-foreground">尚未试跑</p>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span>模型：{result.model_used}</span>
                {result.model_note ? <span>· {result.model_note}</span> : null}
                <AdminStatusBadge tone={result.parse_ok ? "ok" : "warn"}>
                  {result.parse_ok ? "解析成功" : "解析失败"}
                </AdminStatusBadge>
              </div>
              {result.parse_error ? (
                <p className="text-sm text-destructive">{result.parse_error}</p>
              ) : null}
              <pre className="admin-textarea max-h-[24rem] overflow-auto whitespace-pre-wrap font-mono text-[12px]">
                {result.preview
                  ? JSON.stringify(result.preview, null, 2)
                  : result.raw_text || "（空）"}
              </pre>
            </div>
          )}
          <details className="mt-3">
            <summary className="cursor-pointer text-xs text-muted-foreground">
              输出契约参考
            </summary>
            <pre className="mt-2 max-h-40 overflow-auto font-mono text-[11px] text-muted-foreground">
              {JSON.stringify(settings?.output_schema ?? {}, null, 2)}
            </pre>
          </details>
        </AdminSectionCard>
      </div>
    </div>
  );
}

export default function AdminDraftStrategiesPage() {
  return <AdminDraftStrategiesPanel />;
}
