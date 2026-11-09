/** 从抖音/分享文案里抽出第一个 http(s) 链接 */
export function extractUrl(text: string): string | null {
  if (!text) return null
  const trimmed = text.trim()
  if (/^https?:\/\//i.test(trimmed) && !/\s/.test(trimmed)) {
    return trimmed
  }
  const m = trimmed.match(/https?:\/\/[^\s\u4e00-\u9fff]+/i)
  if (!m) return null
  return m[0].replace(/[)\],.，。；;]+$/g, '')
}
