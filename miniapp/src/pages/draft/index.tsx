import { useState } from 'react'
import { View, Text } from '@tarojs/components'
import Taro, { useLoad } from '@tarojs/taro'
import { getDraft } from '../../services/agent'
import './index.scss'

export default function DraftPage() {
  const [title, setTitle] = useState('知识底稿')
  const [body, setBody] = useState('')
  const [empty, setEmpty] = useState(false)

  useLoad(async (query) => {
    const id = Number(query.id || 0)
    if (!id) return
    try {
      const data = await getDraft(id)
      if (!data.draft) {
        setEmpty(true)
        setBody('暂无底稿，请先在详情页生成。')
        return
      }
      const d = data.draft
      const t = String(d.title || '知识底稿')
      setTitle(t)
      Taro.setNavigationBarTitle({ title: t })
      const content = String(d.markdown || d.content || d.summary || JSON.stringify(d, null, 2))
      setBody(content)
    } catch (e: any) {
      setEmpty(true)
      setBody(e?.message || '读取失败')
    }
  })

  return (
    <View className='page'>
      <View className='card'>
        <View className='section-title'>{title}</View>
        {empty ? <Text className='muted'>{body}</Text> : <Text className='body'>{body}</Text>}
      </View>
    </View>
  )
}
