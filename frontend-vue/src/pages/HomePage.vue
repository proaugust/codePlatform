<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

type DocFile = { key: string; title: string; path: string; content: string }
type Status = { has_docs: boolean; file_count: number; root: string }
type GenerateResult = { root: string; files: string[]; used_docs: boolean }
type RestartResult = { ok: boolean; message?: string; backend?: Record<string, unknown>; frontend?: Record<string, unknown> | null }
type FrontendStartResult = {
  ok: boolean
  started?: boolean
  already_running?: boolean
  port?: number
  url?: string
  message?: string
}
type RunLogItem = {
  id: number
  at: string
  kind: 'backend' | 'frontend' | 'info' | 'error'
  title: string
  message: string
  detail?: string
  url?: string
}
type Msg = { role: string; content: string; at?: string | null }
type Conclusion = {
  summary: string
  goals: string[]
  scope: string[]
  out_of_scope: string[]
  nfr: string[]
  open_questions: string[]
}
type Elicitation = {
  session_id: string
  lang: string
  status: string
  messages: Msg[]
  conclusion: Conclusion | null
  created_at?: string | null
  updated_at?: string | null
  confirmed_at?: string | null
}
type SessionItem = {
  session_id: string
  status?: string | null
  updated_at?: string | null
  summary?: string
  message_count?: number
}

