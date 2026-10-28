import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, Check, Copy, MessageSquare, Trash2 } from "lucide-react";
import { api, ApiError, recoverAccessAfter401 } from "@/lib/api";
import { authedHeaders } from "@/lib/auth";
import { MarkdownMessage } from "@/components/chat-markdown";

export interface ChatCitation {
  n: number;
  source_id: number;
  line_no: number;
  snippet: string;
  title: string | null;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content_text: string;
  citations: ChatCitation[];
  source_ids: number[];
  note_id: number | null;
  created_at: string | null;
  truncated?: boolean;
  error?: string | null;
}

interface ChatSource {
  videoId: number;
  title: string;
  selected: boolean;
}

async function fetchHistory(access: string, notebookId: number): Promise<ChatMessage[]> {
  const body = await api<{ messages: ChatMessage[] }>(`/notebooks/${notebookId}/chat`, { access });
  return body.messages;
}

/** 一轮 = 一条 user + 紧跟的一条 assistant（若有）。 */
export function groupChatTurns(messages: ChatMessage[]): ChatMessage[][] {
  const turns: ChatMessage[][] = [];
  let i = 0;
  while (i < messages.length) {
    const msg = messages[i];
    if (msg.role === "user") {
      const turn = [msg];
      if (i + 1 < messages.length && messages[i + 1].role === "assistant") {
        turn.push(messages[i + 1]);
        i += 2;
      } else {
        i += 1;
      }
      turns.push(turn);
    } else {
      turns.push([msg]);
      i += 1;
    }
  }
  return turns;
}

function turnSelectable(turn: ChatMessage[]): boolean {
  return turn.length > 0 && turn.every((m) => m.id > 0);
}

export interface ChatRelay {
  pending: ChatMessage | null;
  live: ChatMessage | null;
  error: string | null;
}

