import { parseClockToSeconds } from "@/components/studio-notes";

export type DiagramKind = "flow" | "compare" | "sequence";
export type CalloutTone = "note" | "warn";
export type CompareTone = "plain" | "contrast";

export interface ReadingStep {
  title?: string;
  body: string;
  time?: string;
  videoId?: number;
  quote?: string;
  aside?: string;
}

export interface ReadingNode {
  label: string;
  detail?: string;
}

export interface SequenceCell {
  lane: string;
  text: string;
}

export interface SequenceRow {
  label: string;
  cells: SequenceCell[];
}

export interface ReadingDiagram {
  kind: DiagramKind;
  caption?: string;
  nodes: ReadingNode[];
  columns?: [string, string];
  tone?: CompareTone;
  lanes?: string[];
  rows?: SequenceRow[];
  rowHeader?: string;
}

export interface ReadingCallout {
  tone: CalloutTone;
  label?: string;
  body: string;
}

export interface ReadingCard {
  title: string;
  body: string;
}

export interface ReadingSection {
  id: string;
  title: string;
  summary?: string;
  prose: string[];
  steps: ReadingStep[];
  diagram?: ReadingDiagram;
  cards: ReadingCard[];
  callout?: ReadingCallout;
}

export interface ReadingPageData {
  title?: string;
  kicker?: string;
  theme: string;
  lede?: string;
  sections: ReadingSection[];
  closing?: string;
}

function textOf(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const text = value.trim();
  return text || undefined;
}

function videoIdOf(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) return value;
  if (typeof value === "string" && /^\d+$/.test(value.trim())) {
    const id = Number(value.trim());
    return id > 0 ? id : undefined;
  }
  return undefined;
}

function clockOf(value: unknown): string | undefined {
  const text = textOf(value);
  if (!text || parseClockToSeconds(text) == null) return undefined;
  return text;
}

function sectionId(value: unknown, index: number): string {
  const text = textOf(value);
  if (text && /^[A-Za-z][\w-]{0,40}$/.test(text)) return text;
  return `section-${index + 1}`;
}

function parseProse(value: unknown): string[] {
  if (typeof value === "string") {
    const text = value.trim();
    return text ? [text] : [];
  }
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => item.length > 0)
    .slice(0, 3);
}

function parseNodes(value: unknown): ReadingNode[] {
  if (!Array.isArray(value)) return [];
  const nodes: ReadingNode[] = [];
  for (const item of value) {
    if (typeof item === "string") {
      const label = item.trim();
      if (label) nodes.push({ label });
      continue;
    }
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const label = textOf(row.label);
    if (!label) continue;
    nodes.push({ label, detail: textOf(row.detail) });
  }
  return nodes.slice(0, 6);
}

function parseColumns(value: unknown): [string, string] | undefined {
  if (!Array.isArray(value) || value.length !== 2) return undefined;
  const left = textOf(value[0]);
  const right = textOf(value[1]);
  if (!left || !right) return undefined;
  return [left, right];
}

function parseLanes(value: unknown): string[] | undefined {
  if (!Array.isArray(value) || value.length < 2 || value.length > 4) return undefined;
  const lanes: string[] = [];
  for (const item of value) {
    const text = textOf(item);
    if (!text || text.length > 12 || lanes.includes(text)) return undefined;
    lanes.push(text);
  }
  return lanes;
}

function parseSequenceRows(value: unknown, lanes: string[]): SequenceRow[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const known = new Set(lanes);
  const rows: SequenceRow[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const label = textOf(row.label);
    if (!label || !Array.isArray(row.cells)) continue;
    const cells: SequenceCell[] = [];
    const seen = new Set<string>();
    for (const cell of row.cells) {
      if (!cell || typeof cell !== "object") continue;
      const record = cell as Record<string, unknown>;
      const lane = textOf(record.lane);
      const text = textOf(record.text);
      if (!lane || !text || !known.has(lane) || seen.has(lane)) continue;
      seen.add(lane);
      cells.push({ lane, text });
    }
    if (cells.length === 0) continue;
    rows.push({ label, cells });
    if (rows.length === 6) break;
  }
  return rows.length >= 2 ? rows : undefined;
}

