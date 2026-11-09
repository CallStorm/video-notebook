import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import type { Editor } from "@tiptap/react";
import { ArrowUp, Check, Copy, RefreshCw, X } from "lucide-react";
import { ApiError, recoverAccessAfter401 } from "@/lib/api";
import { authedHeaders } from "@/lib/auth";

export type AssistAction = "write" | "translate" | "explain";

export interface AssistSelection {
  text: string;
  from: number | null;
  to: number | null;
}

const ACTION_LABEL: Record<AssistAction, string> = {
  write: "帮写",
  translate: "翻译",
  explain: "解读",
};

export function NoteAssist({
  access,
  notebookId,
  sourceIds,
  noteIds,
  rootRef,
  editorRef,
  onApply,
}: {
  access: string;
  notebookId: number;
  sourceIds: number[];
  noteIds: number[];
  rootRef: RefObject<HTMLElement | null>;
  editorRef: RefObject<Editor | null>;
  onApply: (mode: "replace" | "insert", result: string, selection: AssistSelection) => Promise<void>;
}) {
  const uiRef = useRef<HTMLDivElement>(null);
  const cardOpen = useRef(false);
  const [bar, setBar] = useState<{ rect: DOMRect; selection: AssistSelection } | null>(null);
  const [card, setCard] = useState<{
    action: AssistAction;
    selection: AssistSelection;
    rect: DOMRect;
  } | null>(null);
  const [text, setText] = useState("");
  const [instruction, setInstruction] = useState("");
  const [usedInstruction, setUsedInstruction] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [applying, setApplying] = useState<"replace" | "insert" | null>(null);

  useEffect(() => {
    cardOpen.current = card != null;
  }, [card]);

  useEffect(() => {
    function capture(target: EventTarget | null) {
      if (target instanceof Node && uiRef.current?.contains(target)) return;
      const root = rootRef.current;
      if (!root) return;
      window.setTimeout(() => {
        if (cardOpen.current) return;
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed || !sel.anchorNode || !root.contains(sel.anchorNode)) {
          setBar(null);
          return;
        }
        const editor = editorRef.current;
        let from: number | null = null;
        let to: number | null = null;
        let picked = sel.toString().trim();
        if (editor && !editor.state.selection.empty && root.contains(editor.view.dom)) {
          from = editor.state.selection.from;
          to = editor.state.selection.to;
          picked = editor.state.doc.textBetween(from, to, "\n").trim();
        }
        if (!picked) {
          setBar(null);
          return;
        }
        const rect = sel.getRangeAt(0).getBoundingClientRect();
        setBar({ rect, selection: { text: picked, from, to } });
      }, 0);
    }
    function onMouseUp(event: MouseEvent) {
      capture(event.target);
    }
    function onKeyUp(event: KeyboardEvent) {
      if (!event.shiftKey && event.key !== "Shift") return;
      capture(event.target);
    }
    window.addEventListener("mouseup", onMouseUp);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("mouseup", onMouseUp);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [editorRef, rootRef]);

  async function run(action: AssistAction, selection: AssistSelection, nextInstruction: string, prior: string | null) {
    setStreaming(true);
    setError(null);
    setText("");
    setCopied(false);
    setUsedInstruction(nextInstruction);
    let acc = "";
    try {
      await readAssist(access, notebookId, {
        action,
        selection: selection.text,
        instruction: nextInstruction.trim() || null,
        prior,
        source_ids: sourceIds,
        note_ids: noteIds,
        onToken: (token) => {
          acc += token;
          setText(acc);
        },
        onError: (message) => setError(message),
        onDone: (finalText) => {
          acc = finalText;
          setText(finalText);
        },
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "生成失败");
    } finally {
      setStreaming(false);
    }
  }

  function open(action: AssistAction) {
    if (!bar) return;
    const next = { action, selection: bar.selection, rect: bar.rect };
    setCard(next);
    setBar(null);
    setInstruction("");
    void run(action, next.selection, "", null);
  }

  async function apply(mode: "replace" | "insert") {
    if (!card || !text.trim() || streaming) return;
    setApplying(mode);
    setError(null);
    try {
      await onApply(mode, text.trim(), card.selection);
      setCard(null);
      setBar(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "写回失败");
    } finally {
      setApplying(null);
    }
  }

  async function copyResult() {
    if (!text.trim()) return;
    try {
      await navigator.clipboard.writeText(text.trim());
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("复制失败");
    }
  }

  const plainExplain = card?.action === "explain" && sourceIds.length + noteIds.length === 0;

  return (
    <div ref={uiRef}>
      {bar ? (
        <div
          className="fixed z-40 flex h-9 items-center rounded-[10px] border border-border bg-card p-0.5"
          style={{ top: Math.max(8, bar.rect.top - 44), left: Math.max(8, bar.rect.left) }}
          role="toolbar"
          aria-label="对选中文字"
          onMouseDown={(event) => event.preventDefault()}
        >
          {(Object.keys(ACTION_LABEL) as AssistAction[]).map((action) => (
            <button
              key={action}
              type="button"
              className="h-7 rounded-lg px-3 text-[13px] text-foreground hover:bg-muted"
              onClick={() => open(action)}
            >
              {ACTION_LABEL[action]}
            </button>
          ))}
        </div>
      ) : null}
      {card ? (
        <div
          className="fixed z-40 flex max-h-[min(420px,calc(100vh-24px))] w-[min(420px,calc(100vw-16px))] flex-col rounded-[14px] border border-border bg-card p-3.5"
          style={cardStyle(card.rect)}
          role="dialog"
          aria-label={`${ACTION_LABEL[card.action]}结果`}
        >
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{ACTION_LABEL[card.action]}</span>
            <button
              type="button"
              className="rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="关闭"
              onClick={() => setCard(null)}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          {plainExplain ? (
            <p className="mb-2 text-[11px] text-muted-foreground">未勾选来源，仅根据这段文字解读。</p>
          ) : null}
          <div className="min-h-0 flex-1 overflow-y-auto text-sm leading-6">
            {text || (streaming ? "生成中…" : "")}
          </div>
          {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
          <div className="mt-3 flex items-center justify-between gap-2">
            <div className="flex flex-wrap">
              <CardButton disabled={!text.trim() || streaming || applying != null} onClick={() => void apply("replace")}>
                <Check className="h-3.5 w-3.5" />
                {applying === "replace" ? "替换中…" : "替换"}
              </CardButton>
              <CardButton disabled={!text.trim() || streaming || applying != null} onClick={() => void apply("insert")}>
                <ArrowUp className="h-3.5 w-3.5 rotate-180" />
                {applying === "insert" ? "插入中…" : "插入"}
              </CardButton>
              <CardButton disabled={!text.trim()} onClick={() => void copyResult()}>
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "已复制" : "复制"}
              </CardButton>
            </div>
            <button
              type="button"
              className="rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
              aria-label="重新生成"
              disabled={streaming}
              onClick={() => void run(card.action, card.selection, usedInstruction, null)}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${streaming ? "animate-spin" : ""}`} />
            </button>
          </div>
          <form
            className="mt-3 flex h-10 items-center gap-2 rounded-xl border border-border bg-background px-3"
            onSubmit={(event) => {
              event.preventDefault();
              const next = instruction.trim();
              if (!next || streaming) return;
              setInstruction("");
              void run(card.action, card.selection, next, text.trim() || null);
            }}
          >
            <input
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              placeholder="继续调整，例如再短一点"
              aria-label="继续调整结果"
              className="h-8 min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground"
            />
            <button
              type="submit"
              className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-40"
              aria-label="发送"
              disabled={streaming || !instruction.trim()}
            >
              <ArrowUp className="h-3.5 w-3.5" />
            </button>
          </form>
          <p className="mt-2 text-center text-[11px] text-muted-foreground">内容由 AI 生成，仅供参考</p>
        </div>
      ) : null}
    </div>
  );
}

function CardButton({
  children,
  disabled,
  onClick,
}: {
  children: ReactNode;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="inline-flex h-7 items-center gap-1 rounded-lg px-2 text-[13px] text-primary hover:bg-primary/10 disabled:opacity-40"
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function cardStyle(rect: DOMRect): { top: number; left: number } {
  const width = Math.min(420, window.innerWidth - 16);
  const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
  const below = rect.bottom + 8;
  const top = below > window.innerHeight - 220 ? Math.max(8, rect.top - 280) : below;
  return { top, left };
}

async function readAssist(
  access: string,
  notebookId: number,
  handlers: {
    action: AssistAction;
    selection: string;
    instruction: string | null;
    prior: string | null;
    source_ids: number[];
    note_ids: number[];
    onToken: (token: string) => void;
    onError: (message: string) => void;
    onDone: (text: string) => void;
  },
): Promise<void> {
  const payload = {
    action: handlers.action,
    selection: handlers.selection,
    instruction: handlers.instruction,
    prior: handlers.prior,
    source_ids: handlers.source_ids,
    note_ids: handlers.note_ids,
  };

  async function post(token: string): Promise<Response> {
    return fetch(`/api/notebooks/${notebookId}/notes/assist`, {
      method: "POST",
      headers: authedHeaders(token, {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      }),
      body: JSON.stringify(payload),
    });
  }

  let response = await post(access);
  if (response.status === 401) {
    const fresh = await recoverAccessAfter401();
    if (fresh) response = await post(fresh);
  }
  if (!response.ok) {
    let errBody: { code?: string; message?: string } | null = null;
    try {
      errBody = await response.json();
    } catch {
      /* empty */
    }
    throw new ApiError(response.status, errBody?.code ?? `http_${response.status}`, errBody?.message ?? "生成失败", errBody);
  }
  if (!response.body) throw new ApiError(500, "empty", "没有返回内容");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const line = chunk.split("\n").find((item) => item.startsWith("data:"));
      if (!line) continue;
      const event = JSON.parse(line.slice(line.indexOf(":") + 1).trim()) as {
        type: string;
        t?: string;
        message?: string;
        text?: string;
      };
      if (event.type === "token" && event.t) handlers.onToken(event.t);
      if (event.type === "error") handlers.onError(event.message || "生成失败");
      if (event.type === "done") handlers.onDone(event.text ?? "");
    }
  }
}
