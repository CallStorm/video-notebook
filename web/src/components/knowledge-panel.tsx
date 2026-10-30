import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Check,
  Loader2,
  Network,
  PanelRightClose,
  Plus,
  Presentation,
  RefreshCw,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { parseClockToSeconds } from "@/components/studio-notes";

type ModelRef = "inherit" | "claude_code" | "chat";
type Language = "中文" | "English";
type ExampleKind = "life" | "allusion" | "work" | "other";

type AskTurn = { role: "user" | "assistant"; content: string };

const ASK_CHIPS: { id: string; label: string; message: string }[] = [
  { id: "explain", label: "解释这句", message: "请用通俗的话解释这句原句在说什么。" },
  { id: "theme", label: "和主题关系", message: "这句原句和整段主题有什么关系？帮我串一下。" },
  { id: "life", label: "举个生活例子", message: "就这句原句，再举一个贴近生活的例子帮助理解。" },
];

export interface KnowledgeSource {
  video_id: number;
  selected_for_chat: boolean;
  video: { title: string | null; source_url: string | null };
}

export interface KnowledgeNote {
  id: number;
  title: string;
  selected_for_chat: boolean;
}

interface StrategyOption {
  id: number;
  name: string;
  title: string;
  description: string;
  kind: string;
  apply_default: boolean;
  suggested_model: ModelRef;
  min_sources: number;
}

interface DraftPoint {
  id: string;
  text: string;
  time?: string | null;
  evidence?: string | null;
  source_hint?: string | null;
  video_id?: number | null;
  checked: boolean;
  example?: string | null;
  example_kind?: ExampleKind | null;
  comment?: string | null;
}

interface DraftTakeaway {
  id: string;
  text: string;
  checked: boolean;
}

interface DraftConcept {
  term: string;
  definition: string;
}

interface KnowledgeDraft {
  id: number;
  notebook_id: number;
  strategy_id: number | null;
  strategy_title: string | null;
  status: string;
  language: string;
  model_ref: string;
  model_used: string | null;
  conclusion: string;
  conclusions: string[];
  content: {
    theme: string;
    concepts: DraftConcept[];
    points: DraftPoint[];
    takeaways: DraftTakeaway[];
    open_questions: string[];
  };
  source_video_ids: number[];
  source_note_ids: number[];
  error_message: string | null;
  updated_at: string | null;
}

const MODEL_LABELS: Record<ModelRef, string> = {
  inherit: "策略推荐",
  claude_code: "Claude Code 全局模型",
  chat: "对话模型",
};


function pointEvidence(point: DraftPoint): string | null {
  return (point.evidence || "").trim() || null;
}

function pointExample(point: DraftPoint): string | null {
  return (point.example || "").trim() || null;
}

function pointComment(point: DraftPoint): string | null {
  return (point.comment || "").trim() || null;
}

function sourceTitle(source: KnowledgeSource): string {
  return source.video.title || source.video.source_url || `来源 ${source.video_id}`;
}

function toggleId(ids: number[], id: number): number[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}

function normalizeConclusions(draft: KnowledgeDraft | null | undefined): string[] {
  if (!draft) return [];
  if (Array.isArray(draft.conclusions) && draft.conclusions.length) {
    return draft.conclusions.map((s) => String(s));
  }
  const legacy = (draft.conclusion || "").trim();
  return legacy ? [legacy] : [];
}


interface StudioCapability {
  id: number;
  name: string;
  icon: string | null;
  format_key: string;
}

interface StudioTaskCreated {
  id: number;
  format_key: string;
  status: string;
}

const TOPIC_MAX = 80;

function truncateText(value: string, max: number): string {
  const t = value.trim();
  if (t.length <= max) return t;
  return t.slice(0, max - 1) + "…";
}

function draftLanguage(draft: KnowledgeDraft): Language {
  return draft.language === "English" ? "English" : "中文";
}

function pointsForExport(draft: KnowledgeDraft): { points: DraftPoint[]; usedAll: boolean } {
  const checked = draft.content.points.filter((p) => p.checked);
  if (checked.length > 0) return { points: checked, usedAll: false };
  return { points: draft.content.points, usedAll: true };
}

function formatPointBlock(point: DraftPoint, index: number): string {
  const lines = [`${index}. ${point.text.trim()}`];
  const evidence = pointEvidence(point);
  const example = pointExample(point);
  if (evidence) lines.push(`   原句：${evidence}`);
  if (example) lines.push(`   例：${example}`);
  return lines.join("\n");
}

function buildMindMapFields(draft: KnowledgeDraft, points: DraftPoint[]): Record<string, string> {
  const theme = (draft.content.theme || "").trim();
  const topic = truncateText(theme || "知识要点导图", TOPIC_MAX);
  const parts: string[] = [
    "请严格围绕下列要点组织导图，不要扩写成全片大纲。",
    "",
    "要点：",
  ];
  points.forEach((p, i) => parts.push(formatPointBlock(p, i + 1)));
  const conclusions = normalizeConclusions(draft);
  if (conclusions.length) {
    parts.push("", "结论：");
    conclusions.forEach((c, i) => parts.push(`${i + 1}. ${c}`));
  }
  return {
    topic,
    focus_mode: "action",
    extra_constraints: parts.join("\n"),
  };
}

function buildSlidesBrief(draft: KnowledgeDraft, points: DraftPoint[]): string {
  const theme = (draft.content.theme || "").trim() || "知识要点";
  const n = points.length;
  const parts: string[] = [
    "受众：自学复盘",
    "结构建议：封面 → 要点展开 → 结论/行动",
    `页数：约 ${n + 2} 页（封面 1 + 要点 ${n} + 结论/行动 1）`,
    `主题：${theme}`,
    "",
    "要点：",
  ];
  points.forEach((p, i) => {
    parts.push(`${i + 1}. ${p.text.trim()}`);
    const evidence = pointEvidence(p);
    const example = pointExample(p);
    if (evidence) parts.push(`   原句摘要：${truncateText(evidence, 120)}`);
    if (example) parts.push(`   例：${truncateText(example, 120)}`);
  });
  const conclusions = normalizeConclusions(draft);
  if (conclusions.length) {
    parts.push("", "结论：");
    conclusions.forEach((c, i) => parts.push(`${i + 1}. ${c}`));
  }
  return parts.join("\n");
}


