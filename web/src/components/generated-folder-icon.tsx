import {
  coverStyleFromVariant,
  parseCoverStyle,
  type CoverMotif,
  type CoverPalette,
  type CoverStyle,
} from "@/lib/cover-gen";

/** Compact theme glyph for directory icons (not full-bleed covers). */
function MotifGlyph({
  motif,
  p,
  x = 0,
  y = 0,
  scale = 1,
}: {
  motif: CoverMotif;
  p: CoverPalette;
  x?: number;
  y?: number;
  scale?: number;
}) {
  const t = `translate(${x} ${y}) scale(${scale})`;
  switch (motif) {
    case "ev":
      return (
        <g transform={t} opacity="0.95">
          <circle cx="0" cy="4" r="14" fill="none" stroke={p.c} strokeWidth="2.2" opacity="0.75" />
          <circle cx="0" cy="4" r="8.5" fill="none" stroke={p.mist} strokeWidth="1.6" />
          <path d="M-1.5 -10 L5 -2 L0.5 -2 L3 11 L-4 2 L1 2 Z" fill={p.ink} />
        </g>
      );
    case "tech":
      return (
        <g transform={t} opacity="0.95">
          <polygon
            points="0,-13 11,-6.5 11,6.5 0,13 -11,6.5 -11,-6.5"
            fill="none"
            stroke={p.c}
            strokeWidth="1.8"
          />
          <circle cx="0" cy="0" r="3.8" fill={p.ink} />
          <circle cx="11" cy="-6.5" r="2" fill={p.mist} />
          <circle cx="-11" cy="6.5" r="2" fill={p.mist} />
          <line x1="0" y1="0" x2="11" y2="-6.5" stroke={p.mist} strokeWidth="1.2" />
          <line x1="0" y1="0" x2="-11" y2="6.5" stroke={p.mist} strokeWidth="1.2" />
        </g>
      );
    case "finance":
      return (
        <g transform={t} opacity="0.95">
          <rect x="-12" y="4" width="4.5" height="9" rx="1" fill={p.c} opacity="0.8" />
          <rect x="-5" y="-1" width="4.5" height="14" rx="1" fill={p.mist} opacity="0.9" />
          <rect x="2" y="-8" width="4.5" height="21" rx="1" fill={p.ink} opacity="0.92" />
          <rect x="9" y="-13" width="4.5" height="26" rx="1" fill={p.c} opacity="0.75" />
        </g>
      );
    case "food":
      return (
        <g transform={t} opacity="0.95">
          <ellipse cx="0" cy="8" rx="14" ry="5.5" fill="none" stroke={p.c} strokeWidth="2" />
          <path d="M-8 3 Q -5 -8 -1.5 3" fill="none" stroke={p.ink} strokeWidth="1.6" />
          <path d="M1 1 Q 3.5 -9 6 1" fill="none" stroke={p.mist} strokeWidth="1.6" />
          <path d="M7 3 Q 10 -5 12 4" fill="none" stroke={p.ink} strokeWidth="1.4" opacity="0.75" />
        </g>
      );
    case "nature":
      return (
        <g transform={t} opacity="0.95">
          <path d="M0 12 L-14 12 L-6 0 L0 6 L8 -6 L14 12 Z" fill={p.c} opacity="0.4" />
          <path
            d="M-1.5 12 C -1.5 0, 8 -9, 13 -2 C 5 0, 1.5 6, -1.5 12 Z"
            fill={p.mist}
            opacity="0.9"
          />
          <line
            x1="-1.5"
            y1="12"
            x2="-1.5"
            y2="1"
            stroke={p.ink}
            strokeWidth="1.4"
            opacity="0.75"
          />
        </g>
      );
    case "creative":
      return (
        <g transform={t} opacity="0.95">
          <rect
            x="-10"
            y="-10"
            width="15"
            height="15"
            rx="2.5"
            fill={p.c}
            opacity="0.5"
            transform="rotate(18)"
          />
          <rect
            x="-3"
            y="-7"
            width="15"
            height="15"
            rx="2.5"
            fill={p.mist}
            opacity="0.6"
            transform="rotate(-12)"
          />
          <circle cx="3" cy="1" r="4.2" fill={p.ink} opacity="0.9" />
        </g>
      );
    case "study":
      return (
        <g transform={t} opacity="0.95">
          <rect x="-13" y="-9" width="24" height="18" rx="2" fill={p.c} opacity="0.4" />
          <rect x="-10" y="-5" width="18" height="2.6" rx="1" fill={p.ink} opacity="0.8" />
          <rect x="-10" y="0" width="13" height="2.2" rx="1" fill={p.mist} opacity="0.85" />
          <rect x="-10" y="4.5" width="10" height="2.2" rx="1" fill={p.mist} opacity="0.55" />
          <path d="M10 -10 L13.5 -10 L13.5 12 L10 10 Z" fill={p.ink} opacity="0.85" />
        </g>
      );
    default:
      return (
        <g transform={t} opacity="0.92">
          <circle cx="0" cy="0" r="13" fill="none" stroke={p.c} strokeWidth="2" />
          <circle cx="6" cy="-5" r="8" fill={p.mist} opacity="0.5" />
          <rect x="-11" y="5" width="16" height="6.5" rx="2" fill={p.ink} opacity="0.6" />
        </g>
      );
  }
}

