/** 品牌标：视频画面 + 笔记折角，区别于通用笔记本图标。 */
export function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className="relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-xl shadow-soft"
        aria-hidden
      >
        <svg viewBox="0 0 32 32" className="h-8 w-8" fill="none">
          <rect width="32" height="32" rx="10" fill="#2563EB" />
          {/* screen / page */}
          <rect x="7" y="8" width="18" height="14" rx="2.5" fill="white" fillOpacity="0.95" />
          {/* play */}
          <path d="M13.2 12.2v7.6L19.8 16 13.2 12.2Z" fill="#2563EB" />
          {/* note lines */}
          <path
            d="M8.5 24.5h9.5M8.5 26.5h6"
            stroke="white"
            strokeOpacity="0.9"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
          {/* folded corner — AI 辅色点缀 */}
          <path d="M21 8h4v4l-4-4Z" fill="#0D9488" fillOpacity="0.85" />
        </svg>
      </div>
      <span className="text-lg font-semibold tracking-tight text-foreground">
        视频笔记
      </span>
    </div>
  );
}
