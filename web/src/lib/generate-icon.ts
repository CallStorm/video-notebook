import { api } from "@/lib/api";

/** 按名称调用后端，用默认 logo（或 chat）模型生成单个 emoji。 */
export async function generateIcon(access: string, name: string): Promise<string> {
  const body = await api<{ icon: string }>("/icons/generate", {
    method: "POST",
    access,
    body: { name: name.trim() },
  });
  return body.icon;
}
