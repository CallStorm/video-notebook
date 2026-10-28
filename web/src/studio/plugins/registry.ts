/** Per-plugin Studio result viewers. Add a folder + register here for a new capability. */
export { StudioMindmap as MindMapResultView } from "@/components/studio-mindmap";
export { StudioSlides as SlidesResultView } from "@/components/studio-slides";
export { StudioNotes as StructuredNotesResultView } from "@/components/studio-notes";
export { StudioFile as FileResultView } from "@/components/studio-file";

import type { ComponentType } from "react";
import { StudioMindmap } from "@/components/studio-mindmap";
import { StudioSlides } from "@/components/studio-slides";
import { StudioNotes } from "@/components/studio-notes";
import { StudioFile } from "@/components/studio-file";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyProps = any;

export const STUDIO_RESULT_VIEWS: Record<string, ComponentType<AnyProps>> = {
  mind_map: StudioMindmap,
  slides: StudioSlides,
  structured_notes: StudioNotes,
  file: StudioFile,
};

export function getStudioResultView(formatKey: string): ComponentType<AnyProps> | null {
  return STUDIO_RESULT_VIEWS[formatKey] ?? null;
}

export function isStudioOpenableFormat(formatKey: string): boolean {
  return formatKey in STUDIO_RESULT_VIEWS;
}

export function isTextStudioFormat(formatKey: string): boolean {
  return formatKey === "mind_map" || formatKey === "structured_notes";
}
