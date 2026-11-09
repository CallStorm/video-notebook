import { useEffect, useMemo, useRef, useState } from 'react'
import { View, Text, Image, Canvas, ScrollView, Video } from '@tarojs/components'
import Taro, { useLoad, useUnload } from '@tarojs/taro'
import {
  downloadVideo,
  generateDraft,
  getDraft,
  getJob,
  getNotebook,
  getReadiness,
  listArtifacts
} from '../../services/agent'
import type {
  ArtifactItem,
  DraftContent,
  DraftDoc,
  DraftPoint,
  NotebookDetail,
  Readiness,
  SourceItem
} from '../../types/agent'
import './index.scss'

const COVER_TONES = ['#D9EEE8', '#E8E4F5', '#F5E6D8', '#E3F0F7', '#F3E8EE', '#EAF3E0']
const VERDICT_LABEL: Record<string, string> = {
  supported: '有依据',
  partial: '部分支持',
  unsupported: '待核实'
}

type Phase = 'empty' | 'generating' | 'ready'

type LearningStep =
  | { key: string; kind: 'theme'; no: number; title: string; body: string }
  | { key: string; kind: 'concepts'; no: number; title: string; items: Array<{ term: string; definition: string }> }
  | { key: string; kind: 'point'; no: number; title: string; point: DraftPoint; index: number }
  | { key: string; kind: 'takeaways'; no: number; title: string; items: string[] }
  | { key: string; kind: 'questions'; no: number; title: string; items: string[] }
  | { key: string; kind: 'conclusions'; no: number; title: string; items: string[]; checks: DraftDoc['conclusion_checks'] }
  | { key: string; kind: 'fallback'; no: number; title: string; body: string }

function coverTone(id: number) {
  return COVER_TONES[Math.abs(id) % COVER_TONES.length]
}

function asContent(draft: DraftDoc | null): DraftContent | null {
  if (!draft) return null
  const c = draft.content
  if (!c) return null
  if (typeof c === 'string') return { theme: c }
  return c
}

function normalizeConclusions(draft: DraftDoc | null): string[] {
  if (!draft) return []
  if (Array.isArray(draft.conclusions) && draft.conclusions.length) {
    return draft.conclusions.map((s) => String(s).trim()).filter(Boolean)
  }
  return String(draft.conclusion || '')
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
}

function youtubeThumb(url?: string | null): string | null {
  if (!url) return null
  const m = String(url).match(
    /(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)([\w-]{6,})/i
  )
  return m ? 'https://i.ytimg.com/vi/' + m[1] + '/hqdefault.jpg' : null
}

function platformLabel(url?: string | null, platform?: string | null): string {
  if (platform) return String(platform)
  const u = String(url || '').toLowerCase()
  if (u.includes('youtube') || u.includes('youtu.be')) return 'YouTube'
  if (u.includes('bilibili') || u.includes('b23.tv')) return 'B站'
  if (u.includes('douyin') || u.includes('tiktok')) return '抖音'
  return '视频'
}

