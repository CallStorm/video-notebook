/** Cover tokens stored in cover_url:
 *  - gen:v1:{0-11} legacy preset index
 *  - gen:v2:{pattern}:{a}:{b}:{c}:{ink}:{mist} legacy AI style
 *  - gen:v3:{layout}:{motif}:{pattern}:{a}:{b}:{c}:{ink}:{mist} layout+motif covers
 */

export const COVER_VARIANT_COUNT = 12;

export const GEN_V1_PREFIX = "gen:v1:";
export const GEN_V2_PREFIX = "gen:v2:";
export const GEN_V3_PREFIX = "gen:v3:";
/** Create-dialog placeholder - no title-driven motif until user clicks generate. */
export const EMPTY_COVER_TOKEN = "gen:empty";

export type CoverPalette = {
  a: string;
  b: string;
  c: string;
  ink: string;
  mist: string;
};

export const COVER_PALETTES: CoverPalette[] = [
  { a: "#0B1F4A", b: "#2563EB", c: "#93C5FD", ink: "#F8FAFC", mist: "#60A5FA" },
  { a: "#042F2E", b: "#0D9488", c: "#5EEAD4", ink: "#F0FDFA", mist: "#2DD4BF" },
  { a: "#0F172A", b: "#334155", c: "#94A3B8", ink: "#F8FAFC", mist: "#64748B" },
  { a: "#1E3A8A", b: "#3B82F6", c: "#BFDBFE", ink: "#EFF6FF", mist: "#60A5FA" },
  { a: "#134E4A", b: "#14B8A6", c: "#99F6E4", ink: "#F0FDFA", mist: "#2DD4BF" },
  { a: "#1E1B4B", b: "#4F46E5", c: "#A5B4FC", ink: "#EEF2FF", mist: "#818CF8" },
  { a: "#082F49", b: "#0284C7", c: "#7DD3FC", ink: "#F0F9FF", mist: "#38BDF8" },
  { a: "#14532D", b: "#059669", c: "#6EE7B7", ink: "#ECFDF5", mist: "#34D399" },
  { a: "#1C1917", b: "#44403C", c: "#A8A29E", ink: "#FAFAF9", mist: "#78716C" },
  { a: "#172554", b: "#1D4ED8", c: "#93C5FD", ink: "#EFF6FF", mist: "#3B82F6" },
  { a: "#083344", b: "#0891B2", c: "#67E8F9", ink: "#ECFEFF", mist: "#22D3EE" },
  { a: "#312E81", b: "#6366F1", c: "#C7D2FE", ink: "#EEF2FF", mist: "#818CF8" },
];

export type CoverPattern = "orbs" | "waves" | "mesh" | "beams" | "rings" | "grid";
export type CoverLayout = "accent" | "split" | "badge" | "bands" | "frame" | "hero";
export type CoverMotif =
  | "ev"
  | "tech"
  | "finance"
  | "food"
  | "nature"
  | "creative"
  | "study"
  | "abstract";

const PATTERNS: CoverPattern[] = ["orbs", "waves", "mesh", "beams", "rings", "grid"];
const LAYOUTS: CoverLayout[] = ["accent", "split", "badge", "bands", "frame", "hero"];
const MOTIFS: CoverMotif[] = [
  "ev",
  "tech",
  "finance",
  "food",
  "nature",
  "creative",
  "study",
  "abstract",
];

export type CoverStyle = {
  palette: CoverPalette;
  pattern: CoverPattern;
  layout: CoverLayout;
  motif: CoverMotif;
  label?: string;
};

/** Neutral muted palette for empty / never-generated covers. */
export const EMPTY_COVER_STYLE: CoverStyle = {
  palette: { a: "#E7E5E4", b: "#D6D3D1", c: "#A8A29E", ink: "#57534E", mist: "#78716C" },
  pattern: "orbs",
  layout: "accent",
  motif: "abstract",
  label: "",
};

type ThemeHit = {
  motif: CoverMotif;
  layouts: CoverLayout[];
  label: string;
};

