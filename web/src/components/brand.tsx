import { Notebook } from "lucide-react";

export function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400 via-teal-400 to-emerald-400 text-white shadow-sm">
        <Notebook className="h-4 w-4" strokeWidth={2.25} />
      </div>
      <span className="text-lg font-semibold tracking-tight text-foreground">
        视频笔记
      </span>
    </div>
  );
}