function shortSlideTitle(draft: KnowledgeDraft, points: DraftPoint[]): string {
  const theme = (draft.content.theme || "").trim();
  if (theme) return truncateText(theme, 24);
  const first = points.find((p) => p.text.trim())?.text.trim();
  if (first) return truncateText(first, 24);
  return "知识要点";
}

function buildSlidesFields(draft: KnowledgeDraft, points: DraftPoint[]): Record<string, string> {
  return {
    title: shortSlideTitle(draft, points),
    brief: buildSlidesBrief(draft, points),
  };
}

function resolveSourceIds(
  draft: KnowledgeDraft,
  sources: KnowledgeSource[],
  notes: KnowledgeNote[],
): { video_ids: number[]; note_ids: number[] } {
  let video_ids = [...(draft.source_video_ids || [])];
  let note_ids = [...(draft.source_note_ids || [])];
  if (video_ids.length === 0 && note_ids.length === 0) {
    video_ids = sources.filter((s) => s.selected_for_chat).map((s) => s.video_id);
    note_ids = notes.filter((n) => n.selected_for_chat).map((n) => n.id);
  }
  return { video_ids, note_ids };
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-2 text-[11px] font-semibold tracking-wide text-primary/80">
      <span className="h-px flex-1 bg-primary/15" />
      <span>{children}</span>
      <span className="h-px flex-1 bg-primary/15" />
    </div>
  );
}

