import { createRouter, createWebHistory } from 'vue-router'
import { DEFAULT_MENU_PATH, menus } from '../menus'
import ArtifactsPage from '../pages/ArtifactsPage.vue'
import ChatPage from '../pages/ChatPage.vue'
import DocsPage from '../pages/DocsPage.vue'
import RuntimePage from '../pages/RuntimePage.vue'
import SettingsPage from '../pages/SettingsPage.vue'

const pageMap = {
  chat: ChatPage,
  runtime: RuntimePage,
  docs: DocsPage,
  artifacts: ArtifactsPage,
  settings: SettingsPage,
} as const

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: DEFAULT_MENU_PATH },
    ...menus.map((m) => ({
      path: m.path,
      name: m.key,
      component: pageMap[m.key],
    })),
  ],
})

export default router
