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
  source_count: number;
  note_count?: number;
  updated_at: string | null;
}

function formatDate(iso: string | null): string {
  return formatDateZh(iso);
}

function formatSources(n: number): string {
  return n === 1 ? "1 个来源" : `${n} 个来源`;
}

function coverMeta(nb: NotebookBookCardData): string {
  const parts = [formatDate(nb.updated_at), formatSources(nb.source_count)];
  if ((nb.note_count ?? 0) > 0) parts.push(`${nb.note_count} 笔记`);
  return parts.join(" · ");
}

export function NotebookBookCard({
  notebook: nb,
  onUpdateTitle,
  onTogglePin,
  onDelete,
  onAddToCollection,
}: {
  notebook: NotebookBookCardData;
  onUpdateTitle: (id: number) => void;
  onTogglePin: (id: number) => void;
  onDelete: (id: number) => void;
  onAddToCollection?: (id: number) => void;
}) {
  const remote = isRemoteCover(nb.cover_url);
  const meta = coverMeta(nb);

  return (
    <div className="book-stage group">
      <div className="book-3d">
        <div className="book-pages" aria-hidden />
        <div className="book-spine-edge" aria-hidden />

        <div className="book-front">
          <Link
            to={`/notebooks/${nb.id}`}
            className="book-cover-link"
            aria-label={nb.title}
          >
            {remote ? (
              <>
                <img
                  src={nb.cover_url!}
                  alt=""
                  className="h-full w-full object-cover"
                />
                <div className="book-cover-overlay">
                  <h3 className="line-clamp-3 text-[13px] font-semibold leading-snug text-white">
                    {nb.title}
                  </h3>
                  <p className="mt-1.5 text-[10px] text-white/75">{meta}</p>
                </div>
              </>
            ) : (
              <GeneratedCover
                title={nb.title}
                coverUrl={nb.cover_url}
                variant={nb.id}
                meta={meta}
                className="h-full w-full"
              />
            )}
            {nb.is_pinned ? (
              <span className="absolute left-2 top-2 z-[1] inline-flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-medium text-amber-700 shadow-sm backdrop-blur-sm">
                <Pin className="h-3 w-3 fill-amber-500 text-amber-500" />
                置顶
              </span>
            ) : null}
          </Link>

          <div
            className="absolute right-1.5 top-1.5 z-10 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"
            onClick={(e) => e.stopPropagation()}
          >
            <NotebookCardMenu
              notebookId={nb.id}
              isPinned={nb.is_pinned}
              onRequestEdit={onUpdateTitle}
              onAddToCollection={onAddToCollection}
              onTogglePin={onTogglePin}
              onDelete={onDelete}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