/**
 * Large directory / folder chrome with an AI theme motif badge.
 * Style tokens reuse gen:v* cover_url values, but render as icons — not covers.
 */
export function GeneratedFolderIcon({
  title,
  coverUrl,
  variant = 0,
  className,
  showBadge = true,
}: {
  title: string;
  coverUrl?: string | null;
  variant?: number;
  className?: string;
  showBadge?: boolean;
}) {
  const short = title.trim() || "集合";
  const resolved: CoverStyle = coverUrl
    ? parseCoverStyle(coverUrl, variant, short)
    : coverStyleFromVariant(variant, short);
  const { palette: p, motif } = resolved;
  const seed = (p.a + motif + short).length + short.charCodeAt(0);
  const uid = `fi-${seed}-${short.length}-${motif}`;

  return (
    <svg
      viewBox="0 0 128 104"
      preserveAspectRatio="xMidYMid meet"
      className={className}
      role="img"
      aria-label={short}
    >
      <defs>
        <linearGradient id={`${uid}-body`} x1="0" y1="0" x2="0.15" y2="1">
          <stop offset="0%" stopColor={p.c} />
          <stop offset="42%" stopColor={p.b} />
          <stop offset="100%" stopColor={p.a} />
        </linearGradient>
        <linearGradient id={`${uid}-tab`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={p.mist} />
          <stop offset="100%" stopColor={p.b} />
        </linearGradient>
        <linearGradient id={`${uid}-sheen`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.32" />
          <stop offset="50%" stopColor="#ffffff" stopOpacity="0.06" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
        <filter id={`${uid}-soft`} x="-15%" y="-15%" width="130%" height="140%">
          <feDropShadow dx="0" dy="2.5" stdDeviation="2" floodColor={p.a} floodOpacity="0.3" />
        </filter>
      </defs>

      {/* Tab */}
      <path
        d="M14 34 V22 C14 18.5 16.5 16 20 16 H52 C55.5 16 58 17.5 59.5 20.5 L66 34 Z"
        fill={`url(#${uid}-tab)`}
      />
      <path
        d="M14 34 H66 L59.5 20.5 C58 17.5 55.5 16 52 16 H20"
        fill="none"
        stroke={p.ink}
        strokeOpacity="0.12"
        strokeWidth="1"
      />

      {/* Body */}
      <rect
        x="8"
        y="34"
        width="112"
        height="62"
        rx="12"
        fill={`url(#${uid}-body)`}
        filter={`url(#${uid}-soft)`}
      />
      <rect x="8" y="34" width="112" height="62" rx="12" fill={`url(#${uid}-sheen)`} />
      <rect
        x="8"
        y="34"
        width="112"
        height="62"
        rx="12"
        fill="none"
        stroke={p.ink}
        strokeOpacity="0.16"
        strokeWidth="1.2"
      />

      {/* Lip under tab */}
      <rect x="8" y="34" width="112" height="5" fill={p.a} opacity="0.18" />

      {showBadge ? (
        <>
          <rect x="42" y="48" width="44" height="36" rx="11" fill={p.a} opacity="0.4" />
          <rect
            x="44"
            y="50"
            width="40"
            height="32"
            rx="10"
            fill={p.b}
            opacity="0.32"
            stroke={p.ink}
            strokeOpacity="0.28"
            strokeWidth="1"
          />
          <MotifGlyph motif={motif} p={p} x={64} y={66} scale={0.92} />
        </>
      ) : null}
    </svg>
  );
}
