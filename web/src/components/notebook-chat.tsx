import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, Check, Copy } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { authedHeaders } from "@/lib/auth";
import { MarkdownMessage } from "@/components/chat-markdown";

export interface ChatCitation {
  n: number;
  source_id: number;
  line_no: number;
  snippet: string;
  title: string | null;
}

interface ChatMessage {
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

export function NotebookChat({
  access,
  notebookId,
  sources,
  onJump,
}: {
  access: string;
  notebookId: number;
  sources: ChatSource[];
  onJump: (videoId: number, lineNo: number) => void;
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
  const bottomRef = useRef<HTMLDivElement>(null);
  const selectedIds = sources.filter((source) => source.selected).map((source) => source.videoId);

  const saved = history.data ?? [];
  const shown = [...saved];
  if (pendingUser) shown.push(pendingUser);
  if (live && (live.id < 0 || !saved.some((message) => message.id === live.id))) {
    shown.push(live);
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [shown.length, live?.content_text]);

  async function send() {
    const message = draft.trim();
    if (!message || sending || selectedIds.length === 0) return;
    setDraft("");
    setFormError(null);
    setSending(true);
    setPendingUser({
      id: -1,
      role: "user",
      content_text: message,
      citations: [],
      source_ids: selectedIds,
      note_id: null,
      created_at: null,
    });
    setLive({
      id: -2,
      role: "assistant",
      content_text: "",
      citations: [],
      source_ids: selectedIds,
      note_id: null,
      created_at: null,
    });
    let savedId: number | null = null;
    try {
      await readChatStream(access, notebookId, message, selectedIds, {
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
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {history.isLoading ? (
          <p className="text-sm text-muted-foreground">加载对话…</p>
        ) : shown.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center text-sm text-muted-foreground">
            <p>
              向勾选的来源提问。
              <br />
              回答里的编号可以点，会打开对应字幕。
            </p>
          </div>
        ) : (
          <div className="mx-auto flex max-w-2xl flex-col gap-4">
            {shown.map((message) => (
              <MessageBubble
                key={`${message.role}-${message.id}-${message.created_at ?? "live"}`}
                access={access}
                message={message}
                onJump={onJump}
                onSaved={() => {
                  qc.invalidateQueries({ queryKey: ["chat", notebookId] });
                  qc.invalidateQueries({ queryKey: ["notebook", notebookId] });
                }}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
      <form
        className="px-6 pb-4 pt-2"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <div className="mx-auto flex max-w-2xl flex-col gap-1.5">
          {formError ? <p className="px-4 text-xs text-destructive">{formError}</p> : null}
          <div className="flex items-center gap-3 rounded-full border bg-background px-4 py-1.5 shadow-sm">
            <input
              value={draft}
              placeholder="Ask a question or create something"
              disabled={sending || selectedIds.length === 0}
              className="h-9 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-60"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send();
                }
              }}
            />
            <span className="shrink-0 text-xs text-muted-foreground">
              {selectedIds.length} {selectedIds.length === 1 ? "source" : "sources"}
            </span>
            <button
              type="submit"
              title="发送"
              disabled={sending || !draft.trim() || selectedIds.length === 0}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground transition enabled:bg-foreground enabled:text-background disabled:opacity-70"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function MessageBubble({
  access,
  message,
  onJump,
  onSaved,
}: {
  access: string;
  message: ChatMessage;
  onJump: (videoId: number, lineNo: number) => void;
  onSaved: () => void;
}) {
  const mine = message.role === "user";
  const finished = !mine && message.id > 0 && !!message.content_text;
  return (
    <div className={mine ? "flex justify-end" : "flex justify-start"}>
      <div className="max-w-[85%]">
        <div
          className={`rounded-2xl px-3 py-2 text-sm leading-6 ${
            mine ? "bg-primary text-primary-foreground" : "bg-muted"
          }`}
        >
          {mine ? (
            <p className="whitespace-pre-wrap">{message.content_text}</p>
          ) : (
            <MarkdownMessage text={message.content_text} citations={message.citations} onJump={onJump} />
          )}
          {message.truncated ? (
            <p className="mt-1 text-[11px] text-muted-foreground">字幕较长，这次只带上了前面一部分。</p>
          ) : null}
          {message.error ? <p className="mt-1 text-[11px] text-destructive">{message.error}</p> : null}
          {!mine && sendingPlaceholder(message) ? (
            <p className="text-[11px] text-muted-foreground">正在回答…</p>
          ) : null}
        </div>
        {finished ? <AnswerActions access={access} message={message} onSaved={onSaved} /> : null}
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
        className="hover:text-foreground disabled:hover:text-muted-foreground"
        disabled={!!noteId || saving}
        onClick={() => void saveNote()}
      >
        {noteId ? "Saved" : saving ? "Saving…" : "Save to note"}
      </button>
      <button type="button" title={copied ? "已复制" : "复制"} onClick={() => void copyAnswer()}>
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
      {error ? <span className="text-destructive">{error}</span> : null}
    </div>
  );
}

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

async function readChatStream(
  access: string,
  notebookId: number,
  message: string,
  sourceIds: number[],
  handlers: {
    onToken: (token: string) => void;
    onWarning: () => void;
    onError: (message: string) => void;
    onDone: (messageId: number | null, citations: ChatCitation[]) => void;
  },
): Promise<void> {
  const response = await fetch(`/api/notebooks/${notebookId}/chat`, {
    method: "POST",
    headers: authedHeaders(access, { "Content-Type": "application/json", Accept: "text/event-stream" }),
    body: JSON.stringify({ message, source_ids: sourceIds }),
  });
  if (!response.ok) {
    let payload: { code?: string; message?: string } | null = null;
    try {
      payload = await response.json();
    } catch {
      /* empty */
    }
    throw new ApiError(
      response.status,
      payload?.code ?? `http_${response.status}`,
      payload?.message ?? "发送失败",
      payload,
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