const TARGET = 'java'
const DRAFT_KEY = `elicit_draft_${TARGET}`
const BACKEND_PORT = 8070
const FRONTEND_PORT = 5175
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`

const docs = ref<DocFile[]>([])
const activeDoc = ref(0)
const status = ref<Status | null>(null)
const result = ref<GenerateResult | null>(null)
const error = ref('')
const analyzing = ref(false)
const generating = ref(false)
const chatting = ref(false)
const concluding = ref(false)
const confirming = ref(false)
const restarting = ref(false)
const startingBackend = ref(false)
const startingFrontend = ref(false)
const readyToConclude = ref(false)
const pipelineNote = ref('')
const restartInfo = ref<RestartResult | null>(null)
const frontendStartInfo = ref<FrontendStartResult | null>(null)
const runLogs = ref<RunLogItem[]>([])
const runLogOpen = ref(true)
const consoleOpen = ref(true)
const backendLog = ref('')
const frontendLog = ref('')
const backendListening = ref(false)
const frontendListening = ref(false)
const refreshingLogs = ref(false)
let runLogSeq = 0

function pushRunLog(item: Omit<RunLogItem, 'id' | 'at'>) {
  runLogSeq += 1
  runLogs.value = [
    {
      id: runLogSeq,
      at: new Date().toLocaleTimeString(),
      ...item,
    },
    ...runLogs.value,
  ].slice(0, 30)
  runLogOpen.value = true
}

/** 手动/启动成功后：只提取一次日志文件内容，不轮询 */
async function refreshConsoleLogs() {
  refreshingLogs.value = true
  consoleOpen.value = true
  try {
    const [beRes, feRes] = await Promise.all([
      fetch(`/api/agent/${TARGET}/runtime/logs?kind=backend`),
      fetch(`/api/agent/${TARGET}/runtime/logs?kind=frontend`),
    ])
    const be = await beRes.json()
    const fe = await feRes.json()
    if (beRes.ok && typeof be.text === 'string') {
      backendLog.value = be.text || '（日志文件为空）'
      backendListening.value = !!be.listening
    } else {
      backendLog.value = `拉取失败: ${detailOf(be)}\n若为 Not Found，请先重启 Python Agent（8001）。`
    }
    if (feRes.ok && typeof fe.text === 'string') {
      frontendLog.value = fe.text || '（日志文件为空）'
      frontendListening.value = !!fe.listening
    } else {
      frontendLog.value = `拉取失败: ${detailOf(fe)}`
    }
  } catch (e) {
    backendLog.value = `拉取日志异常: ${String(e)}`
  } finally {
    refreshingLogs.value = false
  }
}

const elicitation = ref<Elicitation | null>(null)
const sessions = ref<SessionItem[]>([])
const input = ref('')
const conclusionEdit = ref<Conclusion>({
  summary: '',
  goals: [],
  scope: [],
  out_of_scope: [],
  nfr: [],
  open_questions: [],
})
const showAdvanced = ref(false)
const advancedSpec = ref('')

const messages = computed(() => elicitation.value?.messages || [])
const elicitStatus = computed(() => elicitation.value?.status || 'drafting')
const canChat = computed(() => elicitStatus.value !== 'confirmed' && !chatting.value)
const canConclude = computed(
  () => messages.value.some((m) => m.role === 'user') && elicitStatus.value !== 'confirmed' && !concluding.value,
)
const canConfirm = computed(
  () =>
    (elicitStatus.value === 'concluded' || !!conclusionEdit.value.summary.trim()) &&
    elicitStatus.value !== 'confirmed' &&
    !confirming.value &&
    !generating.value &&
    !restarting.value,
)
const busy = computed(
  () =>
    confirming.value ||
    generating.value ||
    restarting.value ||
    analyzing.value ||
    startingBackend.value ||
    startingFrontend.value,
)
/** 已确认（或已有文档）时可手动再生成/增量修改；未确认但可确认时走「确认并生成」 */
const canGenerate = computed(
  () =>
    (elicitStatus.value === 'confirmed' || docs.value.length > 0 || !!status.value?.has_docs) &&
    !busy.value,
)
const canConfirmAndGenerate = computed(() => canConfirm.value && !busy.value)

function detailOf(data: unknown) {
  if (data && typeof data === 'object' && 'detail' in data) {
    const d = (data as { detail: unknown }).detail
    return typeof d === 'string' ? d : JSON.stringify(d)
  }
  return JSON.stringify(data)
}

function listToText(items: string[]) {
  return (items || []).join('\n')
}

function textToList(text: string) {
  return text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
}

function applyElicitation(data: Elicitation) {
  elicitation.value = data
  if (data.conclusion) {
    conclusionEdit.value = {
      summary: data.conclusion.summary || '',
      goals: [...(data.conclusion.goals || [])],
      scope: [...(data.conclusion.scope || [])],
      out_of_scope: [...(data.conclusion.out_of_scope || [])],
      nfr: [...(data.conclusion.nfr || [])],
      open_questions: [...(data.conclusion.open_questions || [])],
    }
  }
}

function saveDraft() {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ input: input.value }))
  } catch {
    /* ignore */
  }
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return
    const data = JSON.parse(raw) as { input?: string }
    if (typeof data.input === 'string' && data.input && !input.value) {
      input.value = data.input
    }
  } catch {
    /* ignore */
  }
}

function clearDraft() {
  try {
    localStorage.removeItem(DRAFT_KEY)
  } catch {
    /* ignore */
  }
}

watch(input, () => saveDraft())

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

async function loadElicit() {
  const r = await fetch(`/api/agent/${TARGET}/elicit`)
  const data = await r.json()
  if (!r.ok) throw new Error(detailOf(data))
  applyElicitation(data.elicitation)
}

async function loadSessions() {
  try {
    const r = await fetch(`/api/agent/${TARGET}/elicit/sessions`)
    const data = await r.json()
    if (r.ok && Array.isArray(data.sessions)) sessions.value = data.sessions
  } catch {
    /* ignore */
  }
}

onMounted(async () => {
  loadDraft()
  error.value = ''
  try {
    await Promise.all([refreshStatus(), loadDocs(), loadElicit(), loadSessions()])
  } catch (e) {
    error.value = String(e)
  }
})

async function onSend() {
  const text = input.value.trim()
  if (!text || !canChat.value) return
  chatting.value = true
  error.value = ''
  try {
    const r = await fetch('/api/agent/elicit/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: TARGET, content: text }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    readyToConclude.value = !!data.ready_to_conclude
    input.value = ''
    clearDraft()
  } catch (e) {
    error.value = String(e)
  } finally {
    chatting.value = false
  }
}

async function onConclude() {
  concluding.value = true
  error.value = ''
  try {
    const r = await fetch('/api/agent/elicit/conclude', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: TARGET }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    readyToConclude.value = false
  } catch (e) {
    error.value = String(e)
  } finally {
    concluding.value = false
  }
}

async function onRestart(opts?: { withFrontend?: boolean }) {
  const withFrontend = opts?.withFrontend !== false
  restarting.value = true
  pipelineNote.value = withFrontend ? '正在重启 Java 后端 + Vue 前端…' : '正在重启 Java 后端…'
  pushRunLog({
    kind: 'info',
    title: withFrontend ? '重启后端+前端' : '启动/重启后端',
    message: pipelineNote.value,
  })
  try {
    // 优先稳定入口；旧进程若无此路由再回退 /{target}/restart
    let r = await fetch('/api/agent/runtime/start-backend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: TARGET, with_frontend: withFrontend }),
    })
    if (r.status === 404) {
      const q = withFrontend ? '' : '?with_frontend=false'
      r = await fetch(`/api/agent/${TARGET}/restart${q}`, { method: 'POST' })
    }
    const data = await r.json()
    if (!r.ok) {
      const detail = detailOf(data)
      if (r.status === 404 || /not found/i.test(detail)) {
        throw new Error(
          '启动接口 404：当前 Python Agent（8001）未加载新路由。请在 Cursor 里停止并重新 F5 启动 backend，再点「启动后端」。',
        )
      }
      throw new Error(detail)
    }
    restartInfo.value = data
    const msg = data.message || '产物已重启'
    pipelineNote.value = msg
    const backend = (data.backend || {}) as Record<string, unknown>
    pushRunLog({
      kind: 'backend',
      title: 'Java 后端',
      message: msg,
      detail: JSON.stringify(data, null, 2),
      url: typeof backend.url === 'string' ? backend.url : BACKEND_URL,
    })
    if (data.frontend) {
      const fe = data.frontend as Record<string, unknown>
      pushRunLog({
        kind: 'frontend',
        title: 'Vue 前端',
        message: String(fe.message || '前端已处理'),
        detail: JSON.stringify(fe, null, 2),
        url: typeof fe.url === 'string' ? fe.url : FRONTEND_URL,
      })
    }
    await refreshConsoleLogs()
    return data as RestartResult
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
    pushRunLog({ kind: 'error', title: '后端启动失败', message: String(e) })
    throw e
  } finally {
    restarting.value = false
  }
}

async function onStartBackend() {
  startingBackend.value = true
  error.value = ''
  frontendStartInfo.value = null
  pipelineNote.value = '正在启动 Java 后端…'
  try {
    const data = await onRestart({ withFrontend: false })
    pipelineNote.value = data.message || `Java 后端已启动：${BACKEND_URL}`
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
  } finally {
    startingBackend.value = false
  }
}

async function onStartFrontend() {
  startingFrontend.value = true
  error.value = ''
  frontendStartInfo.value = null
  pipelineNote.value = '正在启动 Java Vue 前端…'
  pushRunLog({ kind: 'info', title: '启动前端', message: pipelineNote.value })
  try {
    const r = await fetch(`/api/agent/${TARGET}/frontend/start`, { method: 'POST' })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    frontendStartInfo.value = data
    const msg = data.message || `Vue 前端已启动：${FRONTEND_URL}`
    pipelineNote.value = msg
    pushRunLog({
      kind: 'frontend',
      title: 'Vue 前端',
      message: msg,
      detail: JSON.stringify(data, null, 2),
      url: typeof data.url === 'string' ? data.url : FRONTEND_URL,
    })
    await refreshConsoleLogs()
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
    pushRunLog({ kind: 'error', title: '前端启动失败', message: String(e) })
  } finally {
    startingFrontend.value = false
  }
}

async function onGenerate(opts?: { restart?: boolean }) {
  generating.value = true
  error.value = ''
  result.value = null
  restartInfo.value = null
  pipelineNote.value = '正在生成代码…'
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
    if (opts?.restart !== false) {
      generating.value = false
      await onRestart()
    } else {
      pipelineNote.value = '代码已生成'
    }
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
    throw e
  } finally {
    generating.value = false
  }
}

async function onConfirm() {
  confirming.value = true
  analyzing.value = true
  error.value = ''
  result.value = null
  restartInfo.value = null
  pipelineNote.value = '确认结论并生成文档…'
  try {
    const r = await fetch('/api/agent/elicit/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: TARGET, conclusion: conclusionEdit.value }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    docs.value = data.analyze?.files || []
    activeDoc.value = 0
    await Promise.all([refreshStatus(), loadSessions()])
    confirming.value = false
    analyzing.value = false
    await onGenerate({ restart: true })
    pipelineNote.value = '完成：文档 → 代码 → 重启'
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
  } finally {
    confirming.value = false
    analyzing.value = false
    generating.value = false
    restarting.value = false
  }
}

async function onNewSession() {
  error.value = ''
  try {
    const r = await fetch('/api/agent/elicit/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: TARGET }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    conclusionEdit.value = {
      summary: '',
      goals: [],
      scope: [],
      out_of_scope: [],
      nfr: [],
      open_questions: [],
    }
    readyToConclude.value = false
    input.value = ''
    clearDraft()
    await loadSessions()
  } catch (e) {
    error.value = String(e)
  }
}

async function onRestore(sessionId: string) {
  error.value = ''
  try {
    const r = await fetch(`/api/agent/elicit/sessions/${sessionId}/restore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: TARGET }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    readyToConclude.value = false
    await loadSessions()
  } catch (e) {
    error.value = String(e)
  }
}

