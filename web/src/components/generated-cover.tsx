import {
  coverStyleFromVariant,
  isEmptyCover,
  isRemoteCover,
  parseCoverStyle,
  type CoverLayout,
  type CoverMotif,
  type CoverPalette,
  type CoverPattern,
  type CoverStyle,
} from "@/lib/cover-gen";

/** Covers are graphics-only — title/meta live under the card, never baked into the SVG. */

function Orbs({ p }: { p: CoverPalette }) {
  return (
    <>
      <circle cx="78" cy="42" r="52" fill={p.mist} opacity="0.28" />
      <circle cx="22" cy="78" r="38" fill={p.c} opacity="0.22" />
      <circle cx="88" cy="88" r="24" fill={p.ink} opacity="0.1" />
    </>
  );
}

function Waves({ p }: { p: CoverPalette }) {
  return (
    <>
      <path d="M0 55 Q 25 40 50 55 T 100 55 V 100 H 0 Z" fill={p.mist} opacity="0.28" />
      <path d="M0 68 Q 25 55 50 68 T 100 68 V 100 H 0 Z" fill={p.c} opacity="0.3" />
      <path d="M0 82 Q 25 72 50 82 T 100 82 V 100 H 0 Z" fill={p.ink} opacity="0.1" />
    </>
  );
}

function Mesh({ p }: { p: CoverPalette }) {
  const lines = [18, 32, 46, 60, 74];
  return (
    <>
      {lines.map((y) => (
        <line key={`h-${y}`} x1="8" y1={y} x2="92" y2={y + 4} stroke={p.c} strokeWidth="0.7" opacity="0.32" />
      ))}
      {lines.map((x) => (
        <line key={`v-${x}`} x1={x} y1="12" x2={x + 6} y2="88" stroke={p.mist} strokeWidth="0.65" opacity="0.28" />
      ))}
    </>
  );
}

function Beams({ p }: { p: CoverPalette }) {
  return (
    <>
      <polygon points="50,8 62,92 38,92" fill={p.mist} opacity="0.22" />
      <polygon points="28,12 40,92 16,92" fill={p.c} opacity="0.18" />
      <polygon points="78,18 88,92 68,92" fill={p.ink} opacity="0.1" />
    </>
  );
}

function Rings({ p }: { p: CoverPalette }) {
  return (
    <>
      <circle cx="70" cy="42" r="36" fill="none" stroke={p.mist} strokeWidth="2.4" opacity="0.35" />
      <circle cx="70" cy="42" r="24" fill="none" stroke={p.c} strokeWidth="1.8" opacity="0.4" />
      <circle cx="70" cy="42" r="12" fill="none" stroke={p.ink} strokeWidth="1.2" opacity="0.28" />
    </>
  );
}

function Grid({ p }: { p: CoverPalette }) {
  return (
    <>
      {Array.from({ length: 6 }, (_, i) => (
        <line key={`gv-${i}`} x1={12 + i * 14} y1="10" x2={12 + i * 14} y2="110" stroke={p.c} strokeWidth="0.55" opacity="0.26" />
      ))}
      {Array.from({ length: 7 }, (_, i) => (
        <line key={`gh-${i}`} x1="8" y1={16 + i * 14} x2="92" y2={16 + i * 14} stroke={p.mist} strokeWidth="0.55" opacity="0.22" />
      ))}
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
    case "rings":
      return <Rings p={p} />;
    case "grid":
      return <Grid p={p} />;
    default:
      return <Orbs p={p} />;
  }
}

