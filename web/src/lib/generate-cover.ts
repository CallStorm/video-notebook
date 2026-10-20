import { api } from "@/lib/api";

export interface GeneratedCoverResult {
  cover_url: string;
  pattern: string;
  a: string;
  b: string;
  c: string;
  ink: string;
  mist: string;
}

/** 调用后端 LLM，按名称+描述生成封面样式 token。 */
export async function generateCover(
  access: string,
  title: string,
  description?: string,
): Promise<GeneratedCoverResult> {
  return api<GeneratedCoverResult>("/covers/generate", {
    method: "POST",
    access,
    body: {
      title: title.trim(),
      description: description?.trim() || null,
    },
  });
}
