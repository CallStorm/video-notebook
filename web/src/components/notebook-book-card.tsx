import { Link } from "react-router-dom";
import { Pin } from "lucide-react";
import { NotebookCardMenu } from "@/components/notebook-card-menu";
import { GeneratedCover } from "@/components/generated-cover";
import { isRemoteCover } from "@/lib/cover-gen";
import type { ReactNode } from "react";
import { cn, formatDateZh } from "@/lib/utils";

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
  index_status?: string | null;
  index_error?: string | null;
}

function formatSources(n: number): string {
  return n === 1 ? "1 个来源" : `${n} 个来源`;
}


/** Cover overlay chips: frosted glass so they sit on any generated/remote cover. */
const coverChip =
  "inline-flex items-center gap-1 rounded-full border border-white/20 bg-black/40 px-2 py-0.5 text-[10px] font-medium leading-none text-white/95 shadow-[0_1px_2px_rgba(0,0,0,0.25)] backdrop-blur-md";

function CoverChip({
  className,
  title,
  children,
}: {
  className?: string;
  title?: string;
  children: ReactNode;
}) {
  return (
    <span className={cn(coverChip, className)} title={title}>
      {children}
    </span>
  );
}

export function NotebookBookCard({
  notebook: nb,
  onUpdateTitle,
  onTogglePin,
  onToggleShare,
  onReindex,
  onDelete,
  onAddToCollection,
}: {
  notebook: NotebookBookCardData;
  onUpdateTitle: (id: number) => void;
  onTogglePin: (id: number) => void;
  onToggleShare?: (id: number) => void;
  onReindex?: (id: number) => void;
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
        <div className="absolute left-2 top-2 z-[1] flex flex-wrap gap-1">
          {nb.is_pinned ? (
            <CoverChip className="text-amber-100">
              <Pin className="h-2.5 w-2.5 fill-amber-300 text-amber-300" />
              置顶
            </CoverChip>
          ) : null}
          {nb.share_all ? (
            <CoverChip>
              <span
                aria-hidden
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-300"
              />
              公开
            </CoverChip>
          ) : null}
          {nb.index_status === "failed" ? (
            <CoverChip
              className="border-rose-300/30 text-rose-100"
              title={nb.index_error ?? "索引失败"}
            >
              <span
                aria-hidden
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400"
              />
              索引失败
            </CoverChip>
          ) : nb.index_status === "ready" ? (
            <CoverChip>
              <span
                aria-hidden
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-sky-300"
              />
              已索引
            </CoverChip>
          ) : nb.index_status === "indexing" ? (
            <CoverChip className="text-amber-100">
              <span
                aria-hidden
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300"
              />
              索引中
            </CoverChip>
          ) : null}
        </div>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-black/20 to-transparent opacity-0 transition-opacity duration-200 group-hover:opacity-100" />
      </Link>

      <div className="flex items-start gap-1 px-2 pb-2 pt-1.5">
        <Link to={`/notebooks/${nb.id}`} className="min-w-0 flex-1 text-left">
          <h3 className="line-clamp-2 text-xs font-semibold leading-snug tracking-tight text-foreground">
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
            indexStatus={nb.index_status}
            onRequestEdit={onUpdateTitle}
            onAddToCollection={onAddToCollection}
            onTogglePin={onTogglePin}
            onToggleShare={onToggleShare}
            onReindex={onReindex}
            onDelete={onDelete}
          />
        </div>
      </div>
    </article>
  );
}
