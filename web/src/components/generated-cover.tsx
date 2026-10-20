import {
  coverStyleFromVariant,
  parseCoverStyle,
  type CoverPalette,
  type CoverPattern,
  type CoverStyle,
} from "@/lib/cover-gen";

function Orbs({ p }: { p: CoverPalette }) {
  return (
    <>
      <circle cx="78" cy="42" r="52" fill={p.mist} opacity="0.35" />
      <circle cx="22" cy="78" r="38" fill={p.c} opacity="0.28" />
      <circle cx="88" cy="88" r="24" fill={p.ink} opacity="0.12" />
      <circle cx="36" cy="28" r="14" fill={p.ink} opacity="0.18" />
    </>
  );
}

function Waves({ p }: { p: CoverPalette }) {
  return (
    <>
      <path
        d="M0 55 Q 25 40 50 55 T 100 55 V 100 H 0 Z"
        fill={p.mist}
        opacity="0.3"
      />
      <path
        d="M0 68 Q 25 55 50 68 T 100 68 V 100 H 0 Z"
        fill={p.c}
        opacity="0.35"
      />
      <path
        d="M0 82 Q 25 72 50 82 T 100 82 V 100 H 0 Z"
        fill={p.ink}
        opacity="0.12"
      />
    </>
  );
}

function Mesh({ p }: { p: CoverPalette }) {
  const lines = [18, 32, 46, 60, 74];
  return (
    <>
      {lines.map((y) => (
        <line
          key={`h-${y}`}
          x1="8"
          y1={y}
          x2="92"
          y2={y + 4}
          stroke={p.c}
          strokeWidth="0.6"
          opacity="0.35"
        />
      ))}
      {lines.map((x) => (
        <line
          key={`v-${x}`}
          x1={x}
          y1="12"
          x2={x + 6}
          y2="88"
          stroke={p.mist}
          strokeWidth="0.55"
          opacity="0.3"
        />
      ))}
      <circle cx="70" cy="30" r="28" fill={p.mist} opacity="0.22" />
    </>
  );
}

function Beams({ p }: { p: CoverPalette }) {
  return (
    <>
      <polygon points="50,8 62,92 38,92" fill={p.mist} opacity="0.25" />
      <polygon points="28,12 40,92 16,92" fill={p.c} opacity="0.2" />
      <polygon points="78,18 88,92 68,92" fill={p.ink} opacity="0.12" />
      <circle cx="50" cy="36" r="10" fill={p.ink} opacity="0.2" />
    </>
  );
}

function Pattern({ kind, p }: { kind: CoverPattern; p: CoverPalette }) {
  switch (kind) {
    case "waves":
      return <Waves p={p} />;
    case "mesh":
      return <Mesh p={p} />;
    case "beams":
      return <Beams p={p} />;
    default:
      return <Orbs p={p} />;
  }
}

export function GeneratedCover({
  title,
  coverUrl,
  variant,
  style,
  meta,
  className,
}: {
  title: string;
  /** Prefer this — resolves gen:v1 / gen:v2 */
  coverUrl?: string | null;
  /** Legacy preset index when coverUrl absent */
  variant?: number;
  style?: CoverStyle;
  meta?: string | null;
  className?: string;
}) {
  const resolved: CoverStyle =
    style ??
    (coverUrl
      ? parseCoverStyle(coverUrl, variant ?? 0)
      : coverStyleFromVariant(variant ?? 0));
  const { palette: p, pattern } = resolved;
  const short = title.trim() || "未命名";
  const seed = (p.a + pattern).length;
  const uid = `cg-${seed}-${short.length}`;
  const titleLines = wrapTitle(short, 12);
  const titleBlockY = meta ? 78 : 92;

  return (
    <svg
      viewBox="0 0 100 140"
      preserveAspectRatio="xMidYMid slice"
      className={className}
      role="img"
      aria-label={short}
    >
      <defs>
        <linearGradient id={`${uid}-bg`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={p.a} />
          <stop offset="55%" stopColor={p.b} />
          <stop offset="100%" stopColor={p.c} />
        </linearGradient>
        <linearGradient id={`${uid}-veil`} x1="0" y1="0.45" x2="0" y2="1">
          <stop offset="0%" stopColor={p.a} stopOpacity="0" />
          <stop offset="100%" stopColor={p.a} stopOpacity="0.55" />
        </linearGradient>
        <filter id={`${uid}-soft`}>
          <feGaussianBlur stdDeviation="0.4" />
        </filter>
      </defs>

      <rect width="100" height="140" fill={`url(#${uid}-bg)`} />

      <g opacity="0.95" filter={`url(#${uid}-soft)`}>
        <Pattern kind={pattern} p={p} />
      </g>

      <g opacity="0.08">
        {Array.from({ length: 18 }, (_, i) => (
          <circle
            key={i}
            cx={(i * 17 + seed * 3) % 100}
            cy={(i * 23 + seed * 7) % 140}
            r="0.45"
            fill={p.ink}
          />
        ))}
      </g>

      <rect width="100" height="140" fill={`url(#${uid}-veil)`} />

      <rect x="10" y="12" width="14" height="3.2" rx="1.2" fill={p.ink} opacity="0.55" />

      {titleLines.map((line, i) => (
        <text
          key={i}
          x="10"
          y={titleBlockY + i * 11}
          fill={p.ink}
          fontSize="8.5"
          fontWeight="650"
          fontFamily='ui-sans-serif, system-ui, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
        >
          {line}
        </text>
      ))}

      {meta ? (
        <text
          x="10"
          y="128"
          fill={p.ink}
          opacity="0.72"
          fontSize="5.5"
          fontFamily='ui-sans-serif, system-ui, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
        >
          {truncateMeta(meta, 28)}
        </text>
      ) : null}
    </svg>
  );
}

function wrapTitle(title: string, maxChars: number): string[] {
  const chars = Array.from(title);
  if (chars.length <= maxChars) return [title];
  const lines: string[] = [];
  let i = 0;
  while (i < chars.length && lines.length < 3) {
    const end = Math.min(i + maxChars, chars.length);
    let chunk = chars.slice(i, end).join("");
    if (lines.length === 2 && end < chars.length) {
      chunk = chars.slice(i, Math.min(i + maxChars - 1, chars.length)).join("") + "…";
      lines.push(chunk);
      break;
    }
    lines.push(chunk);
    i = end;
  }
  return lines;
}

function truncateMeta(meta: string, maxChars: number): string {
  const chars = Array.from(meta);
  if (chars.length <= maxChars) return meta;
  return chars.slice(0, maxChars - 1).join("") + "…";
}
