export type TagBrief = {
  id: number
  name: string
  color?: string | null
  notebook_count?: number
}

export type NotebookBrief = {
  notebook_id: number
  name: string
  description?: string | null
  cover_url?: string | null
  tags?: TagBrief[]
  source_count?: number
  note_count?: number
  subtitle_ready?: number
  subtitle_total?: number
  created_at?: string
  updated_at?: string
}

export type VideoBrief = {
  video_id?: number
  id?: number
  title?: string
  status?: string
  subtitle_status?: string
  source_url?: string | null
  platform?: string | null
  source_type?: string | null
  mime?: string | null
  duration_ms?: number | null
  overview_text?: string | null
  error_message?: string | null
}

export type SourceItem = {
  notebook_id: number
  video_id: number
  sort?: number
  selected_for_chat?: boolean
  video?: VideoBrief
}

export type Readiness = {
  notebook_id?: number
  ready_for_draft?: boolean
  items?: Array<{
    video_id: number
    title?: string
    status?: string
    subtitle_status?: string
    ready?: boolean
  }>
}

export type NotebookDetail = NotebookBrief & {
  sources?: SourceItem[]
  readiness?: Readiness
}

export type ArtifactItem = {
  task_id?: number
  artifact_id?: number
  format_key?: string
  title?: string
  status?: string
  draft?: { has_content?: boolean }
  note?: string
}

export type DraftConcept = {
  term?: string
  definition?: string
}

export type DraftPoint = {
  id?: string
  text?: string
  time?: string | null
  evidence?: string | null
  example?: string | null
  example_kind?: string | null
  comment?: string | null
  source_hint?: string | null
  video_id?: number | null
  checked?: boolean
}

export type DraftTakeaway = {
  id?: string
  text?: string
  checked?: boolean
}

export type ConclusionCheck = {
  text?: string
  verdict?: 'supported' | 'partial' | 'unsupported' | string
  gap?: string
}

export type DraftContent = {
  theme?: string
  concepts?: DraftConcept[]
  points?: DraftPoint[]
  takeaways?: DraftTakeaway[]
  open_questions?: string[]
}

export type DraftDoc = {
  id?: number
  notebook_id?: number
  strategy_title?: string | null
  status?: string
  language?: string
  conclusion?: string
  conclusions?: string[]
  conclusion_checks?: ConclusionCheck[]
  content?: DraftContent | string
  markdown?: string
  summary?: string
  title?: string
  updated_at?: string
  error_message?: string | null
  source_video_ids?: number[]
  [k: string]: unknown
}

export type DraftPayload = {
  notebook_id: number
  draft: null | DraftDoc
}

export type JobStatus = {
  job_id: number
  task_id?: number
  kind?: string
  status?: string
  error?: string | null
  next_step?: string | null
  format_key?: string
}

export type DownloadVideoPayload = {
  video_id: number
  filename?: string | null
  mime?: string | null
  download_url: string
  expires_at?: string | null
}
