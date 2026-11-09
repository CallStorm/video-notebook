export default defineAppConfig({
  pages: [
    'pages/notebooks/index',
    'pages/collect/index',
    'pages/mine/index',
    'pages/connect/index',
    'pages/detail/index',
    'pages/draft/index'
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#ffffff',
    navigationBarTitleText: '笔记本',
    navigationBarTextStyle: 'black',
    backgroundColor: '#f5f7fa'
  },
  tabBar: {
    color: '#94a3b8',
    selectedColor: '#0f766e',
    backgroundColor: '#ffffff',
    borderStyle: 'white',
    list: [
      {
        pagePath: 'pages/notebooks/index',
        text: '笔记本',
        iconPath: 'assets/tab-notebook.png',
        selectedIconPath: 'assets/tab-notebook-active.png'
      },
      {
        pagePath: 'pages/collect/index',
        text: '收集',
        iconPath: 'assets/tab-collect.png',
        selectedIconPath: 'assets/tab-collect-active.png'
      },
      {
        pagePath: 'pages/mine/index',
        text: '我的',
        iconPath: 'assets/tab-mine.png',
        selectedIconPath: 'assets/tab-mine-active.png'
      }
    ]
  }
})