function formatDuration(ms?: number | null): string {
  if (!ms || ms <= 0) return ''
  const total = Math.round(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return m + ':' + String(s).padStart(2, '0')
}

function buildSteps(draft: DraftDoc | null, notebookName?: string): LearningStep[] {
  const content = asContent(draft)
  const steps: LearningStep[] = []
  let no = 1

  if (content?.theme && String(content.theme).trim()) {
    steps.push({
      key: 'theme',
      kind: 'theme',
      no: no++,
      title: '主题',
      body: String(content.theme).trim()
    })
  }

  const concepts = (content?.concepts || [])
    .map((c) => ({
      term: String(c.term || '').trim(),
      definition: String(c.definition || '').trim()
    }))
    .filter((c) => c.term || c.definition)
  if (concepts.length) {
    steps.push({
      key: 'concepts',
      kind: 'concepts',
      no: no++,
      title: '概念',
      items: concepts
    })
  }

  const points = (content?.points || []).filter((p) => String(p.text || '').trim())
  points.forEach((point, index) => {
    steps.push({
      key: 'point-' + (point.id || index),
      kind: 'point',
      no: no++,
      title: '精华要点',
      point,
      index
    })
  })

  const takeaways = (content?.takeaways || [])
    .map((t) => String(t.text || '').trim())
    .filter(Boolean)
  if (takeaways.length) {
    steps.push({
      key: 'takeaways',
      kind: 'takeaways',
      no: no++,
      title: '可执行收获',
      items: takeaways
    })
  }

  const questions = (content?.open_questions || [])
    .map((q) => String(q || '').trim())
    .filter(Boolean)
  if (questions.length) {
    steps.push({
      key: 'questions',
      kind: 'questions',
      no: no++,
      title: '遗留问题',
      items: questions
    })
  }

  const conclusions = normalizeConclusions(draft)
  if (conclusions.length) {
    steps.push({
      key: 'conclusions',
      kind: 'conclusions',
      no: no++,
      title: '结论',
      items: conclusions,
      checks: draft?.conclusion_checks
    })
  }

  if (!steps.length && draft) {
    const flat = flattenDraft(draft, notebookName)
    if (flat) {
      steps.push({
        key: 'fallback',
        kind: 'fallback',
        no: 1,
        title: '底稿',
        body: flat
      })
    }
  }

  return steps
}

function flattenDraft(draft: DraftDoc | null, notebookName?: string): string {
  if (!draft) return ''
  const lines: string[] = []
  const title = String(draft.strategy_title || draft.title || notebookName || '知识底稿')
  lines.push(title)
  lines.push('')
  const content = asContent(draft)
  if (content?.theme) {
    lines.push('主题')
    lines.push(String(content.theme))
    lines.push('')
  }
  if (content?.concepts && content.concepts.length) {
    lines.push('概念')
    content.concepts.forEach((item) => {
      const term = String(item.term || '').trim()
      const def = String(item.definition || '').trim()
      if (term || def) lines.push('· ' + term + (def ? '：' + def : ''))
    })
    lines.push('')
  }
  if (content?.points && content.points.length) {
    lines.push('精华要点')
    content.points.forEach((p, i) => {
      const t = String(p.text || '').trim()
      if (!t) return
      const time = p.time ? ' [' + p.time + ']' : ''
      lines.push(i + 1 + '. ' + t + time)
      const evidence = String(p.evidence || '').trim()
      const example = String(p.example || '').trim()
      if (evidence) lines.push('   原句：' + evidence)
      if (example) lines.push('   例：' + example)
    })
    lines.push('')
  }
  if (content?.takeaways && content.takeaways.length) {
    lines.push('可执行收获')
    content.takeaways.forEach((t) => {
      const text = String(t.text || '').trim()
      if (text) lines.push('· ' + text)
    })
    lines.push('')
  }
  if (content?.open_questions && content.open_questions.length) {
    lines.push('遗留问题')
    content.open_questions.forEach((q) => {
      const text = String(q || '').trim()
      if (text) lines.push('· ' + text)
    })
    lines.push('')
  }
  const conclusions = normalizeConclusions(draft)
  if (conclusions.length) {
    lines.push('结论')
    conclusions.forEach((c) => lines.push('· ' + c))
    lines.push('')
  }
  if (typeof draft.markdown === 'string' && draft.markdown.trim()) {
    lines.push(draft.markdown.trim())
  } else if (typeof draft.summary === 'string' && draft.summary.trim() && lines.length <= 2) {
    lines.push(draft.summary.trim())
  }
  return lines.join('\n').trim()
}

function wrapText(ctx: Taro.CanvasContext, text: string, maxWidth: number): string[] {
  const chars = String(text || '').split('')
  const lines: string[] = []
  let line = ''
  chars.forEach((ch) => {
    const test = line + ch
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line)
      line = ch
    } else {
      line = test
    }
  })
  if (line) lines.push(line)
  return lines.length ? lines : ['']
}