function parseDiagram(value: unknown): ReadingDiagram | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const kind: DiagramKind =
    row.kind === "compare" || row.kind === "sequence" || row.kind === "flow" ? row.kind : "flow";
  const nodes = parseNodes(row.nodes);
  const caption = textOf(row.caption);
  if (kind === "sequence") {
    const lanes = parseLanes(row.lanes);
    const rows = lanes ? parseSequenceRows(row.rows, lanes) : undefined;
    if (lanes && rows) {
      const rowHeader = textOf(row.row_header);
      return {
        kind,
        caption,
        nodes,
        lanes,
        rows,
        rowHeader: rowHeader && rowHeader.length <= 8 ? rowHeader : undefined,
      };
    }
  }
  if (nodes.length < 2) return undefined;
  const diagram: ReadingDiagram = { kind, caption, nodes };
  if (kind === "compare") {
    const columns = parseColumns(row.columns);
    if (columns) diagram.columns = columns;
    if (row.tone === "contrast" || row.tone === "plain") diagram.tone = row.tone;
  }
  return diagram;
}

function parseCallout(value: unknown): ReadingCallout | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const row = value as Record<string, unknown>;
  const body = textOf(row.body);
  if (!body) return undefined;
  const tone: CalloutTone = row.tone === "warn" ? "warn" : "note";
  const label = textOf(row.label);
  return { tone, label: label && label.length <= 8 ? label : undefined, body };
}

function parseCards(value: unknown): ReadingCard[] {
  if (!Array.isArray(value)) return [];
  const cards: ReadingCard[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const title = textOf(row.title);
    const body = textOf(row.body);
    if (!title || !body) continue;
    cards.push({ title, body });
    if (cards.length === 6) break;
  }
  return cards;
}

function parseStep(value: unknown): ReadingStep | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const body = textOf(row.body);
  const title = textOf(row.title);
  if (!body && !title) return null;
  return {
    title,
    body: body || title || "",
    time: clockOf(row.time),
    videoId: videoIdOf(row.video_id),
    quote: textOf(row.quote),
    aside: textOf(row.aside),
  };
}

function parseSections(value: unknown): ReadingSection[] {
  if (!Array.isArray(value)) return [];
  const sections: ReadingSection[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const title = textOf(row.title);
    if (!title) continue;
    const steps = Array.isArray(row.steps)
      ? row.steps.map(parseStep).filter((step): step is ReadingStep => step != null)
      : [];
    const prose = parseProse(row.prose);
    const diagram = parseDiagram(row.diagram);
    const cards = parseCards(row.cards);
    const callout = parseCallout(row.callout);
    if (steps.length === 0 && prose.length === 0 && !diagram && cards.length === 0 && !callout) continue;
    const id = sectionId(row.id, sections.length);
    sections.push({
      id: sections.some((section) => section.id === id) ? `section-${sections.length + 1}` : id,
      title,
      summary: textOf(row.summary),
      prose,
      steps,
      diagram,
      cards,
      callout,
    });
  }
  return sections;
}

export function parseReadingPage(text: string | null): ReadingPageData | null {
  if (!text) return null;
  const trimmed = text.trim().replace(/^\uFEFF/, "");
  if (!trimmed.startsWith("{")) return null;
  try {
    const data = JSON.parse(trimmed) as unknown;
    if (!data || typeof data !== "object" || Array.isArray(data)) return null;
    const row = data as Record<string, unknown>;
    const sections = parseSections(row.sections);
    if (sections.length === 0) return null;
    return {
      title: textOf(row.title),
      kicker: textOf(row.kicker),
      theme: textOf(row.theme) || "",
      lede: textOf(row.lede),
      sections,
      closing: textOf(row.closing),
    };
  } catch {
    return null;
  }
}