export function KnowledgePanel({
  access,
  notebookId,
  sources,
  notes,
  onCollapse,
  onSeekVideo,
  onOpenStudio,
  onStudioTaskCreated,
  embedded = false,
}: {
  access: string;
  notebookId: number;
  sources: KnowledgeSource[];
  notes: KnowledgeNote[];
  onCollapse?: () => void;
  onSeekVideo?: (videoId: number, timeSec: number) => void;
  onOpenStudio?: () => void;
  onStudioTaskCreated?: (taskId: number, formatKey: string) => void;
  /** Parent right-rail tabs own mode switch + collapse */
  embedded?: boolean;
}) {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [conceptFilter, setConceptFilter] = useState<string | null>(null);
  const [conclusionsDraft, setConclusionsDraft] = useState<string[]>([]);
  const [editingPointId, setEditingPointId] = useState<string | null>(null);
  const [editingPointText, setEditingPointText] = useState("");
  const [commentEditingId, setCommentEditingId] = useState<string | null>(null);
  const [commentDraft, setCommentDraft] = useState("");
  const [askPointId, setAskPointId] = useState<string | null>(null);
  const [askInput, setAskInput] = useState("");
  const [askTurnsByPoint, setAskTurnsByPoint] = useState<Record<string, AskTurn[]>>({});
  const [askError, setAskError] = useState<string | null>(null);
  const [askPos, setAskPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const askAnchorRef = useRef<HTMLElement | null>(null);
  const askPopoverRef = useRef<HTMLDivElement | null>(null);

  const [strategyId, setStrategyId] = useState<number | null>(null);
  const [language, setLanguage] = useState<Language>("中文");
  const [model, setModel] = useState<ModelRef>("inherit");
  const [videoIds, setVideoIds] = useState<number[]>([]);
  const [noteIds, setNoteIds] = useState<number[]>([]);
  const [focus, setFocus] = useState("");
  const [extra, setExtra] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const strategiesQ = useQuery({
    queryKey: ["draft-strategies", notebookId],
    queryFn: () =>
      api<StrategyOption[]>(`/notebooks/${notebookId}/draft-strategies`, { access }),
    enabled: !!access && !!notebookId,
  });

  const draftQ = useQuery({
    queryKey: ["knowledge-draft", notebookId],
    queryFn: () =>
      api<KnowledgeDraft | null>(`/notebooks/${notebookId}/knowledge-draft`, { access }),
    enabled: !!access && !!notebookId,
  });

  const draft = draftQ.data ?? null;

  const [studioAction, setStudioAction] = useState<"mind_map" | "slides" | null>(null);
  const [studioError, setStudioError] = useState<string | null>(null);

  const capabilitiesQ = useQuery({
    queryKey: ["studio-capabilities", notebookId],
    queryFn: () =>
      api<StudioCapability[]>(`/notebooks/${notebookId}/studio/capabilities`, { access }),
    enabled: !!access && !!notebookId,
  });

  const createStudioTask = useMutation({
    mutationFn: (body: {
      capability_id: number;
      language?: string;
      video_ids: number[];
      note_ids: number[];
      fields: Record<string, string>;
    }) =>
      api<StudioTaskCreated>(`/notebooks/${notebookId}/studio/tasks`, {
        method: "POST",
        access,
        body,
      }),
    onSuccess: (task) => {
      setStudioError(null);
      setStudioAction(null);
      void qc.invalidateQueries({ queryKey: ["studio-tasks", notebookId] });
      onStudioTaskCreated?.(task.id, task.format_key);
    },
    onError: (err) => {
      setStudioAction(null);
      setStudioError(err instanceof ApiError ? err.message : "创建失败");
    },
  });

  function capabilityByFormat(formatKey: "mind_map" | "slides"): StudioCapability | null {
    return (capabilitiesQ.data ?? []).find((c) => c.format_key === formatKey) ?? null;
  }

  function startStudioExport(formatKey: "mind_map" | "slides") {
    if (!draft || createStudioTask.isPending) return;
    setStudioError(null);
    const cap = capabilityByFormat(formatKey);
    if (!cap) {
      setStudioError(
        formatKey === "mind_map"
          ? "请先在 Studio 启用思维导图能力"
          : "请先在 Studio 启用 PPT 能力",
      );
      return;
    }
    const { points } = pointsForExport(draft);
    if (points.length === 0) {
      setStudioError("暂无要点可生成");
      return;
    }
    const { video_ids, note_ids } = resolveSourceIds(draft, sources, notes);
    if (video_ids.length === 0 && note_ids.length === 0) {
      setStudioError("请先选择来源");
      return;
    }
    const fields =
      formatKey === "mind_map"
        ? buildMindMapFields(draft, points)
        : buildSlidesFields(draft, points);
    setStudioAction(formatKey);
    createStudioTask.mutate({
      capability_id: cap.id,
      language: draftLanguage(draft),
      video_ids,
      note_ids,
      fields,
    });
  }


  const conclusionsKey = (draft?.conclusions ?? []).join("\u0001") + "\u0002" + (draft?.conclusion ?? "");
  useEffect(() => {
    setConclusionsDraft(normalizeConclusions(draft));
  }, [draft?.id, conclusionsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!modalOpen) return;
    const strategies = strategiesQ.data ?? [];
    const defaultVideos = sources.filter((s) => s.selected_for_chat).map((s) => s.video_id);
    const defaultNotes = notes.filter((n) => n.selected_for_chat).map((n) => n.id);
    const nextVideos = defaultVideos.length ? defaultVideos : sources.map((s) => s.video_id);
    const nextNotes = defaultNotes;
    const selectedCount = nextVideos.length + nextNotes.length;

    let pick =
      strategies.find((s) => s.apply_default) ??
      strategies[0] ??
      null;
    if (selectedCount >= 2) {
      const compare = strategies.find((s) => s.kind === "compare" || s.name === "compare_read");
      if (compare) pick = compare;
    }
    setStrategyId(pick?.id ?? null);
    setModel(pick?.suggested_model ?? "inherit");
    setLanguage("中文");
    setFocus("");
    setExtra("");
    setShowAdvanced(false);
    setFormError(null);
    setVideoIds(nextVideos);
    setNoteIds(nextNotes);
  }, [modalOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectedStrategy = useMemo(
    () => (strategiesQ.data ?? []).find((s) => s.id === strategyId) ?? null,
    [strategiesQ.data, strategyId],
  );

  const generate = useMutation({
    mutationFn: () =>
      api<KnowledgeDraft>(`/notebooks/${notebookId}/knowledge-draft`, {
        method: "POST",
        access,
        body: {
          strategy_id: strategyId,
          language,
          video_ids: videoIds,
          note_ids: noteIds,
          model,
          focus: focus.trim() || null,
          extra_constraints: extra.trim() || null,
        },
      }),
    onSuccess: (data) => {
      setModalOpen(false);
      setFormError(null);
      qc.setQueryData(["knowledge-draft", notebookId], data);
      void qc.invalidateQueries({ queryKey: ["knowledge-draft", notebookId] });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "生成失败");
    },
  });

  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<KnowledgeDraft>(`/notebooks/${notebookId}/knowledge-draft`, {
        method: "PATCH",
        access,
        body,
      }),
    onSuccess: (data) => {
      qc.setQueryData(["knowledge-draft", notebookId], data);
    },
  });

  function openGenerate() {
    setModalOpen(true);
  }

  function saveConclusions(next?: string[]) {
    if (!draft) return;
    const list = (next ?? conclusionsDraft).map((s) => s.trim()).filter(Boolean);
    const prev = normalizeConclusions(draft);
    if (JSON.stringify(list) === JSON.stringify(prev)) return;
    patch.mutate({ conclusions: list });
  }

  function togglePoint(point: DraftPoint) {
    if (!draft) return;
    const ids = new Set(
      draft.content.points.filter((p) => p.checked).map((p) => p.id),
    );
    if (point.checked) ids.delete(point.id);
    else ids.add(point.id);
    patch.mutate({ checked_point_ids: [...ids] });
  }

  function toggleTakeaway(item: DraftTakeaway) {
    if (!draft) return;
    const ids = new Set(
      draft.content.takeaways.filter((t) => t.checked).map((t) => t.id),
    );
    if (item.checked) ids.delete(item.id);
    else ids.add(item.id);
    patch.mutate({ checked_takeaway_ids: [...ids] });
  }

  function savePointEdit() {
    if (!editingPointId) return;
    const text = editingPointText.trim();
    if (!text) {
      setEditingPointId(null);
      return;
    }
    patch.mutate({ point_text_updates: { [editingPointId]: text } });
    setEditingPointId(null);
  }

  function beginCommentEdit(point: DraftPoint) {
    setCommentEditingId(point.id);
    setCommentDraft(pointComment(point) || "");
  }

  function savePointComment(pointId: string, raw: string | null) {
    const next = raw == null ? null : raw.trim() || null;
    const prev = (draft?.content.points.find((p) => p.id === pointId)?.comment || "").trim() || null;
    setCommentEditingId(null);
    setCommentDraft("");
    if (next === prev) return;
    patch.mutate({ point_comment_updates: { [pointId]: next } });
  }

  const askPoint = useMutation({
    mutationFn: (payload: { point_id: string; message: string; history: AskTurn[] }) =>
      api<{ point_id: string; answer: string }>(
        `/notebooks/${notebookId}/knowledge-draft/point-ask`,
        {
          method: "POST",
          access,
          body: payload,
        },
      ),
    onSuccess: (data, vars) => {
      setAskError(null);
      setAskTurnsByPoint((prev) => {
        const cur = prev[vars.point_id] ?? [];
        return {
          ...prev,
          [vars.point_id]: [...cur, { role: "assistant", content: data.answer }],
        };
      });
    },
    onError: (err) => {
      setAskError(err instanceof ApiError ? err.message : "提问失败");
    },
  });

  function placeAskPopover(anchor: HTMLElement) {
    const rect = anchor.getBoundingClientRect();
    const gap = 8;
    const margin = 8;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const width = Math.min(360, Math.max(260, vw - margin * 2));
    const popH = askPopoverRef.current?.offsetHeight || 320;

    let top = rect.bottom + gap;
    if (top + popH > vh - margin && rect.top - gap - popH >= margin) {
      top = rect.top - gap - popH;
    }
    top = Math.max(margin, Math.min(top, vh - margin - Math.min(popH, vh - margin * 2)));

    // 优先贴按钮右侧对齐，不够则左移
    let left = rect.right - width;
    if (left < margin) left = rect.left;
    if (left + width > vw - margin) left = vw - margin - width;
    left = Math.max(margin, left);

    setAskPos({ top, left, width });
  }

  function closeAsk() {
    setAskPointId(null);
    setAskPos(null);
    askAnchorRef.current = null;
    setAskError(null);
  }

  function openAsk(pointId: string, anchor: HTMLElement) {
    askAnchorRef.current = anchor;
    setAskPointId(pointId);
    setAskInput("");
    setAskError(null);
    // 先粗定位，布局后再精调高度
    placeAskPopover(anchor);
    requestAnimationFrame(() => {
      if (askAnchorRef.current) placeAskPopover(askAnchorRef.current);
    });
  }

  useLayoutEffect(() => {
    if (!askPointId || !askAnchorRef.current) return;
    placeAskPopover(askAnchorRef.current);

    const onReposition = () => {
      if (!askAnchorRef.current) return;
      const r = askAnchorRef.current.getBoundingClientRect();
      // 锚点滚出可视区则关闭
      if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) {
        closeAsk();
        return;
      }
      placeAskPopover(askAnchorRef.current);
    };

    window.addEventListener("resize", onReposition);
    // 捕获阶段：右栏 scroll 也会冒泡到这里
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [askPointId, askTurnsByPoint, askPoint.isPending, askError]);

  function sendAsk(pointId: string, message: string) {
    const msg = message.trim();
    if (!msg || askPoint.isPending) return;
    const history = askTurnsByPoint[pointId] ?? [];
    setAskTurnsByPoint((prev) => ({
      ...prev,
      [pointId]: [...(prev[pointId] ?? []), { role: "user", content: msg }],
    }));
    setAskInput("");
    setAskError(null);
    askPoint.mutate({ point_id: pointId, message: msg, history });
  }

  function writeAnswerToComment(pointId: string, answer: string) {
    const existing = (draft?.content.points.find((p) => p.id === pointId)?.comment || "").trim();
    if (existing && !window.confirm("该要点已有评论，要用这次回答覆盖吗？")) return;
    patch.mutate({ point_comment_updates: { [pointId]: answer } });
  }


  const checkedCount = draft
    ? draft.content.points.filter((p) => p.checked).length +
      draft.content.takeaways.filter((t) => t.checked).length
    : 0;

  const filteredPoints = useMemo(() => {
    if (!draft) return [];
    if (!conceptFilter) return draft.content.points;
    const needle = conceptFilter.toLowerCase();
    return draft.content.points.filter(
      (p) =>
        p.text.toLowerCase().includes(needle) ||
        (p.evidence || "").toLowerCase().includes(needle) ||
        (p.example || "").toLowerCase().includes(needle),
    );
  }, [draft, conceptFilter]);

  const canSubmit =
    strategyId != null &&
    (videoIds.length > 0 || noteIds.length > 0) &&
    !generate.isPending;

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      {embedded ? (
        <div className="flex shrink-0 items-center gap-2 border-b border-border/30 px-3.5 py-1.5">
          <p className="min-w-0 truncate text-[10px] text-muted-foreground">
            {draft
              ? `已勾 ${checkedCount}${draft.strategy_title ? ` · ${draft.strategy_title}` : ""}`
              : "从字幕提炼可勾选的要点与行动"}
          </p>
        </div>
      ) : (
        <header className="panel-header">
          <div className="flex min-w-0 items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <BookOpen className="h-3.5 w-3.5" />
            </span>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold tracking-tight">知识</h2>
              {draft ? (
                <p className="truncate text-[10px] text-muted-foreground">
                  已勾 {checkedCount}
                  {draft.strategy_title ? ` · ${draft.strategy_title}` : ""}
                </p>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {onOpenStudio ? (
              <Button
                size="sm"
                variant="ghost"
                className="h-7 rounded-full px-2 text-xs text-muted-foreground"
                onClick={onOpenStudio}
              >
                Studio
              </Button>
            ) : null}
            {onCollapse ? (
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7 rounded-full hover:bg-primary/10 hover:text-primary"
                title="折叠"
                aria-label="折叠知识面板"
                onClick={onCollapse}
              >
                <PanelRightClose className="h-4 w-4" />
              </Button>
            ) : null}
          </div>
        </header>
      )}

      <div className="flex min-h-0 flex-1 flex-col">
        {draftQ.isLoading ? (
          <div className="flex flex-1 items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载中…
          </div>
        ) : !draft ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Sparkles className="h-5 w-5" />
            </span>
            <div className="space-y-1">
              <p className="text-sm font-medium">字幕就绪后生成知识底稿</p>
              <p className="max-w-[16rem] text-xs text-muted-foreground">
                按策略抽出可勾选、可跳播的要点与收获；勾选后可一键生成导图或幻灯片。
              </p>
            </div>
            <Button className="rounded-full" onClick={openGenerate}>
              生成底稿
            </Button>
          </div>
        ) : (
          <>
            <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto p-3 pb-4">
              {/* 1. 主题 */}
              {draft.content.theme ? (
                <div className="rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/[0.09] via-primary/[0.03] to-transparent px-3.5 py-2.5 shadow-sm">
                  <div className="mb-1 text-[10px] font-semibold tracking-wider text-primary/75">
                    主题
                  </div>
                  <p className="text-sm font-medium leading-snug text-foreground">
                    {draft.content.theme}
                  </p>
                </div>
              ) : null}

              {/* 2. 概念 */}
              {draft.content.concepts.length > 0 ? (
                <section className="space-y-2">
                  <SectionLabel>概念</SectionLabel>
                  <div className="flex flex-wrap gap-1.5">
                    {draft.content.concepts.map((c) => {
                      const active = conceptFilter === c.term;
                      return (
                        <button
                          key={c.term}
                          type="button"
                          title={c.definition || c.term}
                          className={
                            "rounded-full border px-2.5 py-0.5 text-[11px] transition " +
                            (active
                              ? "border-primary/40 bg-primary/10 text-primary"
                              : "border-border/70 bg-card/80 text-muted-foreground hover:border-primary/25")
                          }
                          onClick={() => setConceptFilter(active ? null : c.term)}
                        >
                          {c.term}
                        </button>
                      );
                    })}
                  </div>
                </section>
              ) : null}

              {/* 3. 精华要点 */}
              <section className="space-y-2.5">
                <SectionLabel>精华要点</SectionLabel>
                {draft.content.points.some((p) => !(p.example || "").trim()) ? (
                  <p className="rounded-lg border border-amber-200/60 bg-amber-50/70 px-2.5 py-1.5 text-[10px] leading-relaxed text-amber-900/80 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100/80">
                    当前底稿缺少生活/典故例子。下方先用原句占位；点「重新生成」可按方案 B 产出「例：…」。
                  </p>
                ) : null}
                {filteredPoints.length === 0 ? (
                  <p className="text-xs text-muted-foreground">暂无要点</p>
                ) : (
                  filteredPoints.map((point, idx) => {
                    const secs = parseClockToSeconds(point.time);
                    const seekId =
                      point.video_id ??
                      (draft.source_video_ids.length === 1
                        ? draft.source_video_ids[0]
                        : null);
                    const evidence = pointEvidence(point);
                    const example = pointExample(point);
                    const comment = pointComment(point);
                    const editingComment = commentEditingId === point.id;
                    return (
                      <div
                        key={point.id}
                        className={
                          "group rounded-2xl border px-2.5 py-2.5 shadow-sm transition " +
                          (point.checked
                            ? "border-primary/35 bg-primary/[0.05]"
                            : "border-border/55 bg-card")
                        }
                      >
                        <div className="flex items-start gap-2">
                          <div className="flex shrink-0 flex-col items-center gap-1.5 pt-0.5">
                            <span
                              className={
                                "flex h-5 w-5 items-center justify-center rounded-md text-[10px] font-bold " +
                                (point.checked
                                  ? "bg-primary text-primary-foreground"
                                  : "bg-primary/15 text-primary")
                              }
                            >
                              {idx + 1}
                            </span>
                            <button
                              type="button"
                              className={
                                "flex h-4 w-4 items-center justify-center rounded border " +
                                (point.checked
                                  ? "border-primary bg-primary text-primary-foreground"
                                  : "border-muted-foreground/40")
                              }
                              aria-label="勾选要点"
                              onClick={() => togglePoint(point)}
                            >
                              {point.checked ? <Check className="h-3 w-3" /> : null}
                            </button>
                          </div>
                          <div className="min-w-0 flex-1 space-y-1.5">
                            {editingPointId === point.id ? (
                              <div className="space-y-1">
                                <textarea
                                  className="min-h-[3rem] w-full rounded-lg border border-input bg-background px-2 py-1 text-xs"
                                  value={editingPointText}
                                  onChange={(e) => setEditingPointText(e.target.value)}
                                  autoFocus
                                />
                                <div className="flex gap-1">
                                  <Button size="sm" className="h-7 text-xs" onClick={savePointEdit}>
                                    保存
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 text-xs"
                                    onClick={() => setEditingPointId(null)}
                                  >
                                    取消
                                  </Button>
                                </div>
                              </div>
                            ) : (
                              <p
                                className="cursor-text text-[13px] font-semibold leading-snug text-foreground"
                                onDoubleClick={() => {
                                  setEditingPointId(point.id);
                                  setEditingPointText(point.text);
                                }}
                              >
                                {point.text}
                              </p>
                            )}

                            {evidence ? (
                              <div className="flex items-start gap-1.5">
                                <div className="min-w-0 flex-1 rounded-xl border border-border/55 bg-muted/55 px-2.5 py-1.5">
                                  <p className="text-[11px] leading-relaxed text-foreground/80">
                                    <span className="font-semibold text-muted-foreground">原句：</span>
                                    {evidence}
                                  </p>
                                </div>
                                <button
                                  type="button"
                                  className={
                                    "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border transition " +
                                    (askPointId === point.id
                                      ? "border-primary/40 bg-primary/15 text-primary"
                                      : "border-border/70 bg-card text-primary hover:border-primary/35 hover:bg-primary/10")
                                  }
                                  title="就这段问问"
                                  aria-label="就这段问问"
                                  onClick={(e) => {
                                    if (askPointId === point.id) {
                                      closeAsk();
                                      return;
                                    }
                                    openAsk(point.id, e.currentTarget);
                                  }}
                                >
                                  <Wand2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            ) : (
                              <div className="flex items-center justify-end">
                                <button
                                  type="button"
                                  className="flex h-7 w-7 items-center justify-center rounded-full border border-border/50 text-muted-foreground/40"
                                  title="无原句，暂不可问"
                                  disabled
                                >
                                  <Wand2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            )}

                            {example ? (
                              <div className="rounded-xl border border-amber-200/70 bg-amber-50/90 px-2.5 py-1.5 dark:border-amber-900/50 dark:bg-amber-950/40">
                                <p className="text-[11px] leading-relaxed text-foreground/85">
                                  <span className="font-semibold text-amber-800/90 dark:text-amber-200/90">
                                    例：
                                  </span>
                                  {example}
                                </p>
                              </div>
                            ) : (
                              <div className="rounded-xl border border-dashed border-border/60 bg-muted/30 px-2.5 py-1.5">
                                <p className="text-[10px] text-muted-foreground">
                                  暂无例子 · 重新生成后会出现「例：…」
                                </p>
                              </div>
                            )}

                            <div className="flex items-center justify-end">
                              {secs != null && seekId != null && onSeekVideo ? (
                                <button
                                  type="button"
                                  className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground hover:bg-primary/10 hover:text-primary"
                                  title="跳到原片"
                                  onClick={() => onSeekVideo(seekId, secs)}
                                >
                                  {point.time}
                                </button>
                              ) : point.time ? (
                                <span className="font-mono text-[10px] text-muted-foreground/70">
                                  {point.time}
                                </span>
                              ) : null}
                            </div>

                            {editingComment ? (
                              <div className="space-y-1 rounded-xl border border-primary/20 bg-primary/[0.03] p-2">
                                <textarea
                                  className="min-h-[2.5rem] w-full rounded-lg border border-input bg-background px-2 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/25"
                                  placeholder="写下你的评论…"
                                  value={commentDraft}
                                  rows={2}
                                  autoFocus
                                  onChange={(e) => setCommentDraft(e.target.value)}
                                  onBlur={() => savePointComment(point.id, commentDraft)}
                                />
                                <div className="flex gap-1">
                                  <Button
                                    size="sm"
                                    className="h-7 text-xs"
                                    onClick={() => savePointComment(point.id, commentDraft)}
                                  >
                                    保存
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 text-xs"
                                    onClick={() => {
                                      setCommentEditingId(null);
                                      setCommentDraft("");
                                    }}
                                  >
                                    取消
                                  </Button>
                                  {comment ? (
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      className="ml-auto h-7 text-xs text-destructive hover:text-destructive"
                                      onClick={() => savePointComment(point.id, null)}
                                    >
                                      删除
                                    </Button>
                                  ) : null}
                                </div>
                              </div>
                            ) : comment ? (
                              <div className="flex items-start gap-1.5 rounded-xl border border-border/50 bg-card px-2.5 py-1.5">
                                <p
                                  className="min-w-0 flex-1 cursor-text text-[11px] leading-relaxed text-foreground/85"
                                  onDoubleClick={() => beginCommentEdit(point)}
                                  title="双击编辑"
                                >
                                  <span className="font-semibold text-primary/80">评论：</span>
                                  {comment}
                                </p>
                                <button
                                  type="button"
                                  className="shrink-0 rounded-md px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted hover:text-foreground"
                                  title="编辑评论"
                                  onClick={() => beginCommentEdit(point)}
                                >
                                  编辑
                                </button>
                                <button
                                  type="button"
                                  className="shrink-0 rounded-full p-1 text-muted-foreground/70 hover:bg-destructive/10 hover:text-destructive"
                                  title="删除评论"
                                  onClick={() => savePointComment(point.id, null)}
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            ) : (
                              <button
                                type="button"
                                className="flex h-8 w-full items-center justify-start gap-1 rounded-xl border border-dashed border-border/70 px-2.5 text-[11px] text-muted-foreground transition hover:border-primary/35 hover:bg-primary/[0.04] hover:text-primary"
                                onClick={() => beginCommentEdit(point)}
                              >
                                <Plus className="h-3.5 w-3.5" />
                                写评论
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </section>

              {/* 4. 可执行收获 */}
              {draft.content.takeaways.length > 0 ? (
                <section className="space-y-2">
                  <SectionLabel>可执行收获</SectionLabel>
                  {draft.content.takeaways.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={
                        "flex w-full items-start gap-2 rounded-2xl border px-2.5 py-2 text-left text-xs shadow-sm " +
                        (item.checked
                          ? "border-primary/30 bg-primary/[0.05]"
                          : "border-border/55 bg-card")
                      }
                      onClick={() => toggleTakeaway(item)}
                    >
                      <span
                        className={
                          "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border " +
                          (item.checked
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-muted-foreground/40")
                        }
                      >
                        {item.checked ? <Check className="h-3 w-3" /> : null}
                      </span>
                      <span className="leading-relaxed">{item.text}</span>
                    </button>
                  ))}
                </section>
              ) : null}

              {/* 遗留问题 */}
              {draft.content.open_questions.length > 0 ? (
                <section className="space-y-1.5">
                  <SectionLabel>遗留问题</SectionLabel>
                  <ul className="list-inside list-disc space-y-1 rounded-2xl border border-border/40 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                    {draft.content.open_questions.map((q) => (
                      <li key={q}>{q}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {/* 5. 我的结论 —— 始终显示 */}
              <section className="mt-1 space-y-2">
                <SectionLabel>我的结论</SectionLabel>
                <div className="space-y-1.5 rounded-2xl border border-border/55 bg-card p-2.5 shadow-sm">
                  {conclusionsDraft.length === 0 ? (
                    <p className="px-1 py-0.5 text-[11px] text-muted-foreground">
                      还没有结论。写下你从材料带走的判断，失焦自动保存。
                    </p>
                  ) : null}
                  {conclusionsDraft.map((line, cidx) => (
                    <div key={`c-${cidx}`} className="flex items-start gap-1.5">
                      <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/55" />
                      <textarea
                        className="min-h-[2.4rem] flex-1 resize-y rounded-xl border border-border/50 bg-background px-2.5 py-1.5 text-xs leading-relaxed outline-none focus-visible:border-primary/35 focus-visible:ring-2 focus-visible:ring-ring/25"
                        placeholder={`结论 ${cidx + 1}`}
                        value={line}
                        rows={2}
                        onChange={(e) => {
                          const next = [...conclusionsDraft];
                          next[cidx] = e.target.value;
                          setConclusionsDraft(next);
                        }}
                        onBlur={() => saveConclusions()}
                      />
                      <button
                        type="button"
                        className="mt-1 rounded-full p-1 text-muted-foreground/70 hover:bg-destructive/10 hover:text-destructive"
                        title="删除"
                        aria-label="删除结论"
                        onClick={() => {
                          const next = conclusionsDraft.filter((_, i) => i !== cidx);
                          setConclusionsDraft(next);
                          saveConclusions(next);
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="flex h-9 w-full items-center justify-center gap-1 rounded-xl border border-dashed border-primary/35 bg-primary/[0.03] text-xs text-primary transition hover:bg-primary/10"
                    onClick={() => setConclusionsDraft((prev) => [...prev, ""])}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    失焦自动保存 · + 添加
                  </button>
                </div>
              </section>
            </div>

            <div className="shrink-0 border-t border-border/60 bg-card/95 px-3 py-2.5 backdrop-blur">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="min-w-0 truncate text-[11px] text-muted-foreground">
                  已勾选{" "}
                  <span className="font-medium text-foreground">
                    {draft.content.points.filter((p) => p.checked).length}
                  </span>{" "}
                  条要点
                </p>
                <button
                  type="button"
                  className="inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[11px] text-muted-foreground transition hover:bg-primary/10 hover:text-primary"
                  title="重做知识底稿"
                  onClick={openGenerate}
                >
                  <RefreshCw className="h-3 w-3" />
                  重做底稿
                </button>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-10 flex-1 gap-1.5 rounded-xl border-primary/25 bg-primary/[0.04] text-xs font-medium text-foreground hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
                  disabled={createStudioTask.isPending || draft.content.points.length === 0}
                  title="基于已勾选要点生成思维导图"
                  onClick={() => startStudioExport("mind_map")}
                >
                  {studioAction === "mind_map" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      创建中…
                    </>
                  ) : (
                    <>
                      <Network className="h-4 w-4 text-primary" />
                      生成导图
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-10 flex-1 gap-1.5 rounded-xl border-primary/25 bg-primary/[0.04] text-xs font-medium text-foreground hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
                  disabled={createStudioTask.isPending || draft.content.points.length === 0}
                  title="基于已勾选要点生成幻灯片"
                  onClick={() => startStudioExport("slides")}
                >
                  {studioAction === "slides" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      创建中…
                    </>
                  ) : (
                    <>
                      <Presentation className="h-4 w-4 text-primary" />
                      生成幻灯片
                    </>
                  )}
                </Button>
              </div>
              {studioError ? (
                <p className="mt-1.5 text-[10px] text-destructive">{studioError}</p>
              ) : (
                <p className="mt-1.5 text-[10px] text-muted-foreground">
                  基于已勾选要点生成
                  {draft.content.points.some((p) => p.checked)
                    ? `（已勾 ${draft.content.points.filter((p) => p.checked).length} 条）`
                    : "；未勾选则用全部要点"}
                </p>
              )}
            </div>
          </>
        )}
      </div>


      {askPointId && draft ? (() => {
        const askPointObj = draft.content.points.find((x) => x.id === askPointId) ?? null;
        if (!askPointObj) return null;
        const askEvidence = pointEvidence(askPointObj) || "";
        const turns = askTurnsByPoint[askPointId] ?? [];
        const lastAssistant = [...turns].reverse().find((m) => m.role === "assistant");
        if (!askPos) return null;
        return (
          <div
            ref={askPopoverRef}
            className="fixed z-50 flex max-h-[min(55vh,420px)] flex-col overflow-hidden rounded-2xl border border-primary/25 bg-card shadow-xl"
            style={{ top: askPos.top, left: askPos.left, width: askPos.width }}
          >
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
                <div className="flex items-center gap-1.5 text-sm font-semibold">
                  <Wand2 className="h-3.5 w-3.5 text-primary" />
                  就这段问问
                </div>
                <button
                  type="button"
                  className="rounded-full p-1 text-muted-foreground hover:bg-muted"
                  onClick={() => closeAsk()}
                  aria-label="关闭"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-2 overflow-y-auto px-3 py-2">
                <div className="rounded-xl border border-border/50 bg-muted/50 px-2.5 py-1.5">
                  <p className="text-[10px] font-medium text-muted-foreground">原句</p>
                  <p className="text-[11px] leading-relaxed text-foreground/85">{askEvidence}</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {ASK_CHIPS.map((chip) => (
                    <button
                      key={chip.id}
                      type="button"
                      disabled={askPoint.isPending}
                      className="rounded-full border border-primary/25 bg-primary/[0.06] px-2.5 py-1 text-[11px] text-primary hover:bg-primary/10 disabled:opacity-50"
                      onClick={() => sendAsk(askPointId, chip.message)}
                    >
                      {chip.label}
                    </button>
                  ))}
                </div>
                {turns.length > 0 ? (
                  <div className="space-y-1.5">
                    {turns.map((m, i) => (
                      <div
                        key={`${m.role}-${i}`}
                        className={
                          "rounded-xl px-2.5 py-1.5 text-[11px] leading-relaxed " +
                          (m.role === "user"
                            ? "ml-4 bg-primary/10 text-foreground"
                            : "mr-2 border border-border/50 bg-muted/40 text-foreground/90")
                        }
                      >
                        <span className="mb-0.5 block text-[9px] font-medium text-muted-foreground">
                          {m.role === "user" ? "我" : "AI"}
                        </span>
                        {m.content}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[10px] text-muted-foreground">点快捷问法，或自己输入问题。</p>
                )}
                {askPoint.isPending ? (
                  <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    思考中…
                  </div>
                ) : null}
                {askError ? (
                  <p className="rounded-lg bg-destructive/10 px-2 py-1 text-[11px] text-destructive">
                    {askError}
                  </p>
                ) : null}
              </div>
              <div className="space-y-1.5 border-t border-border/60 px-3 py-2">
                {lastAssistant ? (
                  <button
                    type="button"
                    className="w-full rounded-lg border border-dashed border-primary/30 py-1 text-[11px] text-primary hover:bg-primary/5"
                    onClick={() => writeAnswerToComment(askPointId, lastAssistant.content)}
                  >
                    写入评论
                  </button>
                ) : null}
                <div className="flex gap-1.5">
                  <Input
                    value={askInput}
                    onChange={(e) => setAskInput(e.target.value)}
                    placeholder="继续追问…"
                    className="h-9 text-xs"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        sendAsk(askPointId, askInput);
                      }
                    }}
                  />
                  <Button
                    size="sm"
                    className="h-9 shrink-0"
                    disabled={askPoint.isPending || !askInput.trim()}
                    onClick={() => sendAsk(askPointId, askInput)}
                  >
                    发送
                  </Button>
                </div>
              </div>
            </div>
          </div>
        );
      })() : null}

      {modalOpen ? (
        <div className="absolute inset-0 z-30 flex items-end justify-center bg-black/30 p-3 sm:items-center">
          <div className="flex max-h-[92%] w-full max-w-md flex-col overflow-hidden rounded-2xl border border-border/70 bg-card shadow-xl">
            <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
              <h3 className="text-sm font-semibold">生成底稿</h3>
              <button
                type="button"
                className="rounded-full p-1 text-muted-foreground hover:bg-muted"
                onClick={() => !generate.isPending && setModalOpen(false)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
              <label className="block space-y-1">
                <span className="text-[11px] font-medium text-muted-foreground">策略</span>
                <select
                  className="h-10 w-full rounded-xl border border-input bg-background px-3 text-sm"
                  value={strategyId ?? ""}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    setStrategyId(id);
                    const s = (strategiesQ.data ?? []).find((x) => x.id === id);
                    if (s) setModel(s.suggested_model);
                  }}
                >
                  {(strategiesQ.data ?? []).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                      {s.apply_default ? "（默认）" : ""}
                      {s.min_sources > 1 ? ` · ≥${s.min_sources} 来源` : ""}
                    </option>
                  ))}
                </select>
                {selectedStrategy?.description ? (
                  <p className="text-[11px] text-muted-foreground">{selectedStrategy.description}</p>
                ) : null}
              </label>

              <fieldset className="space-y-1.5">
                <legend className="text-[11px] font-medium text-muted-foreground">来源</legend>
                <div className="max-h-36 space-y-1 overflow-y-auto rounded-xl border border-border/60 p-2">
                  {sources.length === 0 && notes.length === 0 ? (
                    <p className="px-1 text-xs text-muted-foreground">本内暂无来源</p>
                  ) : null}
                  {sources.map((s) => (
                    <label key={`v-${s.video_id}`} className="flex items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={videoIds.includes(s.video_id)}
                        onChange={() => setVideoIds((ids) => toggleId(ids, s.video_id))}
                      />
                      <span className="truncate">{sourceTitle(s)}</span>
                    </label>
                  ))}
                  {notes.map((n) => (
                    <label key={`n-${n.id}`} className="flex items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={noteIds.includes(n.id)}
                        onChange={() => setNoteIds((ids) => toggleId(ids, n.id))}
                      />
                      <span className="truncate">笔记 · {n.title}</span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <div className="grid grid-cols-2 gap-2">
                <label className="block space-y-1">
                  <span className="text-[11px] font-medium text-muted-foreground">语言</span>
                  <select
                    className="h-10 w-full rounded-xl border border-input bg-background px-3 text-sm"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value as Language)}
                  >
                    <option value="中文">中文</option>
                    <option value="English">English</option>
                  </select>
                </label>
                <label className="block space-y-1">
                  <span className="text-[11px] font-medium text-muted-foreground">模型</span>
                  <select
                    className="h-10 w-full rounded-xl border border-input bg-background px-3 text-sm"
                    value={model}
                    onChange={(e) => setModel(e.target.value as ModelRef)}
                  >
                    {(Object.keys(MODEL_LABELS) as ModelRef[]).map((k) => (
                      <option key={k} value={k}>
                        {MODEL_LABELS[k]}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="block space-y-1">
                <span className="text-[11px] font-medium text-muted-foreground">聚焦（可选）</span>
                <Input
                  value={focus}
                  onChange={(e) => setFocus(e.target.value)}
                  placeholder="例如：只关心落地步骤"
                />
              </label>

              <button
                type="button"
                className="text-[11px] text-muted-foreground underline-offset-2 hover:underline"
                onClick={() => setShowAdvanced((v) => !v)}
              >
                {showAdvanced ? "收起高级" : "高级：额外约束"}
              </button>
              {showAdvanced ? (
                <textarea
                  className="min-h-[4rem] w-full rounded-xl border border-input bg-background px-3 py-2 text-xs"
                  value={extra}
                  onChange={(e) => setExtra(e.target.value)}
                  placeholder="拼在策略提示词后的额外约束"
                />
              ) : null}

              {formError ? (
                <p className="rounded-lg bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
                  {formError}
                </p>
              ) : null}
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-border/60 px-4 py-3">
              <Button
                variant="ghost"
                disabled={generate.isPending}
                onClick={() => setModalOpen(false)}
              >
                取消
              </Button>
              <Button
                disabled={!canSubmit}
                onClick={() => generate.mutate()}
              >
                {generate.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    生成中…
                  </>
                ) : (
                  "生成底稿"
                )}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
