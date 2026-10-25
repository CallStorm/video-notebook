import { api } from "@/lib/api";

export interface GeneratedCoverResult {
  cover_url: string;
  layout: string;
  motif: string;
  pattern: string;
  a: string;
  b: string;
  c: string;
  ink: string;
  mist: string;
  label?: string;
}

/** 调用后端，按名称+描述生成封面（文生图 URL 或 SVG token）。 */
export async function generateCover(
  access: string,
  title: string,
  description?: string,
  opts?: { mode?: "image" | "svg" },
): Promise<GeneratedCoverResult> {
  return api<GeneratedCoverResult>("/covers/generate", {
    method: "POST",
    access,
    body: {
      title: title.trim(),
      description: description?.trim() || null,
      ...(opts?.mode ? { mode: opts.mode } : {}),
    },
  });
}
