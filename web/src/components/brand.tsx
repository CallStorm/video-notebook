/** 品牌标：视频画面 + 笔记折角，区别于通用笔记本图标。 */
export function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className="relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-xl shadow-sm"
        aria-hidden
      >
        <svg viewBox="0 0 32 32" className="h-8 w-8" fill="none">
          <defs>
            <linearGradient id="vnb-brand" x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">
              <stop stopColor="#38BDF8" />
              <stop offset="0.55" stopColor="#2DD4BF" />
              <stop offset="1" stopColor="#34D399" />
            </linearGradient>
          </defs>
          <rect width="32" height="32" rx="10" fill="url(#vnb-brand)" />
          {/* screen / page */}
          <rect x="7" y="8" width="18" height="14" rx="2.5" fill="white" fillOpacity="0.92" />
          {/* play */}
          <path d="M13.2 12.2v7.6L19.8 16 13.2 12.2Z" fill="#0F766E" />
          {/* note lines */}
          <path
            d="M8.5 24.5h9.5M8.5 26.5h6"
            stroke="white"
            strokeOpacity="0.85"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
          {/* folded corner */}
          <path d="M21 8h4v4l-4-4Z" fill="#CCFBF1" fillOpacity="0.9" />
        </svg>
      </div>
      <span className="text-lg font-semibold tracking-tight text-foreground">
        视频笔记
      </span>
    </div>
  );
}
