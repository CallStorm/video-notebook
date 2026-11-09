import { PropsWithChildren } from 'react'
import { useLaunch } from '@tarojs/taro'
import { seedDefaultConfig } from './store/config'
import './app.scss'

function App({ children }: PropsWithChildren) {
  useLaunch(() => {
    seedDefaultConfig()
    console.log('影知 miniapp launch')
  })
  return children
}

export default App
