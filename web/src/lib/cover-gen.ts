/** Cover tokens stored in cover_url:
 *  - gen:v1:{0-11} legacy preset index
 *  - gen:v2:{pattern}:{a}:{b}:{c}:{ink}:{mist} AI-generated style (hex without #)
 */

export const COVER_VARIANT_COUNT = 12;

export const GEN_V1_PREFIX = "gen:v1:";
export const GEN_V2_PREFIX = "gen:v2:";

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

export type CoverPattern = "orbs" | "waves" | "mesh" | "beams";

const PATTERNS: CoverPattern[] = ["orbs", "waves", "mesh", "beams"];

export type CoverStyle = {
  palette: CoverPalette;
  pattern: CoverPattern;
};

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
    coverUrl?.startsWith(GEN_V1_PREFIX) || coverUrl?.startsWith(GEN_V2_PREFIX),
  );
}

function hex6(raw: string, fallback: string): string {
  const s = raw.trim().replace(/^#/, "");
  if (!/^[0-9A-Fa-f]{6}$/.test(s)) return fallback;
  return `#${s}`;
}

export function parseCoverStyle(
  coverUrl: string | null | undefined,
  fallbackId = 0,
): CoverStyle {
  if (coverUrl?.startsWith(GEN_V2_PREFIX)) {
    const parts = coverUrl.slice(GEN_V2_PREFIX.length).split(":");
    if (parts.length >= 6) {
      const [patternRaw, a, b, c, ink, mist] = parts;
      const pattern = (PATTERNS.includes(patternRaw as CoverPattern)
        ? patternRaw
        : "orbs") as CoverPattern;
      return {
        pattern,
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
      return coverStyleFromVariant(Math.abs(Math.trunc(n)) % COVER_VARIANT_COUNT);
    }
  }
  return coverStyleFromVariant(Math.abs(fallbackId) % COVER_VARIANT_COUNT);
}

export function coverStyleFromVariant(variant: number): CoverStyle {
  const v = Math.abs(variant) % COVER_VARIANT_COUNT;
  return {
    palette: COVER_PALETTES[v],
    pattern: PATTERNS[v % PATTERNS.length],
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
