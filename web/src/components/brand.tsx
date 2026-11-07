/** 品牌标：影知 / Videnote */
export function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <img
        src="/brand-mark.png"
        alt=""
        width={32}
        height={32}
        className="h-8 w-8 rounded-xl object-cover shadow-glow"
        aria-hidden
      />
      <div className="flex flex-col justify-center leading-none">
        <span className="text-lg font-semibold tracking-tight text-foreground">
          影知
        </span>
        <span className="mt-0.5 text-[10px] font-medium tracking-[0.14em] text-muted-foreground">
          Videnote
        </span>
      </div>
    </div>
  );
}
