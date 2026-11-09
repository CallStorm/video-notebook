import Taro from '@tarojs/taro'
import { getConfig } from '../store/config'

export class ApiError extends Error {
  status: number
  constructor(message: string, status = 0) {
    super(message)
    this.status = status
  }
}

function maskToken(token: string) {
  if (!token) return ''
  if (token.length <= 8) return '***'
  return token.slice(0, 6) + '…' + token.slice(-4)
}

function authHeaders(token: string, serverUrl: string): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: 'Bearer ' + token
  }
  // ngrok 免费域名会拦无头请求，加此头跳过浏览器警告页
  if (/ngrok/i.test(serverUrl)) {
    headers['ngrok-skip-browser-warning'] = 'true'
  }
  return headers
}

export async function callTool<T = any>(name: string, args: Record<string, unknown> = {}): Promise<T> {
  const { serverUrl, token } = getConfig()
  if (!serverUrl) throw new ApiError('请先配置 Server URL')
  if (!token) throw new ApiError('请先配置 Agent Token')
  if (!token.startsWith('vn_agent_')) {
    throw new ApiError('Token 应以 vn_agent_ 开头')
  }

  const url = serverUrl + '/agent/v1/tools/' + encodeURIComponent(name)
  const res = await Taro.request({
    url,
    method: 'POST',
    timeout: 30000,
    header: authHeaders(token, serverUrl),
    data: args
  })

  const status = res.statusCode || 0
  const data = res.data as any
  if (status >= 200 && status < 300) {
    return data as T
  }
  const msg =
    (data && (data.message || data.detail || data.error)) ||
    ('请求失败 HTTP ' + status + '（token ' + maskToken(token) + '）')
  throw new ApiError(String(msg), status)
}

export async function listTools(): Promise<{ tools: Array<{ name: string }> }> {
  const { serverUrl, token } = getConfig()
  if (!serverUrl || !token) throw new ApiError('请先配置连接')
  const url = serverUrl + '/agent/v1/tools'
  const res = await Taro.request({
    url,
    method: 'GET',
    timeout: 15000,
    header: authHeaders(token, serverUrl)
  })
  if (res.statusCode >= 200 && res.statusCode < 300) {
    return res.data as any
  }
  const data = res.data as any
  throw new ApiError((data && data.message) || ('连通失败 HTTP ' + res.statusCode), res.statusCode)
}
