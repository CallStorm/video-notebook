import { useState } from 'react'
import { View, Text, Input, Textarea } from '@tarojs/components'
import Taro, { useLoad } from '@tarojs/taro'
import { DEFAULT_SERVER_URL, DEFAULT_TOKEN, getConfig, saveConfig } from '../../store/config'
import { testConnection } from '../../services/agent'
import './index.scss'

export default function ConnectPage() {
  const [serverUrl, setServerUrl] = useState('')
  const [token, setToken] = useState('')
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState('')
  const [ok, setOk] = useState(false)

  useLoad(() => {
    const cfg = getConfig()
    setServerUrl(cfg.serverUrl || DEFAULT_SERVER_URL)
    setToken(cfg.token || DEFAULT_TOKEN)
  })

  const onSave = async () => {
    if (!serverUrl.trim()) {
      Taro.showToast({ title: '请填写 Server URL', icon: 'none' })
      return
    }
    if (!token.trim().startsWith('vn_agent_')) {
      Taro.showToast({ title: 'Token 需以 vn_agent_ 开头', icon: 'none' })
      return
    }
    saveConfig({ serverUrl, token })
    Taro.showToast({ title: '已保存', icon: 'success' })
  }

  const onTest = async () => {
    saveConfig({ serverUrl, token })
    setTesting(true)
    setResult('')
    try {
      const r = await testConnection()
      setOk(true)
      setResult('连通成功：' + r.via + (typeof r.tools === 'number' ? '，' + r.tools + ' 个工具' : ''))
      Taro.showToast({ title: '连通成功', icon: 'success' })
    } catch (e: any) {
      setOk(false)
      setResult(e?.message || '连通失败')
      Taro.showToast({ title: '连通失败', icon: 'none' })
    } finally {
      setTesting(false)
    }
  }

  return (
    <View className='page'>
      <View className='card'>
        <View className='section-title'>影知 · 连接服务</View>
        <Text className='muted hint'>
          默认已填 ngrok 公网地址与 Agent Token。开发者工具请关闭「校验合法域名」；真机预览一般可直连 HTTPS。
        </Text>
        <View className='label'>Server URL</View>
        <Input
          className='input'
          value={serverUrl}
          placeholder={DEFAULT_SERVER_URL}
          onInput={(e) => setServerUrl(e.detail.value)}
        />
        <View className='label'>Agent Token</View>
        <Textarea
          className='input'
          value={token}
          placeholder='vn_agent_…'
          maxlength={200}
          autoHeight
          onInput={(e) => setToken(e.detail.value)}
        />
        <View className='row btn-primary' onClick={onSave}>保存配置</View>
        <View className='row btn-ghost' onClick={onTest}>{testing ? '测试中…' : '连通测试'}</View>
        {result ? <View className={'result ' + (ok ? '' : 'err')}>{result}</View> : null}
      </View>
    </View>
  )
}
