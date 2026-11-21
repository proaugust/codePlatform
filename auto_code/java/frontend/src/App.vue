<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { checkHealth, formatError } from './api/client'

const healthState = ref<'unknown' | 'ok' | 'down'>('unknown')
const healthDetail = ref('检测中…')
const checking = ref(false)

async function ping() {
  checking.value = true
  try {
    const data = await checkHealth()
    healthState.value = data.status === 'ok' ? 'ok' : 'down'
    healthDetail.value = data.status === 'ok' ? '后端服务正常' : `状态：${data.status}`
  } catch (error) {
    const info = formatError(error)
    healthState.value = 'down'
    healthDetail.value = `${info.code}：${info.message}`
  } finally {
    checking.value = false
  }
}

onMounted(ping)
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">
        <h1>图书管理系统</h1>
        <span class="brand-sub">Spring Boot + Vue 3 简易联调</span>
      </div>
      <nav class="nav">
        <RouterLink to="/books">图书列表</RouterLink>
        <RouterLink to="/books/new">新增图书</RouterLink>
      </nav>
      <div class="health" :class="healthState">
        <span class="dot" />
        <span class="health-text">{{ healthDetail }}</span>
        <button class="btn tiny" type="button" :disabled="checking" @click="ping">
          {{ checking ? '检测中' : '重新检测' }}
        </button>
      </div>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