const THEME_RULES: { keys: string[]; motif: CoverMotif; layouts: CoverLayout[]; label: string }[] = [
  {
    keys: ["新能源", "电动", "汽车", "充电", "能源", "电池", "电车", "EV", "ev"],
    motif: "ev",
    layouts: ["hero", "split", "accent"],
    label: "",
  },
  {
    keys: ["科技", "编程", "代码", "AI", "算法", "数据", "数字", "互联网", "软件", "技术", "工程", "芯片"],
    motif: "tech",
    layouts: ["accent", "frame", "split"],
    label: "",
  },
  {
    keys: ["经济", "财经", "金融", "财政", "投资", "股市", "理财", "商业", "营销", "职场", "管理", "财务", "合同", "造价", "预算", "审计", "会计"],
    motif: "finance",
    layouts: ["bands", "accent", "frame"],
    label: "",
  },
  {
    keys: ["自然", "健康", "运动", "环保", "植物", "旅行", "户外", "生态", "工地", "施工", "建筑", "土木", "工程现场"],
    motif: "nature",
    layouts: ["hero", "split", "bands"],
    label: "",
  },
  {
    keys: ["美食", "餐饮", "料理", "烹饪", "探店", "食谱"],
    motif: "food",
    layouts: ["badge", "hero", "bands"],
    label: "",
  },
  {
    keys: ["创意", "设计", "艺术", "音乐", "电影", "娱乐", "游戏", "党建", "党史", "红色", "思政"],
    motif: "creative",
    layouts: ["badge", "split", "frame"],
    label: "",
  },
  {
    keys: ["学习", "教育", "考试", "课程", "笔记", "知识", "阅读", "书"],
    motif: "study",
    layouts: ["accent", "frame", "bands"],
    label: "",
  },
  {
    keys: ["情感", "恋爱", "生活", "日常", "人物", "故事"],
    motif: "abstract",
    layouts: ["badge", "hero", "bands"],
    label: "",
  },
];

