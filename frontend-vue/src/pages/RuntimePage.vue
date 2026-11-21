<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { usePlatform } from '../composables/usePlatform'

type RuntimeTab = 'backend' | 'frontend' | 'runs'

const {
  busy,
  startingBackend,
  startingFrontend,
  stoppingBackend,
  stoppingFrontend,
  hasFrontend,
  BACKEND_URL,
  FRONTEND_URL,
  backendListening,
  frontendListening,
  refreshingLogs,
  logPathHint,
  pipelineNote,
  target,
  targetLabel,
  BACKEND_PORT,
  FRONTEND_PORT,
  backendLog,
  frontendLog,
  runLogs,
  error,
  switchTarget,
  onToggleBackend,
  onToggleFrontend,
  refreshConsoleLogs,
  clearRuntimeLogs,
} = usePlatform()

const activeTab = ref<RuntimeTab>('backend')
const backendLogEl = ref<HTMLElement | null>(null)
const frontendLogEl = ref<HTMLElement | null>(null)
const clearingLogs = ref(false)

watch(hasFrontend, (ok) => {
  if (!ok && activeTab.value === 'frontend') activeTab.value = 'backend'
})

async function scrollLogToBottom(el: HTMLElement | null) {
  await nextTick()
  if (el) el.scrollTop = el.scrollHeight
}

watch(backendLog, () => {
  if (activeTab.value === 'backend') void scrollLogToBottom(backendLogEl.value)
})

watch(frontendLog, () => {
  if (activeTab.value === 'frontend') void scrollLogToBottom(frontendLogEl.value)
})

watch(activeTab, async (tab) => {
  await nextTick()
  if (tab === 'backend') void scrollLogToBottom(backendLogEl.value)
  if (tab === 'frontend') void scrollLogToBottom(frontendLogEl.value)
})

async function onClearCurrentLogs() {
  if (activeTab.value === 'runs' || clearingLogs.value) return
  clearingLogs.value = true
  try {
    await clearRuntimeLogs(activeTab.value)
  } finally {
    clearingLogs.value = false
  }
}

onMounted(() => {
  void refreshConsoleLogs().then(() => {
    void scrollLogToBottom(backendLogEl.value)
  })
})
</script>

