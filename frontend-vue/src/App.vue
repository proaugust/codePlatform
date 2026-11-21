<script setup lang="ts">
import { menus } from './menus'
import { usePlatform, usePlatformBootstrap } from './composables/usePlatform'

usePlatformBootstrap()

const { targetLabel, BACKEND_PORT, FRONTEND_PORT, hasFrontend, elicitation, elicitStatus } = usePlatform()
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="topbar-left">
        <span class="brand">Code Platform · Vue</span>
        <nav class="main-nav" aria-label="主菜单">
          <RouterLink v-for="m in menus" :key="m.key" :to="m.path">{{ m.title }}</RouterLink>
        </nav>
        <span class="muted topbar-meta">
          生成目标 {{ targetLabel }} · 后端 {{ BACKEND_PORT }}
          <template v-if="hasFrontend"> · 业务前端 {{ FRONTEND_PORT }}</template>
          <template v-if="elicitation"> · {{ elicitation.session_id }} · {{ elicitStatus }}</template>
        </span>
      </div>
    </header>

    <main class="page page-wide workspace">
      <RouterView />
    </main>
  </div>
</template>