function hashTitle(title: string): number {
  let h = 2166136261;
  for (let i = 0; i < title.length; i++) {
    h ^= title.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function inferThemeFromTitle(title: string): ThemeHit {
  const t = title.trim();
  for (const rule of THEME_RULES) {
    if (rule.keys.some((k) => t.includes(k))) {
      return { motif: rule.motif, layouts: rule.layouts, label: rule.label };
    }
  }
  const seed = hashTitle(t || "未命名");
  return {
    motif: "abstract",
    layouts: [LAYOUTS[seed % LAYOUTS.length]],
    label: "",
  };
}

export function isRemoteCover(coverUrl: string | null | undefined): boolean {
  if (!coverUrl) return false;
  return (
    coverUrl.startsWith("http://") ||
    coverUrl.startsWith("https://") ||
    coverUrl.startsWith("/")
  );
}

export function isGenCover(coverUrl: string | null | undefined): boolean {
  return Boolean(
    coverUrl?.startsWith(GEN_V1_PREFIX) ||
      coverUrl?.startsWith(GEN_V2_PREFIX) ||
      coverUrl?.startsWith(GEN_V3_PREFIX),
  );
}

export function isEmptyCover(coverUrl: string | null | undefined): boolean {
  // Only the explicit create-dialog token (or blank string). null/undefined
  // still means "derive from variant" for existing notebook cards.
  if (coverUrl == null) return false;
  const t = coverUrl.trim();
  return t === "" || t === EMPTY_COVER_TOKEN;
}

function hex6(raw: string, fallback: string): string {
  const s = raw.trim().replace(/^#/, "");
  if (!/^[0-9A-Fa-f]{6}$/.test(s)) return fallback;
  return `#${s}`;
}

function asPattern(raw: string): CoverPattern {
  return (PATTERNS.includes(raw as CoverPattern) ? raw : "orbs") as CoverPattern;
}

function asLayout(raw: string): CoverLayout {
  return (LAYOUTS.includes(raw as CoverLayout) ? raw : "accent") as CoverLayout;
}

function asMotif(raw: string): CoverMotif {
  return (MOTIFS.includes(raw as CoverMotif) ? raw : "abstract") as CoverMotif;
}

/** Derive layout/motif for legacy tokens so old covers also get the new look. */
function layoutMotifFromTitle(
  title: string | undefined,
  seedHint = 0,
): Pick<CoverStyle, "layout" | "motif" | "label"> {
  const theme = inferThemeFromTitle(title ?? "");
  const seed = hashTitle(title ?? "") ^ seedHint;
  const layout = theme.layouts[seed % theme.layouts.length];
  return { layout, motif: theme.motif, label: "" };
}

export function parseCoverStyle(
  coverUrl: string | null | undefined,
  fallbackId = 0,
  titleForLegacy?: string,
): CoverStyle {
  if (isEmptyCover(coverUrl)) {
    return { ...EMPTY_COVER_STYLE, palette: { ...EMPTY_COVER_STYLE.palette } };
  }
  if (coverUrl?.startsWith(GEN_V3_PREFIX)) {
    const parts = coverUrl.slice(GEN_V3_PREFIX.length).split(":");
    if (parts.length >= 8) {
      const [layoutRaw, motifRaw, patternRaw, a, b, c, ink, mist] = parts;
      return {
        layout: asLayout(layoutRaw),
        motif: asMotif(motifRaw),
        pattern: asPattern(patternRaw),
        palette: {
          a: hex6(a, "#0B1F4A"),
          b: hex6(b, "#2563EB"),
          c: hex6(c, "#93C5FD"),
          ink: hex6(ink, "#F8FAFC"),
          mist: hex6(mist, "#60A5FA"),
        },
        label: "",
      };
    }
  }
  if (coverUrl?.startsWith(GEN_V2_PREFIX)) {
    const parts = coverUrl.slice(GEN_V2_PREFIX.length).split(":");
    if (parts.length >= 6) {
      const [patternRaw, a, b, c, ink, mist] = parts;
      const lm = layoutMotifFromTitle(titleForLegacy, fallbackId);
      return {
        ...lm,
        pattern: asPattern(patternRaw),
        palette: {
          a: hex6(a, "#0B1F4A"),
          b: hex6(b, "#2563EB"),
          c: hex6(c, "#93C5FD"),
          ink: hex6(ink, "#F8FAFC"),
          mist: hex6(mist, "#60A5FA"),
        },
      };
    }
  }
  if (coverUrl?.startsWith(GEN_V1_PREFIX)) {
    const n = Number(coverUrl.slice(GEN_V1_PREFIX.length));
    if (Number.isFinite(n) && n >= 0) {
      return coverStyleFromVariant(
        Math.abs(Math.trunc(n)) % COVER_VARIANT_COUNT,
        titleForLegacy,
      );
    }
  }
  return coverStyleFromVariant(Math.abs(fallbackId) % COVER_VARIANT_COUNT, titleForLegacy);
}

export function coverStyleFromVariant(variant: number, titleForLegacy?: string): CoverStyle {
  const v = Math.abs(variant) % COVER_VARIANT_COUNT;
  const lm = layoutMotifFromTitle(titleForLegacy, v);
  return {
    palette: COVER_PALETTES[v],
    pattern: PATTERNS[v % PATTERNS.length],
    ...lm,
  };
}

/** @deprecated use parseCoverStyle */
export function parseCoverVariant(
  coverUrl: string | null | undefined,
  fallbackId: number,
): number {
  if (coverUrl?.startsWith(GEN_V1_PREFIX)) {
    const n = Number(coverUrl.slice(GEN_V1_PREFIX.length));
    if (Number.isFinite(n) && n >= 0) {
      return Math.abs(Math.trunc(n)) % COVER_VARIANT_COUNT;
    }
  }
  return Math.abs(fallbackId) % COVER_VARIANT_COUNT;
}

export function encodeCoverVariant(variant: number): string {
  return `${GEN_V1_PREFIX}${Math.abs(Math.trunc(variant)) % COVER_VARIANT_COUNT}`;
}

export function coverStyle(variant: number): CoverStyle {
  return coverStyleFromVariant(variant);
}
