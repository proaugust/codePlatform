export type MenuItem = {
  key: 'chat' | 'runtime' | 'docs' | 'artifacts' | 'settings'
  title: string
  path: string
}

/** 顶栏主菜单注册表：增页只改这里 + router 映射 */
export const menus: MenuItem[] = [
  { key: 'chat', title: '聊天', path: '/chat' },
  { key: 'runtime', title: '运行', path: '/runtime' },
  { key: 'docs', title: '文档', path: '/docs' },
  { key: 'artifacts', title: '代码', path: '/artifacts' },
  { key: 'settings', title: '设置', path: '/settings' },
]

export const DEFAULT_MENU_PATH = menus[0]?.path ?? '/chat'