export function NotebookChat({
  access,
  notebookId,
  sources,
  onJump,
  relay,
  readOnly = false,
  onCleared,
}: {
  access: string;
  notebookId: number;
  sources: ChatSource[];
  onJump: (videoId: number, lineNo: number) => void;
  relay?: ChatRelay | null;
  readOnly?: boolean;
  /** 清空会话后通知父组件（如清掉 Studio 接力中的气泡） */
  onCleared?: () => void;
}) {
  const qc = useQueryClient();
  const history = useQuery({
    queryKey: ["chat", notebookId],
    queryFn: () => fetchHistory(access, notebookId),
    enabled: !!access && !!notebookId,
  });
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingUser, setPendingUser] = useState<ChatMessage | null>(null);
  const [live, setLive] = useState<ChatMessage | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set());
  const [deletingSelected, setDeletingSelected] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const selectedSourceIds = sources.filter((source) => source.selected).map((source) => source.videoId);

  const saved = history.data ?? [];
  const shown = [...saved];
  if (pendingUser) shown.push(pendingUser);
  if (relay?.pending) shown.push(relay.pending);
  if (live && (live.id < 0 || !saved.some((message) => message.id === live.id))) {
    shown.push(live);
  }
  const relayLive = relay?.live ?? null;
  if (relayLive && (relayLive.id < 0 || !saved.some((message) => message.id === relayLive.id))) {
    shown.push(relayLive);
  }

  const turns = groupChatTurns(shown);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [shown.length, live?.content_text, relay?.live?.content_text, relay?.error]);

  const streamBusy = sending || !!relay?.pending || !!relay?.live;
  const canClear =
    !readOnly &&
    !clearing &&
    !selecting &&
    !streamBusy &&
    (saved.length > 0 || !!pendingUser || !!live || !!relay?.pending || !!relay?.live);
  const canEnterSelect = !readOnly && !clearing && !streamBusy && saved.some((m) => m.id > 0);

  const selectedTurnCount = turns.filter(
    (turn) => turnSelectable(turn) && turn.every((m) => selectedIds.has(m.id)),
  ).length;

  function exitSelectMode() {
    setSelecting(false);
    setSelectedIds(new Set());
  }

  function toggleTurn(turn: ChatMessage[]) {
    if (!turnSelectable(turn)) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      const allOn = turn.every((m) => next.has(m.id));
      for (const m of turn) {
        if (allOn) next.delete(m.id);
        else next.add(m.id);
      }
      return next;
    });
  }

  async function clearChat() {
    if (!canClear) return;
    if (!window.confirm("删除整段对话？此操作不可恢复。已保存的笔记会保留。")) return;
    setClearing(true);
    setFormError(null);
    try {
      await api(`/notebooks/${notebookId}/chat`, { method: "DELETE", access });
      setPendingUser(null);
      setLive(null);
      setDraft("");
      exitSelectMode();
      onCleared?.();
      await qc.invalidateQueries({ queryKey: ["chat", notebookId] });
      qc.setQueryData<ChatMessage[]>(["chat", notebookId], []);
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "删除失败");
    } finally {
      setClearing(false);
    }
  }

  async function deleteSelected() {
    if (selectedTurnCount <= 0 || deletingSelected) return;
    if (!window.confirm(`删除已选的 ${selectedTurnCount} 轮对话？`)) return;
    setDeletingSelected(true);
    setFormError(null);
    const ids = Array.from(selectedIds);
    try {
      const result = await api<{ deleted_ids: number[] }>(
        `/notebooks/${notebookId}/chat/messages/delete`,
        { method: "POST", access, body: { message_ids: ids } },
      );
      const removed = new Set(result.deleted_ids ?? ids);
      qc.setQueryData<ChatMessage[]>(["chat", notebookId], (prev) =>
        (prev ?? []).filter((m) => !removed.has(m.id)),
      );
      exitSelectMode();
      await qc.invalidateQueries({ queryKey: ["chat", notebookId] });
      await qc.invalidateQueries({ queryKey: ["notebook", notebookId] });
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "删除失败");
    } finally {
      setDeletingSelected(false);
    }
  }

  async function send() {
    const message = draft.trim();
    if (readOnly || selecting || !message || sending || selectedSourceIds.length === 0) return;
    setDraft("");
    setFormError(null);
    setSending(true);
    setPendingUser({
      id: -1,
      role: "user",
      content_text: message,
      citations: [],
      source_ids: selectedSourceIds,
      note_id: null,
      created_at: null,
    });
    setLive({
      id: -2,
      role: "assistant",
      content_text: "",
      citations: [],
      source_ids: selectedSourceIds,
      note_id: null,
      created_at: null,
    });
    let savedId: number | null = null;
    try {
      await readChatStream(access, notebookId, message, selectedSourceIds, {
        onToken: (token) => {
          setLive((current) =>
            current ? { ...current, content_text: current.content_text + token } : current,
          );
        },
        onWarning: () => {
          setLive((current) => (current ? { ...current, truncated: true } : current));
        },
        onError: (text) => {
          setLive((current) => (current ? { ...current, error: text } : current));
        },
        onDone: (messageId, citations) => {
          savedId = messageId;
          setLive((current) =>
            current ? { ...current, id: messageId ?? current.id, citations } : current,
          );
        },
      });
      await qc.invalidateQueries({ queryKey: ["chat", notebookId] });
      const fresh = qc.getQueryData<ChatMessage[]>(["chat", notebookId]) ?? [];
      if (fresh.some((item) => item.role === "user" && item.content_text === message)) {
        setPendingUser(null);
      }
      if (savedId != null && fresh.some((item) => item.id === savedId)) {
        setLive(null);
      }
    } catch (error) {
      setPendingUser(null);
      setLive(null);
      setFormError(error instanceof ApiError ? error.message : "发送失败");
      setDraft(message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {!readOnly && saved.length > 0 ? (
        <div className="flex items-center border-b border-border/20 px-6 py-2">
          {selecting ? (
            <>
              <button
                type="button"
                className="rounded-full px-2.5 py-1 text-[11px] text-muted-foreground transition hover:bg-accent hover:text-foreground"
                onClick={exitSelectMode}
              >
                取消
              </button>
              <span className="flex-1 text-center text-[11px] text-muted-foreground">
                已选 {selectedTurnCount} 轮
              </span>
              <button
                type="button"
                disabled={selectedTurnCount === 0 || deletingSelected}
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] text-destructive transition hover:bg-destructive/10 disabled:opacity-40"
                onClick={() => void deleteSelected()}
              >
                <Trash2 className="h-3.5 w-3.5" />
                {deletingSelected ? "删除中…" : "删除"}
              </button>
            </>
          ) : (
            <div className="ml-auto flex items-center gap-1">
              <button
                type="button"
                title="选择删除"
                disabled={!canEnterSelect}
                className="rounded-full px-2.5 py-1 text-[11px] text-muted-foreground transition hover:bg-accent hover:text-foreground disabled:opacity-40"
                onClick={() => {
                  setSelecting(true);
                  setSelectedIds(new Set());
                  setFormError(null);
                }}
              >
                选择删除
              </button>
              <button
                type="button"
                title="清空对话"
                disabled={!canClear}
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive disabled:opacity-40"
                onClick={() => void clearChat()}
              >
                <Trash2 className="h-3.5 w-3.5" />
                {clearing ? "清空中…" : "清空对话"}
              </button>
            </div>
          )}
        </div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {history.isLoading ? (
          <p className="text-sm text-muted-foreground">加载对话…</p>
        ) : shown.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-3xl bg-primary/10 text-primary shadow-soft">
              <MessageSquare className="h-6 w-6" />
            </span>
            <p className="text-sm font-medium text-foreground">开始与来源对话</p>
            <p className="mt-2 max-w-xs text-xs leading-relaxed text-muted-foreground">
              在左侧勾选来源或笔记，在下方提问。回答中的编号可点击，会跳到对应字幕。
            </p>
          </div>
        ) : (
          <div className="mx-auto flex max-w-2xl flex-col gap-5">
            {turns.map((turn, turnIndex) => {
              const selectable = selecting && turnSelectable(turn);
              const checked = selectable && turn.every((m) => selectedIds.has(m.id));
              return (
                <div
                  key={`turn-${turnIndex}-${turn.map((m) => m.id).join("-")}`}
                  className={
                    selecting
                      ? `flex gap-2 ${selectable ? "cursor-pointer rounded-2xl px-1 -mx-1 py-1 transition hover:bg-accent/40" : "opacity-60"} ${checked ? "bg-accent/50" : ""}`
                      : undefined
                  }
                  onClick={
                    selectable
                      ? (event) => {
                          event.preventDefault();
                          toggleTurn(turn);
                        }
                      : undefined
                  }
                >
                  {selecting ? (
                    <div className="flex w-5 shrink-0 items-start pt-3">
                      {selectable ? (
                        <span
                          className={`mt-0.5 flex h-4 w-4 items-center justify-center rounded-full border ${
                            checked
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-muted-foreground/40 bg-background"
                          }`}
                          aria-hidden
                        >
                          {checked ? <Check className="h-2.5 w-2.5" /> : null}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                  <div className="flex min-w-0 flex-1 flex-col gap-5">
                    {turn.map((message) => (
                      <MessageBubble
                        key={`${message.role}-${message.id}-${message.created_at ?? "live"}`}
                        access={access}
                        message={message}
                        hideActions={selecting}
                        onJump={selecting ? () => {} : onJump}
                        onSaved={() => {
                          qc.invalidateQueries({ queryKey: ["chat", notebookId] });
                          qc.invalidateQueries({ queryKey: ["notebook", notebookId] });
                        }}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
      {readOnly ? (
        <div className="border-t border-border/30 px-6 py-4 text-center text-xs text-muted-foreground">
          公开分享为只读，暂不可在此对话。可浏览来源与字幕。
        </div>
      ) : (
      <form
        className="border-t border-border/30 bg-gradient-to-t from-card/80 to-transparent px-6 pb-5 pt-3"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <div className="mx-auto flex max-w-2xl flex-col gap-1.5">
          {formError || relay?.error ? (
            <p className="px-4 text-xs text-destructive">{formError || relay?.error}</p>
          ) : null}
          <div className="chat-composer">
            <input
              value={draft}
              placeholder={
                selecting
                  ? "选择模式下不可提问…"
                  : selectedSourceIds.length === 0
                    ? "请先在左侧勾选来源…"
                    : "向来源提问…"
              }
              disabled={selecting || sending || selectedSourceIds.length === 0}
              className="h-9 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-60"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send();
                }
              }}
            />
            <span className="hidden shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground sm:inline">
              {selectedSourceIds.length} 个来源
            </span>
            <button
              type="submit"
              title="发送"
              disabled={selecting || sending || !draft.trim() || selectedSourceIds.length === 0}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground transition enabled:bg-primary enabled:text-primary-foreground enabled:shadow-soft disabled:opacity-50"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
        </div>
      </form>
      )}
    </div>
  );
}

function MessageBubble({
  access,
  message,
  onJump,
  onSaved,
  hideActions = false,
}: {
  access: string;
  message: ChatMessage;
  onJump: (videoId: number, lineNo: number) => void;
  onSaved: () => void;
  hideActions?: boolean;
}) {
  const mine = message.role === "user";
  const finished = !mine && message.id > 0 && !!message.content_text;
  return (
    <div className={mine ? "flex justify-end" : "flex justify-start"}>
      <div className="max-w-[85%]">
        <div className={mine ? "chat-bubble-user" : "chat-bubble-assistant"}>
          {mine ? (
            <p className="whitespace-pre-wrap">{message.content_text}</p>
          ) : (
            <MarkdownMessage text={message.content_text} citations={message.citations} onJump={onJump} />
          )}
          {message.truncated ? (
            <p className="mt-1 text-[11px] text-muted-foreground">上下文较满，已自动丢掉更早的对话轮次；勾选字幕仍为全文。</p>
          ) : null}
          {message.error ? <p className="mt-1 text-[11px] text-destructive">{message.error}</p> : null}
          {!mine && sendingPlaceholder(message) ? (
            <p className="text-[11px] text-muted-foreground">正在回答…</p>
          ) : null}
        </div>
        {finished && !hideActions ? <AnswerActions access={access} message={message} onSaved={onSaved} /> : null}
      </div>
    </div>
  );
}

function AnswerActions({
  access,
  message,
  onSaved,
}: {
  access: string;
  message: ChatMessage;
  onSaved: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [saving, setSaving] = useState(false);
  const [noteId, setNoteId] = useState<number | null>(message.note_id);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setNoteId(message.note_id);
  }, [message.note_id]);

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(textWithoutCitations(message.content_text));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("复制失败");
    }
  }

  async function saveNote() {
    if (noteId || saving) return;
    setSaving(true);
    setError(null);
    try {
      const note = await api<{ id: number }>(`/messages/${message.id}/save_as_note`, {
        method: "POST",
        access,
      });
      setNoteId(note.id);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-1.5 flex items-center gap-3 px-1 text-xs text-muted-foreground">
      <button
        type="button"
        className="rounded-full px-2 py-0.5 hover:bg-accent hover:text-foreground disabled:hover:bg-transparent disabled:hover:text-muted-foreground"
        disabled={!!noteId || saving}
        onClick={() => void saveNote()}
      >
        {noteId ? "已保存" : saving ? "保存中…" : "保存为笔记"}
      </button>
      <button
        type="button"
        className="rounded-full p-1 hover:bg-accent hover:text-foreground"
        title={copied ? "已复制" : "复制"}
        onClick={() => void copyAnswer()}
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
      {error ? <span className="text-destructive">{error}</span> : null}
    </div>
  );
}

/** Clipboard only — chat bubbles still render [n] via MarkdownMessage. */
function textWithoutCitations(text: string): string {
  return text
    .replace(/\[\d+\]/g, "")
    .replace(/[ \t]+([，。！？、；：,.])/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .trim();
}

function sendingPlaceholder(message: ChatMessage): boolean {
  return message.id < 0 && !message.content_text && !message.error;
}

export async function readChatStream(
  access: string,
  notebookId: number,
  message: string,
  sourceIds: number[],
  handlers: {
    noteIds?: number[];
    onToken: (token: string) => void;
    onWarning: () => void;
    onError: (message: string) => void;
    onDone: (messageId: number | null, citations: ChatCitation[]) => void;
  },
): Promise<void> {
  const payload: { message: string; source_ids: number[]; note_ids?: number[] } = {
    message,
    source_ids: sourceIds,
  };
  if (handlers.noteIds !== undefined) payload.note_ids = handlers.noteIds;

  async function postChat(token: string): Promise<Response> {
    return fetch(`/api/notebooks/${notebookId}/chat`, {
      method: "POST",
      headers: authedHeaders(token, {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      }),
      body: JSON.stringify(payload),
    });
  }

  let response = await postChat(access);
  if (response.status === 401) {
    const fresh = await recoverAccessAfter401();
    if (fresh) {
      response = await postChat(fresh);
    }
  }
  if (!response.ok) {
    let errBody: { code?: string; message?: string } | null = null;
    try {
      errBody = await response.json();
    } catch {
      /* empty */
    }
    throw new ApiError(
      response.status,
      errBody?.code ?? `http_${response.status}`,
      errBody?.message ?? "发送失败",
      errBody,
    );
  }
  if (!response.body) {
    throw new ApiError(500, "empty", "没有返回内容");
  }
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
        message_id?: number | null;
        citations?: ChatCitation[];
      };
      if (event.type === "token" && event.t) handlers.onToken(event.t);
      if (event.type === "warning") handlers.onWarning();
      if (event.type === "error") handlers.onError(event.message || "回答失败");
      if (event.type === "done") handlers.onDone(event.message_id ?? null, event.citations ?? []);
    }
  }
}
