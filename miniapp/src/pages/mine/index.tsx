import { View, Text, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { clearConfig, getConfig } from '../../store/config'
import logo from '../../assets/logo.png'
import './index.scss'

export default function MinePage() {
  const cfg = getConfig()
  const tokenHint = cfg.token
    ? cfg.token.slice(0, 8) + '…' + cfg.token.slice(-4)
    : '未配置'

  const onClear = () => {
    Taro.showModal({
      title: '清除配置',
      content: '将删除本机保存的 Server URL 与 Token',
      success: (res) => {
        if (res.confirm) {
          clearConfig()
          Taro.showToast({ title: '已清除', icon: 'success' })
          setTimeout(() => Taro.navigateTo({ url: '/pages/connect/index' }), 400)
        }
      }
    })
  }

  return (
    <View className='page'>
      <View className='card brand-box'>
        <Image className='logo' src={logo} mode='aspectFill' />
        <View>
          <View className='name'>影知</View>
          <Text className='en'>Videnote</Text>
        </View>
      </View>

      <View className='card'>
        <View className='section-title'>当前连接</View>
        <Text className='muted'>Server：{cfg.serverUrl || '未配置'}</Text>
        <View />
        <Text className='muted'>Token：{tokenHint}</Text>
        <View
          className='btn-primary'
          style={{ marginTop: '14px' }}
          onClick={() => Taro.navigateTo({ url: '/pages/connect/index' })}
        >
          连接设置
        </View>
        <View className='btn-ghost' style={{ marginTop: '10px' }} onClick={onClear}>
          清除本地配置
        </View>
      </View>

      <View className='card'>
        <View className='section-title'>说明</View>
        <Text className='muted'>
          影知是视频笔记的微信收集入口。开发期请在微信开发者工具关闭「校验合法域名、web-view、TLS
          版本以及 HTTPS 证书」，以便访问内网 HTTP。正式发布仍需 HTTPS 合法域名。
        </Text>
      </View>
    </View>
  )
}
