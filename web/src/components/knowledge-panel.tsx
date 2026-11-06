import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Check,
  Copy,
  Download,
  Loader2,
  Network,
  PanelRightClose,
  Play,
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

interface ConclusionLineRef {
  video_id: number;
  line_no: number;
  start_ms: number;
  end_ms: number;
  text: string;
}

interface ConclusionCheck {
  text: string;
  verdict: "supported" | "partial" | "unsupported";
  gap: string;
  lines: ConclusionLineRef[];
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
  conclusion_checks?: ConclusionCheck[];
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

const VERDICT_LABEL: Record<ConclusionCheck["verdict"], string> = {
  supported: "撑得住",
  partial: "只撑住一部分",
  unsupported: "撑不住",
};

function fmtCueClock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  const hours = Math.floor(minutes / 60);
  const remain = minutes % 60;
  if (hours > 0) {
    return `${hours}:${String(remain).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${remain}:${String(seconds).padStart(2, "0")}`;
}

function buildDraftExport(notebookTitle: string, draft: KnowledgeDraft, conclusions: string[]): string {
  const lines: string[] = [(notebookTitle || "").trim() || "笔记本"];
  const theme = (draft.content.theme || "").trim();
  if (theme) lines.push(`主题：${theme}`);
  lines.push("", "我的结论");
  conclusions
    .map((text) => text.trim())
    .filter(Boolean)
    .forEach((text, index) => lines.push(`${index + 1}. ${text}`));
  const { points } = pointsForExport(draft);
  lines.push("", "要点");
  points.forEach((point, index) => {
    lines.push(`${index + 1}. ${point.text.trim()}`);
    const time = (point.time || "").trim();
    if (time) lines.push(`   时间：${time}`);
    const evidence = pointEvidence(point);
    const example = pointExample(point);
    if (evidence) lines.push(`   原句：${evidence}`);
    if (example) lines.push(`   例：${example}`);
    const comment = (point.comment || "").trim();
    if (comment) lines.push(`   我的评论：${comment}`);
  });
  const concepts = draft.content.concepts.filter((concept) => concept.term.trim());
  if (concepts.length > 0) {
    lines.push("", "概念");
    concepts.forEach((concept) => {
      lines.push(`- ${concept.term.trim()}：${(concept.definition || "").trim()}`);
    });
  }
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

function DraftGeneratingOverlay({ queued }: { queued: boolean }) {
  return (
    <div
      className="absolute inset-0 z-20 flex items-center justify-center bg-background px-6"
      role="status"
      aria-live="polite"
    >
      <div className="flex w-full max-w-[16rem] flex-col items-center gap-4 text-center">
        <div
          className="relative h-28 w-[5.5rem] rounded-2xl border border-primary/30 bg-card shadow-sm"
          style={{ animation: "draft-page-float 2.8s ease-in-out infinite" }}
        >
          <div className="absolute inset-x-3 top-4 space-y-2">
            {[0, 1, 2, 3].map((index) => (
              <span
                key={index}
                className="block h-1.5 origin-left rounded-full bg-primary/70"
                style={{
                  width: index === 3 ? "62%" : "100%",
                  opacity: 1 - index * 0.18,
                  animation: "draft-line-write 1.8s ease-in-out infinite",
                  animationDelay: `${index * 0.18}s`,
                }}
              />
            ))}
          </div>
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium">{queued ? "底稿排队中" : "正在生成底稿"}</p>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            这份底稿先留着，完成后再替换。
          </p>
        </div>
      </div>
    </div>
  );
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
  notebookTitle = "",
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
  notebookTitle?: string;
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
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [conceptFilter, setConceptFilter] = useState<string | null>(null);
  const [conclusionsDraft, setConclusionsDraft] = useState<string[]>([]);
  const [revealedDraftId, setRevealedDraftId] = useState<number | null>(null);
  const [copiedDraft, setCopiedDraft] = useState(false);
  const [reviewErrors, setReviewErrors] = useState<Record<number, string>>({});
  const [reviewingIndex, setReviewingIndex] = useState<number | null>(null);
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

  const [videoIds, setVideoIds] = useState<number[]>([]);
  const [noteIds, setNoteIds] = useState<number[]>([]);
  const [focus, setFocus] = useState("");
  const appliedDraftTask = useRef<number | null>(null);
  const knowledgeBodyRef = useRef<HTMLDivElement>(null);

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
      setFormError(null);
      setModalOpen(false);
      void qc.invalidateQueries({ queryKey: ["studio-tasks", notebookId] });
      if (task.format_key !== "knowledge_draft") {
        onStudioTaskCreated?.(task.id, task.format_key);
      }
    },
    onError: (err, body) => {
      setStudioAction(null);
      const message = err instanceof ApiError ? err.message : "创建失败";
      const cap = (capabilitiesQ.data ?? []).find((item) => item.id === body.capability_id);
      if (cap?.format_key === "knowledge_draft") {
        setFormError(message);
        return;
      }
      setStudioError(message);
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
          ? "思维导图暂不可用，请稍后重试或联系管理员"
          : "PPT 暂不可用，请稍后重试或联系管理员",
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

  const draftTasksQ = useQuery({
    queryKey: ["studio-tasks", notebookId],
    queryFn: () =>
      api<Array<{ id: number; format_key: string; status: string; error_message: string | null }>>(
        `/notebooks/${notebookId}/studio/tasks`,
        { access },
      ),
    enabled: !!access && !!notebookId,
    refetchInterval: (query) => {
      const rows = query.state.data ?? [];
      return rows.some(
        (task) =>
          task.format_key === "knowledge_draft" &&
          (task.status === "queued" || task.status === "running"),
      )
        ? 2000
        : false;
    },
  });

  const latestDraftTask = (draftTasksQ.data ?? []).find((task) => task.format_key === "knowledge_draft") ?? null;
  const draftBusy = latestDraftTask?.status === "queued" || latestDraftTask?.status === "running";
  const draftProgress =
    latestDraftTask?.status === "queued"
      ? "排队中"
      : latestDraftTask?.status === "running"
        ? "生成中"
        : latestDraftTask?.status === "failed"
          ? `失败：${(latestDraftTask.error_message || "").trim() || "生成没有完成"}`
          : null;

  useEffect(() => {
    const node = knowledgeBodyRef.current;
    if (!node) return;
    if (draftBusy) node.setAttribute("inert", "");
    else node.removeAttribute("inert");
  }, [draftBusy]);

  useEffect(() => {
    if (!draftBusy) return;
    setAskPointId(null);
    setEditingPointId(null);
    setCommentEditingId(null);
  }, [draftBusy]);

  useEffect(() => {
    if (!latestDraftTask || latestDraftTask.status !== "succeeded") return;
    if (appliedDraftTask.current === latestDraftTask.id) return;
    appliedDraftTask.current = latestDraftTask.id;
    void qc.invalidateQueries({ queryKey: ["knowledge-draft", notebookId] });
  }, [latestDraftTask, notebookId, qc]);

  useEffect(() => {
    if (!modalOpen) return;
    const defaultVideos = sources.filter((s) => s.selected_for_chat).map((s) => s.video_id);
    const defaultNotes = notes.filter((n) => n.selected_for_chat).map((n) => n.id);
    setFocus("");
    setFormError(null);
    setVideoIds(defaultVideos.length ? defaultVideos : sources.map((s) => s.video_id));
    setNoteIds(defaultNotes);
  }, [modalOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  function startDraftJob() {
    if (createStudioTask.isPending || draftBusy) return;
    if (videoIds.length === 0 && noteIds.length === 0) {
      setFormError("请先选择来源");
      return;
    }
    const cap = (capabilitiesQ.data ?? []).find((item) => item.format_key === "knowledge_draft");
    if (!cap) {
      setFormError("底稿生成暂不可用，请稍后重试或联系管理员");
      return;
    }
    setFormError(null);
    createStudioTask.mutate({
      capability_id: cap.id,
      video_ids: videoIds,
      note_ids: noteIds,
      fields: focus.trim() ? { focus: focus.trim() } : {},
    });
  }

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


  const checkedCount = draft ? draft.content.points.filter((p) => p.checked).length : 0;
  const savedConclusions = draft
    ? normalizeConclusions(draft).map((line) => line.trim()).filter(Boolean)
    : [];
  const recall = Boolean(draft && savedConclusions.length > 0 && revealedDraftId !== draft.id);

  async function copyDraft() {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(buildDraftExport(notebookTitle, draft, conclusionsDraft));
      setCopiedDraft(true);
      window.setTimeout(() => setCopiedDraft(false), 1600);
    } catch {
      setFormError("复制失败");
    }
  }

  async function downloadDraft() {
    if (!draft || downloading) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      const list = conclusionsDraft.map((line) => line.trim()).filter(Boolean);
      const prev = normalizeConclusions(draft);
      if (JSON.stringify(list) !== JSON.stringify(prev)) {
        await patch.mutateAsync({ conclusions: list });
      }
      const response = await api<Response>(
        `/notebooks/${notebookId}/knowledge-draft/export.docx`,
        { access, raw: true },
      );
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const safeTitle = (notebookTitle || "笔记本").replace(/[\\/:*?"<>|]/g, " ").trim() || "笔记本";
      anchor.href = url;
      anchor.download = `${safeTitle}-底稿.docx`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err instanceof ApiError ? err.message : "下载失败");
    } finally {
      setDownloading(false);
    }
  }

  async function reviewConclusion(index: number) {
    const text = (conclusionsDraft[index] || "").trim();
    if (!text || reviewingIndex != null) return;
    setReviewingIndex(index);
    setReviewErrors((prev) => {
      const next = { ...prev };
      delete next[index];
      return next;
    });
    try {
      const list = conclusionsDraft.map((item) => item.trim()).filter(Boolean);
      const prev = normalizeConclusions(draft);
      if (JSON.stringify(list) !== JSON.stringify(prev)) {
        await patch.mutateAsync({ conclusions: list });
      }
      await api<ConclusionCheck>(`/notebooks/${notebookId}/knowledge-draft/review`, {
        method: "POST",
        access,
        body: { conclusion: text },
      });
      await qc.invalidateQueries({ queryKey: ["knowledge-draft", notebookId] });
    } catch (error) {
      setReviewErrors((prev) => ({
        ...prev,
        [index]: error instanceof ApiError ? error.message : "核对失败",
      }));
    } finally {
      setReviewingIndex(null);
    }
  }

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

  const canSubmit = (videoIds.length > 0 || noteIds.length > 0) && !createStudioTask.isPending && !draftBusy;

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      {embedded ? (
        <div className="flex shrink-0 items-center gap-2 border-b border-border/30 px-3.5 py-1.5">
          <p className="min-w-0 truncate text-[10px] text-muted-foreground">
            {draft
              ? `已勾 ${checkedCount}${draft.strategy_title ? ` · ${draft.strategy_title}` : ""}`
              : "从字幕提炼要点，写下你的结论"}
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
                产物
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

      <div className="relative flex min-h-0 flex-1 flex-col" aria-busy={draftBusy}>
        <div ref={knowledgeBodyRef} className="flex min-h-0 flex-1 flex-col">
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
                从勾选的来源抽出可勾选、可跳播的要点。先写下你的结论，再核对。
              </p>
            </div>
            {draftProgress ? (
              <p
                className={`flex items-center gap-1.5 text-xs ${
                  latestDraftTask?.status === "failed" ? "text-destructive" : "text-muted-foreground"
                }`}
              >
                {draftBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                {draftProgress}
              </p>
            ) : null}
            <Button className="rounded-full" disabled={draftBusy} onClick={openGenerate}>
              生成底稿
            </Button>
          </div>
        ) : (
          <>
            <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto p-3 pb-4">
              <section className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="min-w-0 flex-1">
                    <SectionLabel>我的结论</SectionLabel>
                  </div>
                  <button
                    type="button"
                    className="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] text-muted-foreground transition hover:bg-primary/10 hover:text-primary disabled:opacity-40"
                    disabled={downloading}
                    onClick={() => void downloadDraft()}
                  >
                    <Download className="h-3 w-3" />
                    {downloading ? "下载中…" : "下载 Word"}
                  </button>
                  <button
                    type="button"
                    className="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] text-muted-foreground transition hover:bg-primary/10 hover:text-primary"
                    onClick={() => void copyDraft()}
                  >
                    <Copy className="h-3 w-3" />
                    {copiedDraft ? "已复制" : "复制底稿"}
                  </button>
                </div>
                {downloadError ? (
                  <p className="text-[11px] text-destructive">{downloadError}</p>
                ) : null}
                <div className="space-y-1.5 rounded-2xl border border-border/55 bg-card p-2.5 shadow-sm">
                  {conclusionsDraft.length === 0 ? (
                    <p className="px-1 py-0.5 text-[11px] text-muted-foreground">
                      还没有结论。写下你从材料带走的判断，失焦自动保存。
                    </p>
                  ) : null}
                  {conclusionsDraft.map((line, cidx) => {
                    const saved = (draft?.conclusion_checks ?? []).find(
                      (item) => item.text === line.trim(),
                    );
                    return (
                      <div key={`c-${cidx}`} className="space-y-1">
                        <div className="flex items-start gap-1.5">
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
                            onBlur={(e) => {
                              const next = [...conclusionsDraft];
                              next[cidx] = e.currentTarget.value;
                              setConclusionsDraft(next);
                              saveConclusions(next);
                            }}
                          />
                          <button
                            type="button"
                            className="mt-1 shrink-0 rounded-full px-2 py-1 text-[11px] text-primary hover:bg-primary/10 disabled:opacity-40"
                            disabled={!line.trim() || reviewingIndex != null}
                            onClick={() => void reviewConclusion(cidx)}
                          >
                            {reviewingIndex === cidx ? "核对中…" : "核对"}
                          </button>
                          <button
                            type="button"
                            className="mt-1 rounded-full p-1 text-muted-foreground/70 hover:bg-destructive/10 hover:text-destructive"
                            title="删除"
                            aria-label="删除结论"
                            onClick={() => {
                              const next = conclusionsDraft.filter((_, i) => i !== cidx);
                              setConclusionsDraft(next);
                              setReviewErrors({});
                              saveConclusions(next);
                            }}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        {saved ? (
                          <div className="ml-3 rounded-lg bg-muted/50 px-2.5 py-1.5 text-[11px] leading-relaxed">
                            <p className="font-medium text-foreground">{VERDICT_LABEL[saved.verdict]}</p>
                            {saved.gap ? <p className="mt-0.5 text-muted-foreground">{saved.gap}</p> : null}
                            {saved.lines.length > 0 ? (
                              <div className="mt-1 space-y-0.5">
                                {saved.lines.map((cue) => (
                                  <button
                                    key={`${cue.video_id}-${cue.line_no}`}
                                    type="button"
                                    className="block w-full text-left text-muted-foreground hover:text-foreground"
                                    onClick={() => onSeekVideo?.(cue.video_id, cue.start_ms / 1000)}
                                  >
                                    <span className="mr-1 font-mono text-[10px] text-primary">{fmtCueClock(cue.start_ms)}</span>
                                    {cue.text}
                                  </button>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                        {reviewErrors[cidx] ? (
                          <p className="ml-3 text-[11px] text-destructive">{reviewErrors[cidx]}</p>
                        ) : null}
                      </div>
                    );
                  })}
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
              {recall ? (
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 w-full rounded-xl"
                  onClick={() => setRevealedDraftId(draft.id)}
                >
                  对照要点
                </Button>
              ) : (
              <>
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
                            ? "border-primary/35 bg-primary/[0.04]"
                            : "border-border/50 bg-card hover:border-border/80")
                        }
                      >
                        <div className="flex items-start gap-2.5">
                          {/* 左轨：序号 + 勾选 */}
                          <div className="flex w-5 shrink-0 flex-col items-center gap-1.5 pt-0.5">
                            <span
                              className={
                                "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold " +
                                (point.checked
                                  ? "bg-primary text-primary-foreground"
                                  : "bg-primary/12 text-primary")
                              }
                            >
                              {idx + 1}
                            </span>
                            <button
                              type="button"
                              className={
                                "flex h-4 w-4 items-center justify-center rounded border transition " +
                                (point.checked
                                  ? "border-primary bg-primary text-primary-foreground"
                                  : "border-primary/40 bg-background hover:border-primary/70")
                              }
                              aria-label="勾选要点"
                              onClick={() => togglePoint(point)}
                            >
                              {point.checked ? <Check className="h-3 w-3" /> : null}
                            </button>
                          </div>

                          <div className="min-w-0 flex-1 space-y-1.5">
                            {/* 主张：仅此处加粗 */}
                            <div className="min-w-0">
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
                            </div>

                            {/* 原句：标签 + 常规字重，无底色 */}
                            {evidence ? (
                              <div className="flex items-start gap-1.5">
                                <p className="min-w-0 flex-1 text-[11px] font-normal leading-relaxed text-foreground/90">
                                  <span className="mr-1.5 inline-flex items-center rounded-full bg-primary/10 px-1.5 py-px text-[9px] font-semibold text-primary">
                                    原句
                                  </span>
                                  {evidence}
                                </p>
                                <button
                                  type="button"
                                  className={
                                    "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition " +
                                    (askPointId === point.id
                                      ? "bg-primary/12 text-primary"
                                      : "text-muted-foreground/70 hover:bg-muted hover:text-primary")
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
                                  className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/30"
                                  title="无原句，暂不可问"
                                  disabled
                                >
                                  <Wand2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            )}

                            {/* 例：彩色标签 + 正文，无色块 */}
                            {example ? (
                              <p className="text-[11px] font-normal leading-relaxed text-foreground/85">
                                <span className="mr-1.5 inline-flex items-center rounded-full bg-amber-100 px-1.5 py-px text-[9px] font-semibold text-amber-800 dark:bg-amber-900/50 dark:text-amber-200">
                                  例
                                </span>
                                {example}
                              </p>
                            ) : (
                              <p className="text-[10px] text-muted-foreground/80">
                                <span className="mr-1 text-amber-700/70 dark:text-amber-400/70">例</span>
                                暂无例子 · 重新生成后会出现「例：…」
                              </p>
                            )}

                            {/* 已有评论 / 编辑评论 */}
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
                              <div className="flex items-start gap-1.5 rounded-lg border border-border/40 px-2 py-1.5">
                                <p
                                  className="min-w-0 flex-1 cursor-text text-[11px] font-normal leading-relaxed text-foreground/85"
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
                            ) : null}

                            {/* 底栏：时间 + 写评论（勾选已在左轨） */}
                            <div className="flex items-center gap-2 border-t border-border/40 pt-1.5">
                              {secs != null && seekId != null && onSeekVideo ? (
                                <button
                                  type="button"
                                  className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground transition hover:text-primary"
                                  title="跳到原片"
                                  onClick={() => onSeekVideo(seekId, secs)}
                                >
                                  <Play className="h-2.5 w-2.5 fill-current" />
                                  {point.time}
                                </button>
                              ) : point.time ? (
                                <span className="font-mono text-[10px] text-muted-foreground">
                                  {point.time}
                                </span>
                              ) : null}
                              <div className="ml-auto">
                                {!editingComment && !comment ? (
                                  <button
                                    type="button"
                                    className="inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[10px] text-muted-foreground transition hover:bg-muted hover:text-foreground"
                                    onClick={() => beginCommentEdit(point)}
                                  >
                                    <Plus className="h-3 w-3" />
                                    写评论
                                  </button>
                                ) : null}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </section>
              </>
              )}
            </div>

            {recall ? null : (
            <div className="shrink-0 border-t border-border/60 bg-card/95 px-3 py-2.5 backdrop-blur">
              {draftProgress ? (
                <p
                  className={`mb-2 flex items-center gap-1.5 text-[11px] ${
                    latestDraftTask?.status === "failed" ? "text-destructive" : "text-muted-foreground"
                  }`}
                >
                  {draftBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                  <span className="min-w-0 truncate">{draftProgress}</span>
                </p>
              ) : null}
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
                  className="inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[11px] text-muted-foreground transition hover:bg-primary/10 hover:text-primary disabled:opacity-50"
                  title="重做知识底稿"
                  disabled={draftBusy}
                  onClick={openGenerate}
                >
                  <RefreshCw className="h-3 w-3" />
                  重做底稿
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-10 min-w-[30%] flex-1 gap-1.5 rounded-xl border-primary/25 bg-primary/[0.04] text-xs font-medium text-foreground hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
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
            )}
          </>
        )}
        </div>
        {draftBusy ? <DraftGeneratingOverlay queued={latestDraftTask?.status === "queued"} /> : null}
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
                onClick={() => !createStudioTask.isPending && setModalOpen(false)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                用已勾选的来源生成。一条来源按精读，多条来源按对比。生成在后台进行，完成后出现在这里。
              </p>
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

              <label className="block space-y-1">
                <span className="text-[11px] font-medium text-muted-foreground">聚焦（可选）</span>
                <Input
                  value={focus}
                  onChange={(e) => setFocus(e.target.value)}
                  placeholder="例如：只关心落地步骤"
                />
              </label>

              {formError ? (
                <p className="rounded-lg bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
                  {formError}
                </p>
              ) : null}
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-border/60 px-4 py-3">
              <Button
                variant="ghost"
                disabled={createStudioTask.isPending}
                onClick={() => setModalOpen(false)}
              >
                取消
              </Button>
              <Button
                disabled={!canSubmit}
                onClick={() => startDraftJob()}
              >
                {createStudioTask.isPending || draftBusy ? (
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
