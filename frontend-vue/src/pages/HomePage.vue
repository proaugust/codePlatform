<script setup lang="ts">
import { onMounted, ref } from 'vue'

type DocFile = { key: string; title: string; path: string; content: string }
type Status = { has_docs: boolean; file_count: number; root: string }
type GenerateResult = { root: string; files: string[]; used_docs: boolean }

const TARGET = 'go'

const SAMPLE = `做一个简易任务 API：
- GET /health
- GET /tasks 列表
- POST /tasks 创建（title）
- GET /tasks/{id}
`

const spec = ref(SAMPLE)
const docs = ref<DocFile[]>([])
const activeDoc = ref(0)
const status = ref<Status | null>(null)
const result = ref<GenerateResult | null>(null)
const error = ref('')
const analyzing = ref(false)
const generating = ref(false)

function detailOf(data: unknown) {
  if (data && typeof data === 'object' && 'detail' in data) {
    const d = (data as { detail: unknown }).detail
    return typeof d === 'string' ? d : JSON.stringify(d)
  }
  return JSON.stringify(data)
}

async function refreshStatus() {
  try {
    status.value = await (await fetch(`/api/agent/${TARGET}/status`)).json()
  } catch (e) {
    error.value = String(e)
  }
}

async function loadDocs() {
  try {
    const d = await (await fetch(`/api/agent/${TARGET}/docs`)).json()
    if (Array.isArray(d.files)) docs.value = d.files
  } catch {
    /* ignore */
  }
}

onMounted(() => {
  refreshStatus()
  loadDocs()
})

async function onAnalyze() {
  analyzing.value = true
  error.value = ''
  result.value = null
  try {
    const r = await fetch('/api/agent/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spec: spec.value, target: TARGET }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    docs.value = data.files || []
    activeDoc.value = 0
    await refreshStatus()
  } catch (e) {
    error.value = String(e)
  } finally {
    analyzing.value = false
  }
}

async function onGenerate() {
  generating.value = true
  error.value = ''
  result.value = null
  try {
    const r = await fetch('/api/agent/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: TARGET, use_docs: true }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    result.value = data
    await refreshStatus()
  } catch (e) {
    error.value = String(e)
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <section class="page">
    <header class="page-header">
      <h1>需求 → Agent 生成（Go 产物）</h1>
      <p>
        本页只调用 Python <code>/api/agent/*</code>。生成目标 <code>target=go</code>，代码写入
        <code>auto_code/go</code>
        <template v-if="status"> · 当前文件 {{ status.file_count }}</template>
      </p>
    </header>

    <label class="label" for="spec">原始需求</label>
    <textarea id="spec" class="spec-area" v-model="spec" spellcheck="false" />

    <div class="row">
      <button type="button" :disabled="analyzing || !spec.trim()" @click="onAnalyze">
        {{ analyzing ? '分析中…' : '生成文档' }}
      </button>
      <button type="button" :disabled="generating || docs.length === 0" @click="onGenerate">
        {{ generating ? '生成中…' : '生成代码' }}
      </button>
      <span v-if="status" class="muted">文档：{{ status.has_docs ? '已就绪' : '未生成' }}</span>
    </div>

    <pre v-if="error" class="error">{{ error }}</pre>

    <div v-if="docs.length" class="result">
      <h2>需求文档（Agent 产出）</h2>
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
      <p class="muted"><code>{{ docs[activeDoc]?.path }}</code></p>
      <pre class="doc-body">{{ docs[activeDoc]?.content }}</pre>
    </div>

    <div v-if="result" class="result">
      <h2>代码已写入</h2>
      <p><code>{{ result.root }}</code></p>
      <ul>
        <li v-for="f in result.files" :key="f"><code>{{ f }}</code></li>
      </ul>
    </div>
  </section>
</template>
