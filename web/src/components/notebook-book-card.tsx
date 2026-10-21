import { Link } from "react-router-dom";
import { Pin } from "lucide-react";
import { NotebookCardMenu } from "@/components/notebook-card-menu";
import { GeneratedCover } from "@/components/generated-cover";
import { isRemoteCover } from "@/lib/cover-gen";
import { formatDateZh } from "@/lib/utils";

export interface NotebookBookCardData {
  id: number;
  title: string;
  icon: string | null;
  cover_url?: string | null;
  is_pinned: boolean;
  share_all?: boolean;
  source_count: number;
  note_count?: number;
  updated_at: string | null;
}

function formatSources(n: number): string {
  return n === 1 ? "1 个来源" : `${n} 个来源`;
}

export function NotebookBookCard({
  notebook: nb,
  onUpdateTitle,
  onTogglePin,
  onToggleShare,
  onDelete,
  onAddToCollection,
}: {
  notebook: NotebookBookCardData;
  onUpdateTitle: (id: number) => void;
  onTogglePin: (id: number) => void;
  onToggleShare?: (id: number) => void;
  onDelete: (id: number) => void;
  onAddToCollection?: (id: number) => void;
}) {
  const remote = isRemoteCover(nb.cover_url);
  const sourcesLabel = formatSources(nb.source_count ?? 0);

  return (
    <article className="notebook-card group soft-tile soft-tile-hover flex flex-col overflow-hidden">
      <Link
        to={`/notebooks/${nb.id}`}
        className="notebook-cover relative block w-full overflow-hidden text-left"
        aria-label={nb.title}
      >
        {remote ? (
          <img
            src={nb.cover_url!}
            alt=""
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <GeneratedCover
            title={nb.title}
            coverUrl={nb.cover_url}
            variant={nb.id}
            className="h-full w-full"
          />
        )}
        {/* 极淡书脊暗示，不破坏一体卡片感 */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 w-[3px] bg-gradient-to-r from-black/25 via-white/20 to-transparent opacity-70"
        />
        <div className="absolute left-2 top-2 z-[1] flex flex-col gap-1">
          {nb.is_pinned ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-medium text-amber-700 shadow-sm backdrop-blur-sm">
              <Pin className="h-3 w-3 fill-amber-500 text-amber-500" />
              置顶
            </span>
          ) : null}
          {nb.share_all ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-medium text-emerald-700 shadow-sm backdrop-blur-sm">
              公开
            </span>
          ) : null}
        </div>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-black/20 to-transparent opacity-0 transition-opacity duration-200 group-hover:opacity-100" />
      </Link>

      <div className="flex items-start gap-1.5 px-2.5 pb-2.5 pt-2">
        <Link to={`/notebooks/${nb.id}`} className="min-w-0 flex-1 text-left">
          <h3 className="line-clamp-2 text-[13px] font-semibold leading-snug tracking-tight text-foreground">
            {nb.title}
          </h3>
          <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[10px] text-muted-foreground">
            <span className="inline-flex items-center rounded-full bg-muted/80 px-1.5 py-0.5 font-medium text-foreground/80">
              {sourcesLabel}
            </span>
            {nb.updated_at ? (
              <span className="truncate">{formatDateZh(nb.updated_at)}</span>
            ) : null}
          </p>
        </Link>
        <div
          className="shrink-0 pt-0.5 opacity-70 transition-opacity group-hover:opacity-100 focus-within:opacity-100"
          onClick={(e) => e.stopPropagation()}
        >
          <NotebookCardMenu
            notebookId={nb.id}
            isPinned={nb.is_pinned}
            shareAll={!!nb.share_all}
            onRequestEdit={onUpdateTitle}
            onAddToCollection={onAddToCollection}
            onTogglePin={onTogglePin}
            onToggleShare={onToggleShare}
            onDelete={onDelete}
          />
        </div>
      </div>
    </article>
  );
}