/** Theme motifs — simple SVG shapes, clearly different families */
function MotifArt({
  motif,
  p,
  x = 50,
  y = 62,
  scale = 1.25,
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
        <g transform={t} opacity="0.92">
          <circle cx="0" cy="8" r="18" fill="none" stroke={p.c} strokeWidth="2.2" opacity="0.7" />
          <circle cx="0" cy="8" r="11" fill="none" stroke={p.mist} strokeWidth="1.6" opacity="0.85" />
          <path d="M-2 -10 L6 -2 L1 -2 L4 12 L-5 2 L1 2 Z" fill={p.ink} opacity="0.95" />
        </g>
      );
    case "tech":
      return (
        <g transform={t} opacity="0.9">
          <polygon points="0,-16 14,-8 14,8 0,16 -14,8 -14,-8" fill="none" stroke={p.c} strokeWidth="1.8" />
          <circle cx="0" cy="0" r="4.5" fill={p.ink} />
          <circle cx="14" cy="-8" r="2.2" fill={p.mist} />
          <circle cx="-14" cy="8" r="2.2" fill={p.mist} />
          <line x1="0" y1="0" x2="14" y2="-8" stroke={p.mist} strokeWidth="1.2" />
          <line x1="0" y1="0" x2="-14" y2="8" stroke={p.mist} strokeWidth="1.2" />
        </g>
      );
    case "finance":
      return (
        <g transform={t} opacity="0.92">
          <rect x="-14" y="6" width="5" height="10" rx="1" fill={p.c} opacity="0.75" />
          <rect x="-6" y="0" width="5" height="16" rx="1" fill={p.mist} opacity="0.85" />
          <rect x="2" y="-8" width="5" height="24" rx="1" fill={p.ink} opacity="0.9" />
          <rect x="10" y="-14" width="5" height="30" rx="1" fill={p.c} opacity="0.7" />
          <path d="M-16 -6 Q 0 -18 16 -4" fill="none" stroke={p.ink} strokeWidth="1.6" opacity="0.7" />
        </g>
      );
    case "food":
      return (
        <g transform={t} opacity="0.9">
          <ellipse cx="0" cy="10" rx="18" ry="7" fill="none" stroke={p.c} strokeWidth="2" />
          <path d="M-10 4 Q -6 -8 -2 4" fill="none" stroke={p.ink} strokeWidth="1.6" opacity="0.85" />
          <path d="M0 2 Q 3 -10 6 2" fill="none" stroke={p.mist} strokeWidth="1.6" />
          <path d="M8 4 Q 12 -6 14 5" fill="none" stroke={p.ink} strokeWidth="1.4" opacity="0.7" />
        </g>
      );
    case "nature":
      return (
        <g transform={t} opacity="0.9">
          <path d="M0 14 L-18 14 L-8 0 L0 8 L10 -6 L18 14 Z" fill={p.c} opacity="0.35" />
          <path d="M-2 14 C -2 0, 10 -10, 16 -2 C 6 0, 2 8, -2 14 Z" fill={p.mist} opacity="0.85" />
          <line x1="-2" y1="14" x2="-2" y2="2" stroke={p.ink} strokeWidth="1.4" opacity="0.7" />
        </g>
      );
    case "creative":
      return (
        <g transform={t} opacity="0.9">
          <rect x="-12" y="-12" width="18" height="18" rx="3" fill={p.c} opacity="0.45" transform="rotate(18)" />
          <rect x="-4" y="-8" width="18" height="18" rx="3" fill={p.mist} opacity="0.55" transform="rotate(-12)" />
          <circle cx="4" cy="2" r="5" fill={p.ink} opacity="0.85" />
        </g>
      );
    case "study":
      return (
        <g transform={t} opacity="0.9">
          <rect x="-16" y="-10" width="28" height="22" rx="2.5" fill={p.c} opacity="0.35" />
          <rect x="-12" y="-6" width="22" height="3" rx="1" fill={p.ink} opacity="0.75" />
          <rect x="-12" y="0" width="16" height="2.4" rx="1" fill={p.mist} opacity="0.8" />
          <rect x="-12" y="5" width="12" height="2.4" rx="1" fill={p.mist} opacity="0.55" />
          <path d="M12 -12 L16 -12 L16 14 L12 12 Z" fill={p.ink} opacity="0.8" />
        </g>
      );
    default:
      return (
        <g transform={t} opacity="0.88">
          <circle cx="0" cy="0" r="16" fill="none" stroke={p.c} strokeWidth="2" />
          <circle cx="8" cy="-6" r="10" fill={p.mist} opacity="0.45" />
          <rect x="-14" y="6" width="20" height="8" rx="2" fill={p.ink} opacity="0.55" />
        </g>
      );
  }
}

