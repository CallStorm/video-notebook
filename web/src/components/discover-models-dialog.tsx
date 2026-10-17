import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface DiscoveredModel {
  name: string;
  provider: string | null;
  description: string | null;
}

interface DiscoverResponse {
  items: DiscoveredModel[];
}

interface ModelRow {
  id: number;
  name: string;
  provider: string;
  type: string;
  credential_id: number;
}

interface BulkRegisterItem {
  name: string;
  type: "language" | "embedding" | "speech_to_text" | "text_to_speech";
}

interface BulkRegisterResponse {
  created: ModelRow[];
  skipped: string[];
}

const MODALITY_LABEL: Record<string, string> = {
  language: "Chat",
  embedding: "Embed",
  speech_to_text: "STT",
  text_to_speech: "TTS",
};

async function fetchDiscovered(
  access: string,
  credentialId: number,
): Promise<DiscoverResponse> {
  return api<DiscoverResponse>("/admin/models/discover", {
    method: "POST",
    body: { credential_id: credentialId },
    access,
  });
}

async function bulkRegister(
  access: string,
  credentialId: number,
  models: BulkRegisterItem[],
): Promise<BulkRegisterResponse> {
  return api<BulkRegisterResponse>("/admin/models/bulk-register", {
    method: "POST",
    body: { credential_id: credentialId, models },
    access,
  });
}

export interface DiscoverModelsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  credentialId: number;
  credentialName: string;
  /** 凭证支持的 modality 列表。 */
  availableTypes: string[];
  /** 当前已注册的 name@type，用于去重。 */
  existing: string[];
  token: string;
  onSaved?: () => void;
}

export function DiscoverModelsDialog({
  open,
  onOpenChange,
  credentialId,
  credentialName,
  availableTypes,
  existing,
  token,
  onSaved,
}: DiscoverModelsDialogProps) {
  const [discovered, setDiscovered] = useState<DiscoveredModel[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [type, setType] = useState<string>(availableTypes[0] ?? "language");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSelected(new Set());
    setSearch("");
    setError(null);
    setType(availableTypes[0] ?? "language");
    setLoading(true);
    fetchDiscovered(token, credentialId)
      .then((d) => setDiscovered(d.items ?? []))
      .catch((e) => setError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e)))
      .finally(() => setLoading(false));
  }, [open, credentialId, token, availableTypes]);

  const filtered = useMemo(() => {
    if (!search.trim()) return discovered;
    const q = search.toLowerCase();
    return discovered.filter((m) => m.name.toLowerCase().includes(q));
  }, [discovered, search]);

  const showCustom =
    search.trim() !== "" &&
    !discovered.some((m) => m.name.toLowerCase() === search.trim().toLowerCase());

  const register = useMutation({
    mutationFn: () => {
      const items: BulkRegisterItem[] = [];
      const seen = new Set<string>();
      for (const m of discovered) {
        if (selected.has(m.name) && !seen.has(m.name)) {
          items.push({ name: m.name, type: type as BulkRegisterItem["type"] });
          seen.add(m.name);
        }
      }
      if (showCustom) {
        items.push({
          name: search.trim(),
          type: type as BulkRegisterItem["type"],
        });
      }
      return bulkRegister(token, credentialId, items);
    },
    onSuccess: () => {
      onSaved?.();
      onOpenChange(false);
    },
  });

  if (!open) return null;

  const toggle = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const toggleAll = () => {
    const all = filtered.every((m) => selected.has(m.name));
    setSelected((prev) => {
      const next = new Set(prev);
      if (all) {
        filtered.forEach((m) => next.delete(m.name));
      } else {
        filtered.forEach((m) => next.add(m.name));
      }
      return next;
    });
  };

  const totalSelected = selected.size + (showCustom ? 1 : 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-lg flex-col rounded-lg border bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b p-4">
          <div>
            <h2 className="text-base font-semibold">
              模型发现 · {credentialName}
            </h2>
            <p className="text-xs text-muted-foreground">
              勾选要添加的模型；按 modality 注册到凭证下
            </p>
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            className="h-8 w-8"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {loading ? (
            <p className="py-12 text-center text-sm text-muted-foreground">
              拉取中…
            </p>
          ) : error ? (
            <p className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </p>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium">modality</label>
                <select
                  className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                >
                  {availableTypes.map((t) => (
                    <option key={t} value={t}>
                      {MODALITY_LABEL[t] ?? t}
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-muted-foreground">
                  所选模型会以该 modality 注册
                </p>
              </div>

              <Input
                placeholder="搜索 / 输入自定义模型名"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />

              {filtered.length > 0 && (
                <div className="flex items-center justify-between text-xs">
                  <Button type="button" size="sm" variant="outline" onClick={toggleAll}>
                    {filtered.every((m) => selected.has(m.name))
                      ? "取消全选"
                      : "全选"}
                  </Button>
                  <span className="text-muted-foreground">
                    已选 {selected.size} / {filtered.length}
                  </span>
                </div>
              )}

              <div className="space-y-1">
                {filtered.length === 0 && !showCustom && (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    没发现模型
                  </p>
                )}
                {filtered.map((m) => {
                  const isExisting = existing.includes(`${m.name}@${type}`);
                  return (
                    <label
                      key={m.name}
                      className="flex items-center gap-2 rounded p-1.5 text-sm hover:bg-muted"
                    >
                      <input
                        type="checkbox"
                        className="rounded"
                        checked={selected.has(m.name)}
                        onChange={() => toggle(m.name)}
                        disabled={isExisting}
                      />
                      <span className="flex-1 truncate font-mono text-xs">
                        {m.name}
                      </span>
                      {isExisting && (
                        <span className="text-[10px] text-muted-foreground">
                          已存在
                        </span>
                      )}
                    </label>
                  );
                })}

                {showCustom && (
                  <label className="mt-2 flex items-center gap-2 border-t pt-2 text-sm">
                    <input type="checkbox" className="rounded" disabled readOnly />
                    <span className="text-muted-foreground">
                      自定义：{search.trim()}
                    </span>
                  </label>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t p-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button
            type="button"
            onClick={() => register.mutate()}
            disabled={totalSelected === 0 || register.isPending}
          >
            {register.isPending ? "添加中…" : `添加（${totalSelected}）`}
          </Button>
        </div>
      </div>
    </div>
  );
}
