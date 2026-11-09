import Taro from '@tarojs/taro'

const SERVER_KEY = 'vn_server_url'
const TOKEN_KEY = 'vn_agent_token'
const SEED_KEY = 'vn_config_seed'

/** 开发默认：可在「连接设置」里改；仅本机调试用，勿提交到公开仓库 */
export const DEFAULT_SERVER_URL = 'https://bobsled-booting-enigmatic.ngrok-free.dev'
export const DEFAULT_TOKEN = ''
const SEED_VERSION = 'ngrok-2026-11-07'

export type ConnectionConfig = {
  serverUrl: string
  token: string
}

export function getConfig(): ConnectionConfig {
  return {
    serverUrl: String(Taro.getStorageSync(SERVER_KEY) || DEFAULT_SERVER_URL).trim().replace(/\/$/, ''),
    token: String(Taro.getStorageSync(TOKEN_KEY) || DEFAULT_TOKEN).trim()
  }
}

export function saveConfig(cfg: ConnectionConfig) {
  const serverUrl = cfg.serverUrl.trim().replace(/\/$/, '')
  const token = cfg.token.trim()
  Taro.setStorageSync(SERVER_KEY, serverUrl)
  Taro.setStorageSync(TOKEN_KEY, token)
}

export function clearConfig() {
  Taro.removeStorageSync(SERVER_KEY)
  Taro.removeStorageSync(TOKEN_KEY)
}

export function hasConfig(): boolean {
  const { serverUrl, token } = getConfig()
  return Boolean(serverUrl && token)
}

/** 首次或默认种子升级时写入 ngrok 默认地址 */
export function seedDefaultConfig() {
  if (Taro.getStorageSync(SEED_KEY) === SEED_VERSION) return
  saveConfig({ serverUrl: DEFAULT_SERVER_URL, token: DEFAULT_TOKEN })
  Taro.setStorageSync(SEED_KEY, SEED_VERSION)
}