type LayoutProps = {
  p: CoverPalette;
  pattern: CoverPattern;
  motif: CoverMotif;
  uid: string;
};

function LayoutAccent({ p, pattern, motif, uid }: LayoutProps) {
  return (
    <>
      <rect width="100" height="140" fill={`url(#${uid}-bg)`} />
      <g opacity="0.85">
        <Pattern kind={pattern} p={p} />
      </g>
      <rect x="0" y="0" width="7" height="140" fill={p.ink} opacity="0.92" />
      <rect x="7" y="0" width="2.2" height="140" fill={p.mist} opacity="0.75" />
      <MotifArt motif={motif} p={p} x={58} y={68} scale={1.35} />
      <circle cx="28" cy="108" r="18" fill={p.a} opacity="0.35" />
      <circle cx="82" cy="28" r="10" fill={p.ink} opacity="0.12" />
    </>
  );
}

function LayoutSplit({ p, pattern, motif, uid }: LayoutProps) {
  return (
    <>
      <rect width="100" height="140" fill={p.a} />
      <polygon points="0,0 100,0 100,72 0,118" fill={`url(#${uid}-bg)`} />
      <g opacity="0.55">
        <Pattern kind={pattern} p={p} />
      </g>
      <MotifArt motif={motif} p={p} x={54} y={58} scale={1.4} />
      <rect x="0" y="118" width="100" height="22" fill={p.a} opacity="0.55" />
      <rect x="12" y="126" width="28" height="3" rx="1.5" fill={p.mist} opacity="0.45" />
    </>
  );
}

function LayoutBadge({ p, pattern, motif, uid }: LayoutProps) {
  return (
    <>
      <rect width="100" height="140" fill={`url(#${uid}-bg)`} />
      <g opacity="0.5">
        <Pattern kind={pattern} p={p} />
      </g>
      <circle cx="50" cy="64" r="36" fill={p.a} opacity="0.4" />
      <circle cx="50" cy="64" r="28" fill={p.b} opacity="0.5" stroke={p.ink} strokeWidth="1.4" strokeOpacity="0.35" />
      <MotifArt motif={motif} p={p} x={50} y={60} scale={1.05} />
      <circle cx="18" cy="118" r="8" fill={p.c} opacity="0.35" />
      <circle cx="86" cy="22" r="6" fill={p.ink} opacity="0.15" />
    </>
  );
}

function LayoutBands({ p, pattern, motif }: LayoutProps) {
  return (
    <>
      <rect width="100" height="42" fill={p.a} />
      <rect y="42" width="100" height="56" fill={p.b} />
      <rect y="98" width="100" height="42" fill={p.a} />
      <g opacity="0.35" transform="translate(0 8)">
        <Pattern kind={pattern} p={p} />
      </g>
      <MotifArt motif={motif} p={p} x={50} y={68} scale={1.3} />
      <rect x="0" y="96" width="100" height="2.5" fill={p.mist} opacity="0.55" />
      <rect x="14" y="18" width="22" height="3" rx="1.5" fill={p.c} opacity="0.4" />
      <rect x="64" y="120" width="22" height="3" rx="1.5" fill={p.mist} opacity="0.4" />
    </>
  );
}

function LayoutFrame({ p, pattern, motif, uid }: LayoutProps) {
  return (
    <>
      <rect width="100" height="140" fill={`url(#${uid}-bg)`} />
      <g opacity="0.55">
        <Pattern kind={pattern} p={p} />
      </g>
      <rect x="8" y="8" width="84" height="124" rx="6" fill="none" stroke={p.ink} strokeWidth="1.4" opacity="0.55" />
      <rect x="11" y="11" width="78" height="118" rx="4" fill={p.a} opacity="0.28" />
      <MotifArt motif={motif} p={p} x={50} y={70} scale={1.35} />
      <rect x="22" y="24" width="16" height="3" rx="1.5" fill={p.c} opacity="0.45" />
      <rect x="62" y="112" width="16" height="3" rx="1.5" fill={p.mist} opacity="0.4" />
    </>
  );
}

