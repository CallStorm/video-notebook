import { useRef, useState } from 'react'
import { View, Text, Image, Input } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { hasConfig } from '../../store/config'
import {
  autoOrganizeTags,
  deleteNotebook,
  listNotebooks,
  listTags
} from '../../services/agent'
import type { NotebookBrief, TagBrief } from '../../types/agent'
import './index.scss'

const COVER_TONES = ['#D9EEE8', '#E8E4F5', '#F5E6D8', '#E3F0F7', '#F3E8EE', '#EAF3E0']
const DELETE_WIDTH = 76
const SWIPE_OPEN_THRESHOLD = 36

function coverTone(id: number) {
  return COVER_TONES[Math.abs(id) % COVER_TONES.length]
}

type TouchLock = '' | 'h' | 'v'

export default function NotebooksPage() {
  const [items, setItems] = useState<NotebookBrief[]>([])
  const [tags, setTags] = useState<TagBrief[]>([])
  const [loading, setLoading] = useState(false)
  const [organizing, setOrganizing] = useState(false)
  const [q, setQ] = useState('')
  const [tagId, setTagId] = useState<number | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [openId, setOpenId] = useState<number | null>(null)
  const [dragId, setDragId] = useState<number | null>(null)
  const [dragOffset, setDragOffset] = useState(0)
  const [catchId, setCatchId] = useState<number | null>(null)
  const skipClickRef = useRef(false)
  const offsetRef = useRef(0)
  const touchRef = useRef({
    startX: 0,
    startY: 0,
    startOffset: 0,
    locking: '' as TouchLock,
    id: null as number | null,
    moved: false
  })

  async function load(search?: string, nextTagId?: number | null) {
    const s = typeof search === 'string' ? search : q
    const tid = typeof nextTagId === 'undefined' ? tagId : nextTagId
    if (!hasConfig()) {
      Taro.navigateTo({ url: '/pages/connect/index' })
      return
    }
    setLoading(true)
    try {
      const nb = await listNotebooks({ search: s, tagId: tid })
      setItems(nb.items || [])
      setOpenId(null)
      setDragId(null)
      setCatchId(null)
      try {
        const tg = await listTags()
        setTags(tg.items || [])
      } catch (err) {
        setTags([])
      }
    } catch (e) {
      const msg = e && (e as Error).message ? (e as Error).message : '加载失败'
      Taro.showToast({ title: msg, icon: 'none' })
    } finally {
      setLoading(false)
    }
  }

  useDidShow(function () {
    load()
  })

  function onPickTag(id: number | null) {
    setTagId(id)
    setSheetOpen(false)
    load(q, id)
  }

  function clearTag(e?: { stopPropagation?: () => void }) {
    if (e && e.stopPropagation) e.stopPropagation()
    onPickTag(null)
  }

  function confirmDelete(nb: NotebookBrief) {
    Taro.showModal({
      title: '删除笔记本',
      content: '确定删除「' + (nb.name || '未命名') + '」？删除后列表中不再显示。',
      confirmText: '删除',
      confirmColor: '#dc2626',
      success: async function (res) {
        if (!res.confirm) return
        try {
          Taro.showLoading({ title: '删除中' })
          await deleteNotebook(nb.notebook_id)
          Taro.hideLoading()
          Taro.showToast({ title: '已删除', icon: 'success' })
          setOpenId(null)
          load(q, tagId)
        } catch (e) {
          Taro.hideLoading()
          const msg = e && (e as Error).message ? (e as Error).message : '删除失败'
          Taro.showToast({ title: msg, icon: 'none' })
        }
      }
    })
  }

  function closeSwipe() {
    setOpenId(null)
    setDragId(null)
    setCatchId(null)
    offsetRef.current = 0
    setDragOffset(0)
  }

  function frontOffset(id: number) {
    if (dragId === id) return dragOffset
    if (openId === id) return -DELETE_WIDTH
    return 0
  }

  function onSwipeTouchStart(nb: NotebookBrief, e: { touches: Array<{ clientX: number; clientY: number }> }) {
    const t = e.touches[0]
    if (!t) return
    const id = nb.notebook_id
    if (openId != null && openId !== id) {
      setOpenId(null)
    }
    const startOffset = openId === id ? -DELETE_WIDTH : 0
    offsetRef.current = startOffset
    touchRef.current = {
      startX: t.clientX,
      startY: t.clientY,
      startOffset,
      locking: '',
      id,
      moved: false
    }
    setDragId(id)
    setDragOffset(startOffset)
    skipClickRef.current = false
  }

  function onSwipeTouchMove(nb: NotebookBrief, e: { touches: Array<{ clientX: number; clientY: number }> }) {
    const tr = touchRef.current
    if (tr.id !== nb.notebook_id) return
    const t = e.touches[0]
    if (!t) return
    const dx = t.clientX - tr.startX
    const dy = t.clientY - tr.startY
    if (!tr.locking) {
      if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return
      tr.locking = Math.abs(dx) > Math.abs(dy) ? 'h' : 'v'
      if (tr.locking === 'h') {
        setCatchId(nb.notebook_id)
      }
    }
    if (tr.locking !== 'h') return
    tr.moved = true
    skipClickRef.current = true
    let next = tr.startOffset + dx
    if (next > 0) next = 0
    if (next < -DELETE_WIDTH - 24) next = -DELETE_WIDTH - 24
    offsetRef.current = next
    setDragOffset(next)
  }

  function onSwipeTouchEnd(nb: NotebookBrief) {
    const tr = touchRef.current
    if (tr.id !== nb.notebook_id) return
    setCatchId(null)
    if (tr.locking === 'v') {
      setDragId(null)
      touchRef.current.id = null
      return
    }
    if (tr.locking === 'h' || tr.moved) {
      skipClickRef.current = true
      const final = offsetRef.current
      const shouldOpen =
        final <= -SWIPE_OPEN_THRESHOLD ||
        (tr.startOffset < 0 && final < -DELETE_WIDTH * 0.45)
      if (shouldOpen) {
        setOpenId(nb.notebook_id)
        offsetRef.current = -DELETE_WIDTH
        setDragOffset(-DELETE_WIDTH)
      } else {
        setOpenId(null)
        offsetRef.current = 0
        setDragOffset(0)
      }
    }
    setDragId(null)
    touchRef.current.id = null
  }

  function onBookTap(nb: NotebookBrief) {
    if (skipClickRef.current) {
      skipClickRef.current = false
      return
    }
    if (openId === nb.notebook_id) {
      closeSwipe()
      return
    }
    if (openId != null) {
      closeSwipe()
      return
    }
    Taro.navigateTo({
      url: '/pages/detail/index?id=' + nb.notebook_id
    })
  }

  async function onAutoOrganize() {
    if (organizing) return
    if (!items.length) {
      Taro.showToast({ title: '暂无笔记本可归类', icon: 'none' })
      return
    }
    const modal = await Taro.showModal({
      title: '自动归类标签',
      content: '将根据全部笔记本名称与描述，自动生成并覆盖标签关联。是否继续？',
      confirmText: '开始归类'
    })
    if (!modal.confirm) return
    setOrganizing(true)
    try {
      Taro.showLoading({ title: '归类中' })
      const result = await autoOrganizeTags()
      Taro.hideLoading()
      if (result.applied) {
        Taro.showToast({
          title: '已归类 ' + (result.tags?.length || 0) + ' 个标签',
          icon: 'success'
        })
        setTagId(null)
        load('', null)
      } else {
        Taro.showToast({
          title: result.message || '归类未完成',
          icon: 'none'
        })
      }
    } catch (e) {
      Taro.hideLoading()
      const msg = e && (e as Error).message ? (e as Error).message : '归类失败'
      Taro.showToast({ title: msg, icon: 'none' })
    } finally {
      setOrganizing(false)
    }
  }

  const empty = !loading && items.length === 0
  const activeTag = tags.find(function (t) {
    return t.id === tagId
  })
  const sheetTags = [{ id: null as number | null, name: '全部' }].concat(
    tags.map(function (t) {
      return { id: t.id, name: t.name }
    })
  )

  return (
    <View
      className='page nb-page'
      onClick={function () {
        if (openId != null) closeSwipe()
      }}
    >
      <View className='toolbar'>
        <View className='search-wrap'>
          <Input
            className='search-input'
            value={q}
            placeholder='搜索笔记本'
            confirmType='search'
            onInput={function (e) {
              setQ(e.detail.value)
            }}
            onConfirm={function () {
              load(q, tagId)
            }}
          />
        </View>
        <View
          className={tagId != null ? 'filter-btn on' : 'filter-btn'}
          onClick={function () {
            setSheetOpen(true)
          }}
        >
          <Text className='filter-icon'>标签</Text>
          <Text className='filter-label'>
            {activeTag ? activeTag.name : '筛选'}
          </Text>
          {tagId != null ? (
            <Text
              className='filter-clear'
              onClick={function (e) {
                clearTag(e)
              }}
            >
              ×
            </Text>
          ) : null}
        </View>
      </View>

      <View className='actions-row'>
        <View
          className={'auto-tag-btn' + (organizing ? ' disabled' : '')}
          onClick={onAutoOrganize}
        >
          <Text className='auto-tag-text'>
            {organizing ? '归类中…' : '自动归类标签'}
          </Text>
        </View>
        <Text className='actions-hint'>左滑可删除</Text>
      </View>

      {loading ? <Text className='muted tip'>加载中…</Text> : null}

      {empty ? (
        <View className='empty'>
          <View className='empty-title'>还没有笔记本</View>
          <Text className='muted'>去收集页粘贴视频链接</Text>
          <View
            className='btn-primary empty-btn'
            onClick={function () {
              Taro.switchTab({ url: '/pages/collect/index' })
            }}
          >
            去收集
          </View>
        </View>
      ) : null}

      <View className='shelf'>
        {items.map(function (nb) {
          const ox = frontOffset(nb.notebook_id)
          const dragging = dragId === nb.notebook_id
          return (
            <View
              key={nb.notebook_id}
              className='book-swipe'
              catchMove={catchId === nb.notebook_id}
              onClick={function (e) {
                e.stopPropagation()
              }}
              onTouchStart={function (e) {
                onSwipeTouchStart(nb, e)
              }}
              onTouchMove={function (e) {
                onSwipeTouchMove(nb, e)
              }}
              onTouchEnd={function () {
                onSwipeTouchEnd(nb)
              }}
              onTouchCancel={function () {
                onSwipeTouchEnd(nb)
              }}
            >
              <View className='book-swipe-actions'>
                <View
                  className='book-swipe-del'
                  onClick={function (e) {
                    e.stopPropagation()
                    confirmDelete(nb)
                  }}
                >
                  <Text className='book-swipe-del-text'>删除</Text>
                </View>
              </View>
              <View
                className={
                  'book-swipe-front' + (dragging ? ' dragging' : '')
                }
                style={{
                  transform: 'translateX(' + ox + 'px)'
                }}
                onClick={function (e) {
                  e.stopPropagation()
                  onBookTap(nb)
                }}
              >
                <View
                  className='cover-box'
                  style={{ backgroundColor: coverTone(nb.notebook_id) }}
                >
                  {nb.cover_url ? (
                    <Image
                      className='cover-img'
                      src={nb.cover_url}
                      mode='aspectFill'
                    />
                  ) : (
                    <View className='cover-fallback'>
                      <Text className='cover-letter'>
                        {(nb.name || 'N').slice(0, 1)}
                      </Text>
                    </View>
                  )}
                </View>
                <View className='book-meta'>
                  <Text className='book-title'>{nb.name}</Text>
                  {nb.description ? (
                    <Text className='book-desc'>{nb.description}</Text>
                  ) : null}
                  {nb.tags && nb.tags.length ? (
                    <View className='book-tags'>
                      {nb.tags.slice(0, 3).map(function (tg) {
                        return (
                          <Text key={tg.id} className='book-tag'>
                            {tg.name}
                          </Text>
                        )
                      })}
                    </View>
                  ) : null}
                </View>
              </View>
            </View>
          )
        })}
      </View>

      {sheetOpen ? (
        <View className='filter-overlay'>
          <View
            className='filter-mask'
            catchMove
            onClick={function () {
              setSheetOpen(false)
            }}
          />
          <View className='filter-sheet' catchMove>
            <View className='sheet-handle' />
            <Text className='sheet-title'>按标签筛选</Text>
            <View className='tag-grid'>
              {sheetTags.map(function (t) {
                const active = t.id === tagId
                return (
                  <View
                    key={t.id === null ? 'all' : 'tag-' + String(t.id)}
                    className={active ? 'tag-chip on' : 'tag-chip'}
                    onClick={function () {
                      onPickTag(t.id)
                    }}
                  >
                    <Text className='tag-chip-text'>{t.name}</Text>
                  </View>
                )
              })}
            </View>
          </View>
        </View>
      ) : null}
    </View>
  )
}
