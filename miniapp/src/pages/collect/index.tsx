import { useMemo, useState } from 'react'
import { View, Text, Textarea, Input, ScrollView } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { hasConfig } from '../../store/config'
import { addUrl, autoTagNotebook, createNotebook, listNotebooks } from '../../services/agent'
import { extractUrl } from '../../utils/url'
import type { NotebookBrief } from '../../types/agent'
import './index.scss'

const RECENT_COUNT = 3

function autoNotebookName(paste: string, url: string) {
  const line = (paste || '')
    .split(/\r?\n/)
    .map((s) => s.trim())
    .find((s) => s && !/^https?:\/\//i.test(s) && s.length > 1)
  if (line) {
    return line.length > 24 ? line.slice(0, 24) + '…' : line
  }
  try {
    const host = (url.match(/^https?:\/\/([^/?#]+)/i) || [])[1] || ''
    if (host) return '收集 · ' + host.replace(/^www\./, '')
  } catch (_) {
    /* ignore */
  }
  const d = new Date()
  const pad = (n: number) => (n < 10 ? '0' + n : String(n))
  return (
    '新收集 ' +
    pad(d.getMonth() + 1) +
    '-' +
    pad(d.getDate()) +
    ' ' +
    pad(d.getHours()) +
    ':' +
    pad(d.getMinutes())
  )
}

export default function CollectPage() {
  const [paste, setPaste] = useState('')
  const [url, setUrl] = useState<string | null>(null)
  const [notebooks, setNotebooks] = useState<NotebookBrief[]>([])
  const [newName, setNewName] = useState('')
  const [sheetOpen, setSheetOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQ, setSearchQ] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const ensure = async () => {
    if (!hasConfig()) {
      Taro.navigateTo({ url: '/pages/connect/index' })
      return
    }
    try {
      const data = await listNotebooks()
      setNotebooks(data.items || [])
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '加载失败', icon: 'none' })
    }
  }

  useDidShow(() => {
    ensure()
  })

  const recent = useMemo(
    () => notebooks.slice(0, RECENT_COUNT),
    [notebooks]
  )

  const filtered = useMemo(() => {
    const q = searchQ.trim().toLowerCase()
    if (!q) return notebooks
    return notebooks.filter((nb) =>
      (nb.name || '').toLowerCase().includes(q)
    )
  }, [notebooks, searchQ])

  const resolvedUrl = () => url || extractUrl(paste)

  const openSheet = () => {
    const found = resolvedUrl()
    if (!found) {
      Taro.showToast({ title: '请先粘贴含链接的文案', icon: 'none' })
      return
    }
    setUrl(found)
    setSearchOpen(false)
    setSearchQ('')
    setSheetOpen(true)
  }

  const closeSheet = () => {
    if (submitting) return
    setSheetOpen(false)
  }

  const finishCollect = async (notebookId: number) => {
    const found = resolvedUrl()
    if (!found) {
      Taro.showToast({ title: '请先粘贴含链接的文案', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      await addUrl(notebookId, found)
      Taro.showToast({ title: '已加入收集', icon: 'success' })
      setPaste('')
      setUrl(null)
      setNewName('')
      setSheetOpen(false)
      setSearchOpen(false)
      setSearchQ('')
      setTimeout(() => {
        Taro.navigateTo({ url: '/pages/detail/index?id=' + notebookId })
      }, 400)
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '提交失败', icon: 'none' })
    } finally {
      setSubmitting(false)
    }
  }

  const onCreateAndCollect = async () => {
    const found = resolvedUrl()
    if (!found) {
      Taro.showToast({ title: '请先粘贴含链接的文案', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      const name = newName.trim() || autoNotebookName(paste, found)
      const created = await createNotebook(name)
      try {
        await autoTagNotebook(created.notebook_id, paste || found)
      } catch (_) {
        /* 自动归类失败不阻断收集 */
      }
      await addUrl(created.notebook_id, found)
      Taro.showToast({ title: '已新建并收集', icon: 'success' })
      setPaste('')
      setUrl(null)
      setNewName('')
      setSheetOpen(false)
      setSearchOpen(false)
      setSearchQ('')
      try {
        const data = await listNotebooks()
        setNotebooks(data.items || [])
      } catch (_) {
        /* ignore refresh errors */
      }
      setTimeout(() => {
        Taro.navigateTo({ url: '/pages/detail/index?id=' + created.notebook_id })
      }, 400)
    } catch (e: any) {
      Taro.showToast({ title: e?.message || '提交失败', icon: 'none' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <View className='page collect-page'>
      <View className='card paste-card'>
        <View className='section-title'>粘贴分享文案</View>
        <Text className='muted'>从抖音等复制分享内容，自动抽取链接。</Text>
        <Textarea
          className='input paste-area'
          value={paste}
          maxlength={2000}
          placeholder='粘贴包含 https:// 的分享文案'
          onInput={(e) => {
            const v = e.detail.value
            setPaste(v)
            setUrl(extractUrl(v))
          }}
        />
        {url ? (
          <View className='picked'>
            <Text className='picked-label'>已识别链接</Text>
            <Text className='picked-url'>{url}</Text>
          </View>
        ) : (
          <Text className='hint-empty'>粘贴后将自动识别链接</Text>
        )}
      </View>

      <View
        className={'btn-primary collect-cta' + (submitting ? ' disabled' : '')}
        onClick={openSheet}
      >
        收集
      </View>
      <Text className='muted cta-hint'>点收集后选择新建或加入已有笔记本</Text>

      {sheetOpen ? (
        <View className='collect-overlay'>
          <View className='collect-mask' catchMove onClick={closeSheet} />
          <View className='collect-sheet' catchMove>
            <View className='sheet-handle' />
            <Text className='sheet-title'>归档到</Text>

            <View className='sheet-block create-block'>
              <View className='block-head'>
                <Text className='block-title'>新建笔记本</Text>
                <Text className='block-badge'>推荐</Text>
              </View>
              <Input
                className='input sheet-input'
                value={newName}
                placeholder='名称可选，留空则自动命名'
                maxlength={40}
                onInput={(e) => setNewName(e.detail.value)}
              />
              <View
                className={
                  'btn-primary sheet-create-btn' + (submitting ? ' disabled' : '')
                }
                onClick={onCreateAndCollect}
              >
                {submitting ? '提交中…' : '新建并收集'}
              </View>
            </View>

            {recent.length > 0 ? (
              <View className='sheet-block'>
                <Text className='block-title'>最近</Text>
                <View className='nb-list'>
                  {recent.map((nb) => (
                    <View
                      key={nb.notebook_id}
                      className={
                        'nb-row' + (submitting ? ' disabled' : '')
                      }
                      onClick={() => finishCollect(nb.notebook_id)}
                    >
                      <View className='nb-avatar'>
                        <Text className='nb-avatar-text'>
                          {(nb.name || 'N').slice(0, 1)}
                        </Text>
                      </View>
                      <View className='nb-meta'>
                        <Text className='nb-name'>{nb.name}</Text>
                        {nb.description ? (
                          <Text className='nb-desc'>{nb.description}</Text>
                        ) : (
                          <Text className='nb-desc'>
                            {nb.source_count != null
                              ? nb.source_count + ' 个来源'
                              : '加入此笔记本'}
                          </Text>
                        )}
                      </View>
                      <Text className='nb-go'>加入</Text>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}

            <View className='sheet-block search-block'>
              <View
                className='search-toggle'
                onClick={() => setSearchOpen((v) => !v)}
              >
                <Text className='block-title'>搜索全部</Text>
                <Text className='search-chevron'>
                  {searchOpen ? '收起' : '展开 · ' + notebooks.length}
                </Text>
              </View>
              {searchOpen ? (
                <View className='search-panel'>
                  <Input
                    className='input sheet-input'
                    value={searchQ}
                    placeholder='搜索笔记本名称'
                    confirmType='search'
                    onInput={(e) => setSearchQ(e.detail.value)}
                  />
                  <ScrollView scrollY className='search-scroll'>
                    {filtered.length === 0 ? (
                      <Text className='muted empty-search'>没有匹配的笔记本</Text>
                    ) : (
                      filtered.map((nb) => (
                        <View
                          key={'all-' + nb.notebook_id}
                          className={
                            'nb-row compact' + (submitting ? ' disabled' : '')
                          }
                          onClick={() => finishCollect(nb.notebook_id)}
                        >
                          <View className='nb-avatar sm'>
                            <Text className='nb-avatar-text'>
                              {(nb.name || 'N').slice(0, 1)}
                            </Text>
                          </View>
                          <Text className='nb-name flex1'>{nb.name}</Text>
                          <Text className='nb-go'>加入</Text>
                        </View>
                      ))
                    )}
                  </ScrollView>
                </View>
              ) : null}
            </View>
          </View>
        </View>
      ) : null}
    </View>
  )
}