function LayoutHero({ p, pattern, motif, uid }: LayoutProps) {
  return (
    <>
      <rect width="100" height="140" fill={`url(#${uid}-radial)`} />
      <g opacity="0.4">
        <Pattern kind={pattern} p={p} />
      </g>
      <MotifArt motif={motif} p={p} x={50} y={62} scale={1.55} />
      <rect x="0" y="0" width="100" height="140" fill={`url(#${uid}-veil)`} />
      <circle cx="18" cy="24" r="14" fill={p.c} opacity="0.18" />
      <circle cx="86" cy="112" r="20" fill={p.a} opacity="0.35" />
    </>
  );
}

function renderLayout(layout: CoverLayout, props: LayoutProps) {
  switch (layout) {
    case "split":
      return <LayoutSplit {...props} />;
    case "badge":
      return <LayoutBadge {...props} />;
    case "bands":
      return <LayoutBands {...props} />;
    case "frame":
      return <LayoutFrame {...props} />;
    case "hero":
      return <LayoutHero {...props} />;
    case "accent":
    default:
      return <LayoutAccent {...props} />;
  }
}

function EmptyCoverPlaceholder({ className, label }: { className?: string; label: string }) {
  return (
    <svg
      viewBox="0 0 100 140"
      preserveAspectRatio="xMidYMid slice"
      className={className}
      role="img"
      aria-label={label}
    >
      <rect width="100" height="140" fill="#F5F5F4" />
      <rect
        x="10"
        y="14"
        width="80"
        height="112"
        rx="6"
        fill="none"
        stroke="#D6D3D1"
        strokeWidth="1.6"
        strokeDasharray="4 3"
      />
      <circle cx="50" cy="58" r="14" fill="#E7E5E4" />
      <rect x="34" y="82" width="32" height="4" rx="2" fill="#D6D3D1" />
      <rect x="40" y="90" width="20" height="3" rx="1.5" fill="#E7E5E4" />
    </svg>
  );
}

export function GeneratedCover({
  title,
  coverUrl,
  variant,
  style,
  className,
}: {
  title: string;
  coverUrl?: string | null;
  variant?: number;
  style?: CoverStyle;
  /** @deprecated Ignored — covers never bake text into the image. */
  meta?: string | null;
  className?: string;
}) {
  const short = title.trim() || "未命名";
  // Explicit gen:empty only — null cover_url still uses variant + title (home cards).
  if (!style && isEmptyCover(coverUrl)) {
    return <EmptyCoverPlaceholder className={className} label="空封面" />;
  }
  if (!style && isRemoteCover(coverUrl)) {
    return (
      <img
        src={coverUrl!}
        alt={short}
        className={className}
        style={{ objectFit: "cover", width: "100%", height: "100%" }}
      />
    );
  }
  const resolved: CoverStyle =
    style ??
    (coverUrl
      ? parseCoverStyle(coverUrl, variant ?? 0, short)
      : coverStyleFromVariant(variant ?? 0, short));
  const { palette: p, pattern, layout, motif } = resolved;
  const seed = (p.a + pattern + layout + motif + short).length + short.charCodeAt(0);
  const uid = `cg-${seed}-${short.length}-${layout}`;

  const layoutProps: LayoutProps = {
    p,
    pattern,
    motif,
    uid,
  };

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
          <stop offset="48%" stopColor={p.b} />
          <stop offset="100%" stopColor={p.c} />
        </linearGradient>
        <radialGradient id={`${uid}-radial`} cx="30%" cy="35%" r="75%">
          <stop offset="0%" stopColor={p.c} stopOpacity="0.55" />
          <stop offset="45%" stopColor={p.b} />
          <stop offset="100%" stopColor={p.a} />
        </radialGradient>
        <linearGradient id={`${uid}-veil`} x1="0" y1="0.35" x2="0" y2="1">
          <stop offset="0%" stopColor={p.a} stopOpacity="0" />
          <stop offset="100%" stopColor={p.a} stopOpacity="0.45" />
        </linearGradient>
      </defs>

      {renderLayout(layout, layoutProps)}
    </svg>
  );
}