export default function DetailPage() {
  const [id, setId] = useState(0)
  const [nb, setNb] = useState<NotebookDetail | null>(null)
  const [ready, setReady] = useState<Readiness | null>(null)
  const [draft, setDraft] = useState<DraftDoc | null>(null)
  const [phase, setPhase] = useState<Phase>('empty')
  const [busy, setBusy] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [jobId, setJobId] = useState<number | null>(null)
  const [activeVideoId, setActiveVideoId] = useState<number | null>(null)
  const [playUrl, setPlayUrl] = useState<string>('')
  const [playTitle, setPlayTitle] = useState('')
  const [playLoading, setPlayLoading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const aliveRef = useRef(true)

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const applyPhase = (
    nextDraft: DraftDoc | null,
    arts: ArtifactItem[],
    activeJobId?: number | null
  ) => {
    const runningArt = (arts || []).find((a) => {
      const key = String(a.format_key || '')
      const st = String(a.status || '')
      return (
        key === 'knowledge_draft' &&
        (st === 'queued' || st === 'running' || st === 'pending')
      )
    })
    if (activeJobId || runningArt) {
      setPhase('generating')
      return
    }
    if (nextDraft && (nextDraft.status === 'ready' || asContent(nextDraft) || nextDraft.markdown)) {
      setPhase('ready')
      return
    }
    setPhase('empty')
  }

  const refresh = async (notebookId: number, keepJob?: number | null) => {
    try {
      const detail = await getNotebook(notebookId)
      if (!aliveRef.current) return
      setNb(detail)
      setReady(detail.readiness || (await getReadiness(notebookId)))
      const arts = await listArtifacts(notebookId)
      if (!aliveRef.current) return
      const draftRes = await getDraft(notebookId)
      if (!aliveRef.current) return
      const d = draftRes.draft || null
      setDraft(d)
      applyPhase(d, arts.items || [], keepJob)
      Taro.setNavigationBarTitle({ title: detail.name || '笔记详情' })
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '加载失败', icon: 'none' })
    }
  }

  const startPoll = (notebookId: number, jid: number) => {
    stopPoll()
    setJobId(jid)
    setPhase('generating')
    pollRef.current = setInterval(async () => {
      try {
        const job = await getJob(jid)
        const st = String(job.status || '')
        if (st === 'succeeded') {
          stopPoll()
          setJobId(null)
          await refresh(notebookId, null)
          Taro.showToast({ title: '底稿已生成', icon: 'success' })
        } else if (st === 'failed') {
          stopPoll()
          setJobId(null)
          setPhase(draft ? 'ready' : 'empty')
          Taro.showToast({ title: job.error || '生成失败', icon: 'none' })
          await refresh(notebookId, null)
        }
      } catch {
        // keep polling
      }
    }, 2000)
  }

  useLoad((query) => {
    const notebookId = Number(query.id || 0)
    setId(notebookId)
    if (notebookId) refresh(notebookId)
  })

  useUnload(() => {
    aliveRef.current = false
    stopPoll()
  })

  useEffect(() => {
    return () => {
      aliveRef.current = false
      stopPoll()
    }
  }, [])

  const onGenerate = async () => {
    if (!id || busy || phase === 'generating') return
    setBusy(true)
    try {
      const job = await generateDraft(id)
      const jid = Number(job.job_id)
      Taro.showToast({ title: '已开始生成', icon: 'none' })
      startPoll(id, jid)
      await refresh(id, jid)
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '触发失败', icon: 'none' })
    } finally {
      setBusy(false)
    }
  }

  const ensureAlbumAuth = async () => {
    try {
      await Taro.authorize({ scope: 'scope.writePhotosAlbum' })
      return true
    } catch {
      const modal = await Taro.showModal({
        title: '需要相册权限',
        content: '下载底稿图片需要写入相册权限，请在设置中开启。',
        confirmText: '去设置'
      })
      if (modal.confirm) {
        await Taro.openSetting()
      }
      return false
    }
  }

  const onDownload = async () => {
    if (phase !== 'ready' || !draft || downloading) return
    const body = flattenDraft(draft, nb?.name)
    if (!body) {
      Taro.showToast({ title: '暂无底稿内容', icon: 'none' })
      return
    }
    setDownloading(true)
    try {
      const ok = await ensureAlbumAuth()
      if (!ok) return

      const sys = Taro.getSystemInfoSync()
      const dpr = Math.min(sys.pixelRatio || 2, 3)
      const width = 750
      const padding = 40
      const maxWidth = width - padding * 2
      const lineHeight = 36
      const titleSize = 28
      const bodySize = 22

      const ctx = Taro.createCanvasContext('draftCanvas')
      ctx.setFontSize(bodySize)
      const allLines: Array<{ text: string; size: number; bold?: boolean }> = []
      const rawLines = body.split('\n')
      rawLines.forEach((raw, idx) => {
        const isTitle = idx === 0
        const size = isTitle ? titleSize : bodySize
        ctx.setFontSize(size)
        if (!raw) {
          allLines.push({ text: '', size })
          return
        }
        wrapText(ctx, raw, maxWidth).forEach((ln) => {
          allLines.push({ text: ln, size, bold: isTitle })
        })
      })

      const maxCanvasH = 4000
      let height = padding * 2 + allLines.length * lineHeight + 40
      if (height > maxCanvasH) height = maxCanvasH

      ctx.setFillStyle('#ffffff')
      ctx.fillRect(0, 0, width, height)
      ctx.setFillStyle('#0f766e')
      ctx.fillRect(0, 0, width, 8)
      let y = padding + 24
      for (let i = 0; i < allLines.length; i++) {
        if (y + lineHeight > height - padding) {
          ctx.setFillStyle('#64748b')
          ctx.setFontSize(20)
          ctx.fillText('……（内容过长已截断）', padding, y)
          break
        }
        const row = allLines[i]
        ctx.setFillStyle(row.bold ? '#0f172a' : '#334155')
        ctx.setFontSize(row.size)
        if (row.text) ctx.fillText(row.text, padding, y)
        y += lineHeight
      }
      ctx.setFillStyle('#94a3b8')
      ctx.setFontSize(18)
      ctx.fillText('影知 · 知识底稿', padding, height - 18)

      await new Promise<void>((resolve) => {
        ctx.draw(false, () => resolve())
      })
      await new Promise((r) => setTimeout(r, 80))

      const temp = await Taro.canvasToTempFilePath({
        canvasId: 'draftCanvas',
        destWidth: width * dpr,
        destHeight: height * dpr,
        fileType: 'png'
      })
      await Taro.saveImageToPhotosAlbum({ filePath: temp.tempFilePath })
      Taro.showToast({ title: '已保存到相册', icon: 'success' })
    } catch (e: any) {
      Taro.showToast({ title: e?.errMsg || e?.message || '下载失败', icon: 'none' })
    } finally {
      setDownloading(false)
    }
  }

  const openExternal = async (url: string) => {
    try {
      await Taro.setClipboardData({ data: url })
      Taro.showModal({
        title: '已复制视频链接',
        content: '当前环境无法内嵌播放该来源，链接已复制，可到浏览器打开观看。',
        showCancel: false
      })
    } catch {
      Taro.showToast({ title: '无法打开该视频', icon: 'none' })
    }
  }

  const onWatch = async (source: SourceItem) => {
    const videoId = Number(source.video_id || source.video?.video_id || source.video?.id || 0)
    const title = source.video?.title || '视频 #' + videoId
    const sourceUrl = source.video?.source_url || ''
    if (!videoId) {
      if (sourceUrl) await openExternal(sourceUrl)
      return
    }

    if (activeVideoId === videoId && playUrl) {
      setActiveVideoId(null)
      setPlayUrl('')
      setPlayTitle('')
      return
    }

    setActiveVideoId(videoId)
    setPlayTitle(title)
    setPlayUrl('')
    setPlayLoading(true)
    try {
      const res = await downloadVideo(videoId)
      if (!aliveRef.current) return
      if (res?.download_url) {
        setPlayUrl(res.download_url)
        return
      }
      throw new Error('暂无播放地址')
    } catch (e: any) {
      setActiveVideoId(null)
      setPlayUrl('')
      if (sourceUrl) {
        await openExternal(sourceUrl)
      } else {
        Taro.showToast({ title: e?.message || '暂不可播放', icon: 'none' })
      }
    } finally {
      setPlayLoading(false)
    }
  }

  const sources: SourceItem[] = nb?.sources || []
  const steps = useMemo(() => buildSteps(draft, nb?.name), [draft, nb?.name])
  const primaryLabel =
    phase === 'generating' ? '生成中' : phase === 'ready' ? '重新生成底稿' : '生成底稿'
  const downloadDisabled = phase !== 'ready' || downloading
  const genDisabled = busy || phase === 'generating'

  return (
    <View className='page detail-page'>
      <ScrollView scrollY className='detail-scroll' showScrollbar={false}>
        <View className='hero' style={{ backgroundColor: coverTone(id || 1) }}>
          {nb?.cover_url ? (
            <Image className='hero-img' src={nb.cover_url} mode='aspectFill' />
          ) : (
            <View className='hero-fallback'>
              <Text className='hero-letter'>{(nb?.name || 'N').slice(0, 1)}</Text>
            </View>
          )}
          <View className='hero-mask'>
            <Text className='hero-title'>{nb?.name || '加载中…'}</Text>
            {nb?.description ? (
              <Text className='hero-desc'>{nb.description}</Text>
            ) : (
              <Text className='hero-desc'>
                {ready?.ready_for_draft ? '来源已就绪，可生成底稿' : '抓取/字幕未齐时也可查看来源'}
              </Text>
            )}
          </View>
        </View>

        <View className='sticky-strip'>
          <View className='sticky-head'>
            <Text className='sticky-title'>相关视频</Text>
            <Text className='muted'>{sources.length} 个 · 点封面观看</Text>
          </View>

          {activeVideoId ? (
            <View className='player-box'>
              {playLoading && !playUrl ? (
                <View className='player-loading'>
                  <View className='pulse-ring compact'>
                    <View className='pulse-dot d1' />
                    <View className='pulse-dot d2' />
                    <View className='pulse-dot d3' />
                  </View>
                  <Text className='muted'>正在获取播放地址…</Text>
                </View>
              ) : playUrl ? (
                <Video
                  className='player-video'
                  src={playUrl}
                  title={playTitle}
                  controls
                  autoplay
                  showCenterPlayBtn
                  enableProgressGesture
                  objectFit='contain'
                  onError={() => {
                    Taro.showToast({ title: '播放失败，请稍后重试', icon: 'none' })
                  }}
                />
              ) : null}
              <View className='player-meta'>
                <Text className='player-title'>{playTitle}</Text>
                <Text
                  className='player-close'
                  onClick={() => {
                    setActiveVideoId(null)
                    setPlayUrl('')
                    setPlayTitle('')
                  }}
                >
                  收起
                </Text>
              </View>
            </View>
          ) : null}

          {sources.length === 0 ? (
            <Text className='muted pad'>暂无来源，去收集页添加</Text>
          ) : (
            <ScrollView scrollX className='source-row' showScrollbar={false}>
              {sources.map((s) => {
                const thumb = youtubeThumb(s.video?.source_url)
                const active = activeVideoId === s.video_id
                const dur = formatDuration(s.video?.duration_ms)
                const plat = platformLabel(s.video?.source_url, s.video?.platform)
                return (
                  <View
                    className={'source-card' + (active ? ' active' : '')}
                    key={s.video_id}
                    onClick={() => onWatch(s)}
                  >
                    <View
                      className='source-thumb'
                      style={{ backgroundColor: coverTone(s.video_id) }}
                    >
                      {thumb ? (
                        <Image className='source-thumb-img' src={thumb} mode='aspectFill' />
                      ) : (
                        <Text className='source-thumb-t'>
                          {(s.video?.title || plat || '视').slice(0, 1)}
                        </Text>
                      )}
                      <View className='play-badge'>
                        <Text className='play-badge-t'>{active ? '||' : '▶'}</Text>
                      </View>
                      {dur ? <Text className='dur-chip'>{dur}</Text> : null}
                    </View>
                    <Text className='source-title'>{s.video?.title || '视频 #' + s.video_id}</Text>
                    <Text className='source-meta'>
                      {plat} · {s.video?.status || '-'}
                    </Text>
                  </View>
                )
              })}
            </ScrollView>
          )}
        </View>

        <View className='section draft-section'>
          <View className='section-head'>
            <Text className='section-title'>学习步骤</Text>
            {draft?.updated_at ? (
              <Text className='muted'>
                更新于 {String(draft.updated_at).slice(0, 16).replace('T', ' ')}
              </Text>
            ) : null}
          </View>

          {phase === 'empty' ? (
            <View className='empty-draft'>
              <View className='pulse-ring'>
                <View className='pulse-dot d1' />
                <View className='pulse-dot d2' />
                <View className='pulse-dot d3' />
              </View>
              <View className='skel'>
                <View className='skel-line w80' />
                <View className='skel-line w60' />
                <View className='skel-line w70' />
              </View>
              <Text className='empty-title'>还没有底稿</Text>
              <Text className='muted'>点下方「生成底稿」，整理成可学习的步骤</Text>
            </View>
          ) : null}

          {phase === 'generating' ? (
            <View className='gen-box'>
              <View className='gen-banner'>
                <Text className='gen-title'>底稿生成中…</Text>
                <Text className='muted'>请稍候，完成后会自动展示学习步骤</Text>
                <View className='progress'>
                  <View className='progress-bar' />
                </View>
              </View>
              <View className='skel'>
                <View className='skel-line w90' />
                <View className='skel-line w75' />
                <View className='skel-line w85' />
                <View className='skel-line w55' />
              </View>
              {steps.length ? (
                <View className='steps faded'>
                  {steps.slice(0, 2).map((step) => (
                    <View className='step-card' key={step.key}>
                      <View className='step-no'>
                        <Text className='step-no-t'>{String(step.no).padStart(2, '0')}</Text>
                      </View>
                      <View className='step-main'>
                        <Text className='step-label'>{step.title}</Text>
                      </View>
                    </View>
                  ))}
                </View>
              ) : null}
            </View>
          ) : null}

          {phase === 'ready' ? (
            <View className='steps'>
              {steps.map((step) => (
                <View className='step-card' key={step.key}>
                  <View className='step-no'>
                    <Text className='step-no-t'>{String(step.no).padStart(2, '0')}</Text>
                  </View>
                  <View className='step-main'>
                    <Text className='step-label'>{step.title}</Text>

                    {step.kind === 'theme' || step.kind === 'fallback' ? (
                      <Text className='step-body'>{step.body}</Text>
                    ) : null}

                    {step.kind === 'concepts' ? (
                      <View className='concept-list'>
                        {step.items.map((c, i) => (
                          <View className='concept-card' key={'c' + i}>
                            <Text className='concept-term'>{c.term || '概念'}</Text>
                            {c.definition ? (
                              <Text className='concept-def'>{c.definition}</Text>
                            ) : null}
                          </View>
                        ))}
                      </View>
                    ) : null}

                    {step.kind === 'point' ? (
                      <View className='point-block'>
                        <Text className='step-body strong'>{String(step.point.text || '')}</Text>
                        {String(step.point.evidence || '').trim() ? (
                          <View className='chip-row'>
                            <Text className='chip teal'>原句</Text>
                            <Text className='chip-text'>{String(step.point.evidence).trim()}</Text>
                          </View>
                        ) : null}
                        {String(step.point.example || '').trim() ? (
                          <View className='chip-row'>
                            <Text className='chip amber'>例</Text>
                            <Text className='chip-text'>{String(step.point.example).trim()}</Text>
                          </View>
                        ) : (
                          <Text className='hint'>例 · 暂无例子，重新生成后会出现</Text>
                        )}
                        {String(step.point.comment || '').trim() ? (
                          <View className='chip-row'>
                            <Text className='chip gray'>评</Text>
                            <Text className='chip-text'>{String(step.point.comment).trim()}</Text>
                          </View>
                        ) : null}
                        {step.point.time ? (
                          <Text className='time-chip'>⏱ {step.point.time}</Text>
                        ) : null}
                      </View>
                    ) : null}

                    {step.kind === 'takeaways' || step.kind === 'questions' ? (
                      <View className='bullet-list'>
                        {step.items.map((item, i) => (
                          <Text className='bullet-item' key={step.kind + i}>
                            · {item}
                          </Text>
                        ))}
                      </View>
                    ) : null}

                    {step.kind === 'conclusions' ? (
                      <View className='bullet-list'>
                        {step.items.map((item, i) => {
                          const check = (step.checks || []).find(
                            (c) => String(c.text || '').trim() === item
                          )
                          const verdict = check?.verdict ? VERDICT_LABEL[check.verdict] || check.verdict : ''
                          return (
                            <View className='conclusion-row' key={'con' + i}>
                              <Text className='bullet-item'>· {item}</Text>
                              {verdict ? <Text className='verdict'>{verdict}</Text> : null}
                            </View>
                          )
                        })}
                      </View>
                    ) : null}
                  </View>
                </View>
              ))}
              {!steps.length ? <Text className='muted'>（底稿为空）</Text> : null}
            </View>
          ) : null}
        </View>

        <View className='bottom-spacer' />
      </ScrollView>

      <View className='bottom-bar'>
        <View
          className={'bar-btn primary' + (genDisabled ? ' disabled' : '')}
          onClick={onGenerate}
        >
          <Text className='bar-btn-text'>{primaryLabel}</Text>
        </View>
        <View
          className={'bar-btn secondary' + (downloadDisabled ? ' disabled' : '')}
          onClick={onDownload}
        >
          <Text className='bar-btn-text'>{downloading ? '导出中' : '下载'}</Text>
        </View>
      </View>

      <Canvas
        canvasId='draftCanvas'
        className='off-canvas'
        style={{ width: '750px', height: '4000px' }}
      />
    </View>
  )
}
