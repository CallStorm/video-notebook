/** Per-plugin Studio result viewers. Add a folder + register here for a new capability. */
export { StudioMindmap as MindMapResultView } from "@/components/studio-mindmap";
export { StudioSlides as SlidesResultView } from "@/components/studio-slides";
export { StudioFile as FileResultView } from "@/components/studio-file";

import type { ComponentType } from "react";
import { StudioMindmap } from "@/components/studio-mindmap";
import { StudioSlides } from "@/components/studio-slides";
import { StudioFile } from "@/components/studio-file";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyProps = any;

/** Formats retired from Studio product surface (kept out of create/open UI). */
export const HIDDEN_STUDIO_FORMATS = new Set<string>(["structured_notes"]);

export function isStudioFormatVisible(formatKey: string): boolean {
  return !HIDDEN_STUDIO_FORMATS.has(formatKey);
}

export const STUDIO_RESULT_VIEWS: Record<string, ComponentType<AnyProps>> = {
  mind_map: StudioMindmap,
  slides: StudioSlides,
  file: StudioFile,
};

export function getStudioResultView(formatKey: string): ComponentType<AnyProps> | null {
  if (!isStudioFormatVisible(formatKey)) return null;
  return STUDIO_RESULT_VIEWS[formatKey] ?? null;
}

export function isStudioOpenableFormat(formatKey: string): boolean {
  return isStudioFormatVisible(formatKey) && formatKey in STUDIO_RESULT_VIEWS;
}

export function isTextStudioFormat(formatKey: string): boolean {
  return formatKey === "mind_map";
}