async function onAnalyzeAdvanced() {
  analyzing.value = true
  error.value = ''
  result.value = null
  try {
    const r = await fetch('/api/agent/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spec: advancedSpec.value, target: TARGET }),
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

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    onSend()
  }
}
</script>

<template>
  <section class="page page-wide workspace">
    <header class="topbar">
      <div class="topbar-left">
        <span class="brand">Code Platform · Vue</span>
        <span class="muted topbar-meta">
          Java 产物 · 后端 {{ BACKEND_PORT }} · 业务前端 {{ FRONTEND_PORT }}
          <template v-if="elicitation"> · {{ elicitation.session_id }} · {{ elicitStatus }}</template>
        </span>
      </div>
      <div class="topbar-right">
        <button type="button" class="btn-start" :disabled="busy" @click="onStartBackend">
          {{ startingBackend ? '启动中…' : '启动后端' }}
        </button>
        <button type="button" class="btn-start btn-start-fe" :disabled="busy" @click="onStartFrontend">
          {{ startingFrontend ? '启动中…' : '启动前端' }}
        </button>
        <a class="link-pill" :href="BACKEND_URL" target="_blank" rel="noreferrer">打开后端</a>
        <a class="link-pill" :href="FRONTEND_URL" target="_blank" rel="noreferrer">打开前端</a>
      </div>
    </header>

    <details class="console-panel" :open="consoleOpen" @toggle="consoleOpen = ($event.target as HTMLDetailsElement).open">
      <summary>
        启动控制台（日志文件）
        <span class="muted">
          后端 {{ backendListening ? '已监听' : '未就绪' }} · 前端 {{ frontendListening ? '已监听' : '未就绪' }}
          · 不自动刷新 · 点击展开/隐藏
        </span>
      </summary>
      <div class="console-toolbar">
        <button type="button" class="btn-ghost" :disabled="refreshingLogs" @click="refreshConsoleLogs">
          {{ refreshingLogs ? '提取中…' : '刷新日志（提取一次）' }}
        </button>
        <span class="muted">文件：auto_code/java/logs/backend.log · frontend.log</span>
      </div>
      <p v-if="pipelineNote" class="muted run-log-note">{{ pipelineNote }}</p>
      <div class="console-grid">
        <div class="console-card">
          <div class="console-card-head">
            <strong>Java 后端 :{{ BACKEND_PORT }}</strong>
            <span :class="backendListening ? 'ok' : 'bad'">{{ backendListening ? 'LISTEN' : 'DOWN' }}</span>
            <a :href="BACKEND_URL" target="_blank" rel="noreferrer">打开</a>
          </div>
          <pre class="console-out">{{ backendLog || '（启动成功后自动提取一次；也可点「刷新日志」）' }}</pre>
        </div>
        <div class="console-card">
          <div class="console-card-head">
            <strong>Vue 前端 :{{ FRONTEND_PORT }}</strong>
            <span :class="frontendListening ? 'ok' : 'bad'">{{ frontendListening ? 'LISTEN' : 'DOWN' }}</span>
            <a :href="FRONTEND_URL" target="_blank" rel="noreferrer">打开</a>
          </div>
          <pre class="console-out">{{ frontendLog || '（启动成功后自动提取一次；也可点「刷新日志」）' }}</pre>
        </div>
      </div>
    </details>

    <details class="run-log-panel" :open="runLogOpen" @toggle="runLogOpen = ($event.target as HTMLDetailsElement).open">
      <summary>
        运行记录
        <span class="muted">（{{ runLogs.length }}）启动请求结果，点击展开或隐藏</span>
      </summary>
      <div v-if="!runLogs.length" class="muted run-log-empty">暂无记录。</div>
      <ul v-else class="run-log-list">
        <li v-for="log in runLogs" :key="log.id" :class="['run-log-item', `kind-${log.kind}`]">
          <div class="run-log-head">
            <strong>{{ log.title }}</strong>
            <span class="muted">{{ log.at }}</span>
            <a v-if="log.url" :href="log.url" target="_blank" rel="noreferrer">打开</a>
          </div>
          <div class="run-log-msg">{{ log.message }}</div>
          <pre v-if="log.detail" class="run-log-detail">{{ log.detail }}</pre>
        </li>
      </ul>
    </details>

    <div class="elicit-layout">
      <aside class="history-panel">
        <div class="history-head">
          <strong>历史记录</strong>
          <button type="button" class="btn-ghost" @click="onNewSession">新开窗口</button>
        </div>
        <ul v-if="sessions.length" class="session-list">
          <li v-for="s in sessions" :key="s.session_id">
            <button
              type="button"
              class="session-item"
              :class="{ active: elicitation?.session_id === s.session_id }"
              @click="onRestore(s.session_id)"
            >
              <span class="session-id">{{ s.session_id }}</span>
              <span class="muted">{{ s.summary || `消息 ${s.message_count || 0}` }}</span>
            </button>
          </li>
        </ul>
        <p v-else class="muted">暂无归档会话</p>
      </aside>

      <div class="chat-panel">
        <div class="chat-panel-head">
          <strong>聊天窗口</strong>
          <span class="muted">Enter 发送 · Shift+Enter 换行</span>
        </div>
        <div class="chat-log">
          <div v-if="!messages.length" class="muted chat-empty">
            描述你想生成的系统（目标、核心对象、主要接口）。助手会追问澄清，不会直接写代码。
          </div>
          <div
            v-for="(m, i) in messages"
            :key="i"
            :class="m.role === 'user' ? 'bubble user' : 'bubble assistant'"
          >
            <div class="bubble-role">{{ m.role === 'user' ? '你' : '澄清助手' }}</div>
            <div class="bubble-body">{{ m.content }}</div>
          </div>
        </div>

        <div class="chat-input-row">
          <textarea
            v-model="input"
            class="chat-input"
            rows="3"
            placeholder="输入需求澄清…（Enter 发送，Shift+Enter 换行）"
            :disabled="!canChat"
            @keydown="onKeydown"
          />
          <div class="chat-actions">
            <button type="button" :disabled="!input.trim() || !canChat" @click="onSend">
              {{ chatting ? '发送中…' : '发送' }}
            </button>
            <button type="button" class="btn-secondary" :disabled="!canConclude" @click="onConclude">
              {{ concluding ? '总结中…' : '总结' }}
            </button>
            <span v-if="readyToConclude" class="muted">可总结</span>
          </div>
        </div>

        <div class="chat-gen-row">
          <button
            v-if="canConfirmAndGenerate || (canConfirm && busy)"
            type="button"
            class="btn-gen"
            :disabled="!canConfirmAndGenerate"
            title="确认结论 → 写文档 → 生成/修改代码 → 重启"
            @click="onConfirm"
          >
            {{ busy ? pipelineNote || '处理中…' : '确认并生成/修改代码' }}
          </button>
          <button
            v-else
            type="button"
            class="btn-gen"
            :disabled="!canGenerate"
            title="需先聊天并「总结 → 确认」；已确认后可再次生成或增量修改"
            @click="onGenerate({ restart: true })"
          >
            {{ generating ? '生成中…' : '生成/修改代码' }}
          </button>
          <span class="muted">
            流程：聊天 → 总结 → 确认并生成
            <template v-if="status"> · 文档 {{ status.has_docs ? '已就绪' : '未生成' }}</template>
          </span>
        </div>
      </div>
    </div>

    <div v-if="conclusionEdit.summary || elicitStatus === 'concluded' || elicitStatus === 'confirmed'" class="result">
      <h2>结论（可编辑；确认入口在聊天框下方）</h2>
      <label class="label" for="c-summary">摘要</label>
      <textarea
        id="c-summary"
        v-model="conclusionEdit.summary"
        class="concl-area"
        rows="3"
        :disabled="elicitStatus === 'confirmed'"
      />
      <div class="concl-grid">
        <div>
          <label class="label">目标（每行一条）</label>
          <textarea
            class="concl-area"
            rows="4"
            :value="listToText(conclusionEdit.goals)"
            :disabled="elicitStatus === 'confirmed'"
            @input="conclusionEdit.goals = textToList(($event.target as HTMLTextAreaElement).value)"
          />
        </div>
        <div>
          <label class="label">范围</label>
          <textarea
            class="concl-area"
            rows="4"
            :value="listToText(conclusionEdit.scope)"
            :disabled="elicitStatus === 'confirmed'"
            @input="conclusionEdit.scope = textToList(($event.target as HTMLTextAreaElement).value)"
          />
        </div>
        <div>
          <label class="label">不在范围</label>
          <textarea
            class="concl-area"
            rows="4"
            :value="listToText(conclusionEdit.out_of_scope)"
            :disabled="elicitStatus === 'confirmed'"
            @input="conclusionEdit.out_of_scope = textToList(($event.target as HTMLTextAreaElement).value)"
          />
        </div>
        <div>
          <label class="label">非功能</label>
          <textarea
            class="concl-area"
            rows="4"
            :value="listToText(conclusionEdit.nfr)"
            :disabled="elicitStatus === 'confirmed'"
            @input="conclusionEdit.nfr = textToList(($event.target as HTMLTextAreaElement).value)"
          />
        </div>
      </div>
    </div>

    <details class="advanced" :open="showAdvanced" @toggle="showAdvanced = ($event.target as HTMLDetailsElement).open">
      <summary>高级：直接粘贴需求（跳过澄清）</summary>
      <textarea v-model="advancedSpec" class="spec-area" spellcheck="false" />
      <div class="row">
        <button type="button" :disabled="analyzing || !advancedSpec.trim()" @click="onAnalyzeAdvanced">
          {{ analyzing ? '分析中…' : '生成文档' }}
        </button>
      </div>
    </details>

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