<template>
  <div class="runtime-page">
    <div class="runtime-toolbar">
      <div class="lang-switch" role="group" aria-label="运行目标语言">
        <button
          type="button"
          :class="['lang-btn', { active: target === 'java' }]"
          :disabled="busy"
          @click="switchTarget('java')"
        >
          Java
        </button>
        <button
          type="button"
          :class="['lang-btn', { active: target === 'go' }]"
          :disabled="busy"
          @click="switchTarget('go')"
        >
          Go
        </button>
      </div>
      <button
        type="button"
        :class="['btn-start', { 'btn-stop': backendListening }]"
        :disabled="busy"
        @click="onToggleBackend"
      >
        {{
          startingBackend
            ? '启动中…'
            : stoppingBackend
              ? '停止中…'
              : backendListening
                ? '停止后端'
                : '启动后端'
        }}
      </button>
      <button
        v-if="hasFrontend"
        type="button"
        :class="['btn-start', 'btn-start-fe', { 'btn-stop': frontendListening }]"
        :disabled="busy"
        @click="onToggleFrontend"
      >
        {{
          startingFrontend
            ? '启动中…'
            : stoppingFrontend
              ? '停止中…'
              : frontendListening
                ? '停止前端'
                : '启动前端'
        }}
      </button>
      <a class="link-pill" :href="BACKEND_URL" target="_blank" rel="noreferrer">打开后端</a>
      <a
        v-if="hasFrontend && FRONTEND_URL"
        class="link-pill"
        :href="FRONTEND_URL"
        target="_blank"
        rel="noreferrer"
      >
        打开前端
      </a>
    </div>

    <p v-if="pipelineNote" class="muted runtime-note">{{ pipelineNote }}</p>

    <div class="runtime-main">
      <div class="runtime-tabs" role="tablist" aria-label="运行日志">
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'backend'"
          :class="['runtime-tab', { active: activeTab === 'backend' }]"
          @click="activeTab = 'backend'"
        >
          {{ targetLabel }} 后端
          <span :class="backendListening ? 'ok' : 'bad'">{{
            backendListening ? 'LISTEN' : 'DOWN'
          }}</span>
        </button>
        <button
          v-if="hasFrontend"
          type="button"
          role="tab"
          :aria-selected="activeTab === 'frontend'"
          :class="['runtime-tab', { active: activeTab === 'frontend' }]"
          @click="activeTab = 'frontend'"
        >
          Vue 前端
          <span :class="frontendListening ? 'ok' : 'bad'">{{
            frontendListening ? 'LISTEN' : 'DOWN'
          }}</span>
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'runs'"
          :class="['runtime-tab', { active: activeTab === 'runs' }]"
          @click="activeTab = 'runs'"
        >
          运行记录
          <span class="tab-count">{{ runLogs.length }}</span>
        </button>
        <div class="runtime-tabs-actions">
          <button
            type="button"
            class="btn-ghost"
            :disabled="refreshingLogs"
            @click="refreshConsoleLogs"
          >
            {{ refreshingLogs ? '提取中…' : '刷新日志' }}
          </button>
          <button
            v-if="activeTab === 'backend' || activeTab === 'frontend'"
            type="button"
            class="btn-danger"
            :disabled="refreshingLogs || clearingLogs"
            @click="onClearCurrentLogs"
          >
            {{ clearingLogs ? '清空中…' : '删除所有日志' }}
          </button>
          <span class="muted">{{ logPathHint }}</span>
        </div>
      </div>

      <div class="runtime-pane">
        <template v-if="activeTab === 'backend'">
          <div class="console-card-head">
            <strong>{{ targetLabel }} 后端 :{{ BACKEND_PORT }}</strong>
            <span :class="backendListening ? 'ok' : 'bad'">{{
              backendListening ? 'LISTEN' : 'DOWN'
            }}</span>
            <a :href="BACKEND_URL" target="_blank" rel="noreferrer">打开</a>
          </div>
          <pre ref="backendLogEl" class="console-out">{{
            backendLog || '（启动成功后自动提取一次；也可点「刷新日志」）'
          }}</pre>
        </template>

        <template v-else-if="activeTab === 'frontend'">
          <div class="console-card-head">
            <strong>Vue 前端 :{{ FRONTEND_PORT }}</strong>
            <span :class="frontendListening ? 'ok' : 'bad'">{{
              frontendListening ? 'LISTEN' : 'DOWN'
            }}</span>
            <a :href="FRONTEND_URL" target="_blank" rel="noreferrer">打开</a>
          </div>
          <pre ref="frontendLogEl" class="console-out">{{
            frontendLog || '（启动成功后自动提取一次；也可点「刷新日志」）'
          }}</pre>
        </template>

        <template v-else>
          <div v-if="!runLogs.length" class="muted run-log-empty">暂无记录。</div>
          <ul v-else class="run-log-list">
            <li
              v-for="log in runLogs"
              :key="log.id"
              :class="['run-log-item', `kind-${log.kind}`]"
            >
              <div class="run-log-head">
                <strong>{{ log.title }}</strong>
                <span class="muted">{{ log.at }}</span>
                <a v-if="log.url" :href="log.url" target="_blank" rel="noreferrer">打开</a>
              </div>
              <div class="run-log-msg">{{ log.message }}</div>
              <pre v-if="log.detail" class="run-log-detail">{{ log.detail }}</pre>
            </li>
          </ul>
        </template>
      </div>
    </div>

    <pre v-if="error" class="error">{{ error }}</pre>
  </div>
</template>
