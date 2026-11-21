<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePlatform } from '../composables/usePlatform'

const { docs, activeDoc, status, error, loadDocs, refreshStatus } = usePlatform()

const fullscreen = ref(false)

const currentDoc = computed(() => docs.value[activeDoc.value] ?? null)

async function onRefresh() {
  await Promise.all([loadDocs(), refreshStatus()])
}

function openFullscreen() {
  if (!currentDoc.value) return
  fullscreen.value = true
}

function closeFullscreen() {
  fullscreen.value = false
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && fullscreen.value) {
    e.preventDefault()
    closeFullscreen()
  }
}

watch(fullscreen, (on) => {
  document.body.classList.toggle('docs-fullscreen-open', on)
})

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.body.classList.remove('docs-fullscreen-open')
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="docs-page">
    <div class="page-toolbar">
      <button type="button" class="btn-ghost" @click="onRefresh">刷新文档</button>
      <button
        type="button"
        class="btn-ghost"
        :disabled="!docs.length"
        @click="openFullscreen"
      >
        全屏查看
      </button>
      <span v-if="status" class="muted">
        文档 {{ status.has_docs ? '已就绪' : '未生成' }}
        <template v-if="status.root"> · {{ status.root }}</template>
      </span>
    </div>

    <div v-if="docs.length" class="docs-result">
      <div class="docs-head">
        <h2>需求文档（Agent 产出）</h2>
        <button type="button" class="btn-ghost" :disabled="!currentDoc" @click="openFullscreen">
          全屏
        </button>
      </div>
      <div class="doc-tabs">
        <button
          v-for="(d, i) in docs"
          :key="d.path"
          type="button"
          :class="i === activeDoc ? 'tab active' : 'tab'"
          @click="activeDoc = i"
        >
          {{ d.title }}
        </button>
      </div>
      <p class="muted docs-path"><code>{{ docs[activeDoc]?.path }}</code></p>
      <pre class="doc-body">{{ docs[activeDoc]?.content }}</pre>
    </div>
    <div v-else class="docs-result docs-empty">
      <h2>需求文档</h2>
      <p class="muted">暂无文档。请先在「分析」中确认结论并生成，或在「设置」中粘贴需求直接生成。</p>
    </div>

    <pre v-if="error" class="error docs-error">{{ error }}</pre>
  </div>

  <Teleport to="body">
    <div
      v-if="fullscreen && currentDoc"
      class="doc-fullscreen"
      role="dialog"
      aria-modal="true"
      :aria-label="currentDoc.title"
    >
      <div class="doc-fullscreen-bar">
        <div class="doc-fullscreen-meta">
          <strong>{{ currentDoc.title }}</strong>
          <code class="muted">{{ currentDoc.path }}</code>
        </div>
        <div class="doc-fullscreen-actions">
          <div class="doc-tabs doc-tabs-inline">
            <button
              v-for="(d, i) in docs"
              :key="d.path"
              type="button"
              :class="i === activeDoc ? 'tab active' : 'tab'"
              @click="activeDoc = i"
            >
              {{ d.title }}
            </button>
          </div>
          <button type="button" class="btn-secondary" @click="closeFullscreen">退出全屏 (Esc)</button>
        </div>
      </div>
      <pre class="doc-fullscreen-body">{{ currentDoc.content }}</pre>
    </div>
  </Teleport>
</template>
