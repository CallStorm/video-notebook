import { callTool, listTools } from './request'
import type {
  ArtifactItem,
  DownloadVideoPayload,
  DraftPayload,
  JobStatus,
  NotebookBrief,
  NotebookDetail,
  Readiness,
  TagBrief
} from '../types/agent'

export async function testConnection() {
  try {
    const tools = await listTools()
    return { ok: true as const, via: 'GET /agent/v1/tools', tools: tools.tools?.length || 0 }
  } catch {
    const listed = await callTool<{ total: number }>('list_notebooks', { page: 1, size: 1 })
    return { ok: true as const, via: 'list_notebooks', tools: listed.total }
  }
}

export function listTags() {
  return callTool<{ items: TagBrief[] }>('list_tags', {})
}

export function listNotebooks(
  opts: string | { search?: string; tagId?: number | null } = {}
) {
  const normalized =
    typeof opts === 'string' ? { search: opts, tagId: null as number | null } : opts
  return callTool<{ items: NotebookBrief[]; total: number }>('list_notebooks', {
    page: 1,
    size: 50,
    search: normalized.search || undefined,
    tag_id: normalized.tagId || undefined
  })
}

export function createNotebook(name: string, description?: string) {
  return callTool<NotebookBrief>('create_notebook', { name, description })
}

export function getNotebook(notebook_id: number) {
  return callTool<NotebookDetail>('get_notebook', { notebook_id })
}

export function addUrl(notebook_id: number, url: string) {
  return callTool<{ video: any }>('add_url', { notebook_id, url })
}

export function getReadiness(notebook_id: number) {
  return callTool<Readiness>('get_readiness', { notebook_id })
}

export function generateDraft(notebook_id: number, focus?: string) {
  return callTool<{ job_id: number; status: string }>('generate_draft', {
    notebook_id,
    focus: focus || undefined
  })
}

export function getDraft(notebook_id: number) {
  return callTool<DraftPayload>('get_draft', { notebook_id })
}

export function listArtifacts(notebook_id: number) {
  return callTool<{ items: ArtifactItem[] }>('list_artifacts', { notebook_id })
}

export function getJob(job_id: number) {
  return callTool<JobStatus>('get_job', { job_id })
}

export function downloadVideo(video_id: number) {
  return callTool<DownloadVideoPayload>('download_video', { video_id })
}

export function deleteNotebook(notebook_id: number) {
  return callTool<{ ok: boolean; notebook_id: number }>('delete_notebook', { notebook_id })
}

export function autoTagNotebook(notebook_id: number, hint?: string) {
  return callTool<{ notebook_id: number; tag_ids: number[]; tags: TagBrief[] }>('auto_tag_notebook', {
    notebook_id,
    hint: hint || undefined
  })
}

export function autoOrganizeTags() {
  return callTool<{
    applied: boolean
    message?: string | null
    notebook_count?: number
    tags: TagBrief[]
  }>('auto_organize_tags', {})
}
