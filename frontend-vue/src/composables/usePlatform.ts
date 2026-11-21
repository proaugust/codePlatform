import { computed, onMounted, ref, watch } from 'vue'

export type DocFile = { key: string; title: string; path: string; content: string }
export type Status = { has_docs: boolean; file_count: number; root: string }
export type GenerateResult = { root: string; files: string[]; used_docs: boolean }
export type RestartResult = {
  ok: boolean
  message?: string
  backend?: Record<string, unknown>
  frontend?: Record<string, unknown> | null
}
export type FrontendStartResult = {
  ok: boolean
  started?: boolean
  already_running?: boolean
  port?: number
  url?: string
  message?: string
}
export type RunLogItem = {
  id: number
  at: string
  kind: 'backend' | 'frontend' | 'info' | 'error'
  title: string
  message: string
  detail?: string
  url?: string
}
export type Msg = { role: string; content: string; at?: string | null; mode?: string | null }
export type Conclusion = {
  summary: string
  goals: string[]
  scope: string[]
  out_of_scope: string[]
  nfr: string[]
  open_questions: string[]
}
export type LastPlan = { summary?: string; task_count?: number; at?: string | null }
export type Elicitation = {
  session_id: string
  lang: string
  status: string
  messages: Msg[]
  conclusion: Conclusion | null
  rolling_summary?: string
  plan_ready?: boolean
  last_plan?: LastPlan | null
  created_at?: string | null
  updated_at?: string | null
  confirmed_at?: string | null
  closed_at?: string | null
}
export type SessionItem = {
  session_id: string
  status?: string | null
  updated_at?: string | null
  summary?: string
  message_count?: number
  plan_ready?: boolean
}

export type Lang = 'java' | 'go'
/** 产物文件树浏览目标（与 java/go 同级含共用 frontend） */
export type TreeTarget = Lang | 'frontend'
export type LangMeta = {
  lang: Lang
  backend_port: number
  frontend_port: number | null
  has_frontend: boolean
}

const TARGET_KEY = 'platform_target'
const FALLBACK_LANGS: LangMeta[] = [
  { lang: 'java', backend_port: 8070, frontend_port: 5175, has_frontend: true },
  { lang: 'go', backend_port: 8072, frontend_port: 5175, has_frontend: true },
]

const target = ref<Lang>('java')
const langMetas = ref<LangMeta[]>(FALLBACK_LANGS)

const currentMeta = computed(
  () => langMetas.value.find((m) => m.lang === target.value) || FALLBACK_LANGS[0],
)
const BACKEND_PORT = computed(() => currentMeta.value.backend_port)
const FRONTEND_PORT = computed(() => currentMeta.value.frontend_port)
const hasFrontend = computed(() => !!currentMeta.value.has_frontend)
/** 打开健康检查，避免根路径无映射被生成代码打成 500 */
const BACKEND_URL = computed(() => `http://127.0.0.1:${BACKEND_PORT.value}/health`)
const FRONTEND_URL = computed(() =>
  FRONTEND_PORT.value ? `http://127.0.0.1:${FRONTEND_PORT.value}` : '',
)
const targetLabel = computed(() => (target.value === 'java' ? 'Java' : 'Go'))
const draftKey = computed(() => `elicit_draft_${target.value}`)
const logPathHint = computed(() =>
  hasFrontend.value
    ? `auto_code/${target.value}/logs/backend.log · frontend.log`
    : `auto_code/${target.value}/logs/backend.log`,
)

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
const planning = ref(false)
const executing = ref(false)
const restarting = ref(false)
const startingBackend = ref(false)
const startingFrontend = ref(false)
const stoppingBackend = ref(false)
const stoppingFrontend = ref(false)
const readyToConclude = ref(false)
const readyToPlan = ref(false)
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
const maxTurns = ref(20)
const treeIndentCh = ref(2)
const platformSettings = ref<{
  max_turns: number
  min_max_turns: number
  max_max_turns: number
  tree_indent_ch: number
  min_tree_indent_ch: number
  max_tree_indent_ch: number
  llm_base_url: string
  llm_model: string
  has_llm_api_key: boolean
  llm_api_key_masked: string
  auto_code_root: string
  default_lang: string
} | null>(null)
const closingSession = ref(false)
const deletingSessionId = ref<string | null>(null)
const savingSettings = ref(false)

const messages = computed(() => elicitation.value?.messages || [])
const elicitStatus = computed(() => elicitation.value?.status || 'drafting')
const planReady = computed(() => !!elicitation.value?.plan_ready)
const rollingSummary = computed(() => elicitation.value?.rolling_summary || '')
const sessionClosed = computed(() => elicitStatus.value === 'closed')
const canChat = computed(() => !sessionClosed.value && !chatting.value && !planning.value && !executing.value)
const canConclude = computed(
  () =>
    (messages.value.some((m) => m.role === 'user') || !!rollingSummary.value) &&
    !sessionClosed.value &&
    !concluding.value,
)
const busy = computed(
  () =>
    confirming.value ||
    planning.value ||
    executing.value ||
    generating.value ||
    restarting.value ||
    analyzing.value ||
    startingBackend.value ||
    startingFrontend.value ||
    stoppingBackend.value ||
    stoppingFrontend.value,
)
const canPlan = computed(
  () =>
    !sessionClosed.value &&
    !busy.value &&
    (messages.value.some((m) => m.role === 'user') ||
      !!input.value.trim() ||
      !!conclusionEdit.value.summary.trim() ||
      !!rollingSummary.value),
)
const canExecute = computed(() => !sessionClosed.value && planReady.value && !busy.value)
const canConfirm = computed(() => canPlan.value)
const canGenerate = computed(() => canExecute.value)
const canConfirmAndGenerate = computed(() => canPlan.value)

let bootstrapped = false
let draftWatchBound = false

function isLang(v: unknown): v is Lang {
  return v === 'java' || v === 'go'
}

function isTreeTarget(v: unknown): v is TreeTarget {
  return v === 'java' || v === 'go' || v === 'frontend'
}

function treeTargetLabel(t: TreeTarget): string {
  if (t === 'java') return 'Java'
  if (t === 'go') return 'Go'
  return 'Frontend'
}

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

async function refreshConsoleLogs() {
  refreshingLogs.value = true
  consoleOpen.value = true
  const t = target.value
  try {
    const beRes = await fetch(`/api/agent/${t}/runtime/logs?kind=backend`)
    const be = await beRes.json()
    if (beRes.ok && typeof be.text === 'string') {
      backendLog.value = be.text || '（日志文件为空）'
      backendListening.value = !!be.listening
    } else {
      backendLog.value = `拉取失败: ${detailOf(be)}\n若为 Not Found，请先重启 Python Agent（8001）。`
    }
    if (hasFrontend.value) {
      const feRes = await fetch(`/api/agent/${t}/runtime/logs?kind=frontend`)
      const fe = await feRes.json()
      if (feRes.ok && typeof fe.text === 'string') {
        frontendLog.value = fe.text || '（日志文件为空）'
        frontendListening.value = !!fe.listening
      } else {
        frontendLog.value = `拉取失败: ${detailOf(fe)}`
      }
    } else {
      frontendLog.value = '（当前语言无配套前端）'
      frontendListening.value = false
    }
  } catch (e) {
    backendLog.value = `拉取日志异常: ${String(e)}`
  } finally {
    refreshingLogs.value = false
  }
}

async function clearRuntimeLogs(kind: 'backend' | 'frontend') {
  refreshingLogs.value = true
  const t = target.value
  try {
    const r = await fetch(`/api/agent/${t}/runtime/logs?kind=${kind}`, { method: 'DELETE' })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    const text = typeof data.text === 'string' ? data.text || '（日志已清空）' : '（日志已清空）'
    if (kind === 'backend') {
      backendLog.value = text
      backendListening.value = !!data.listening
    } else {
      frontendLog.value = text
      frontendListening.value = !!data.listening
    }
  } catch (e) {
    error.value = String(e)
  } finally {
    refreshingLogs.value = false
  }
}

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
    localStorage.setItem(draftKey.value, JSON.stringify({ input: input.value }))
  } catch {
    /* ignore */
  }
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(draftKey.value)
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
    localStorage.removeItem(draftKey.value)
  } catch {
    /* ignore */
  }
}

async function refreshStatus() {
  try {
    status.value = await (await fetch(`/api/agent/${target.value}/status`)).json()
  } catch (e) {
    error.value = String(e)
  }
}

async function loadDocs() {
  try {
    const d = await (await fetch(`/api/agent/${target.value}/docs`)).json()
    if (Array.isArray(d.files)) docs.value = d.files
  } catch {
    /* ignore */
  }
}

async function loadElicit() {
  const r = await fetch(`/api/agent/${target.value}/elicit`)
  const data = await r.json()
  if (!r.ok) throw new Error(detailOf(data))
  applyElicitation(data.elicitation)
}

async function loadSessions() {
  try {
    const r = await fetch(`/api/agent/${target.value}/elicit/sessions`)
    const data = await r.json()
    if (r.ok && Array.isArray(data.sessions)) sessions.value = data.sessions
  } catch {
    /* ignore */
  }
}

function applyPlatformSettings(data: {
  max_turns?: number
  tree_indent_ch?: number
  [key: string]: unknown
}) {
  platformSettings.value = data as typeof platformSettings.value
  if (typeof data.max_turns === 'number') maxTurns.value = data.max_turns
  if (typeof data.tree_indent_ch === 'number') treeIndentCh.value = data.tree_indent_ch
}

async function loadPlatformSettings() {
  try {
    const r = await fetch('/api/agent/settings')
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyPlatformSettings(data)
  } catch (e) {
    error.value = String(e)
  }
}

async function savePlatformSettings(patch: {
  max_turns?: number
  tree_indent_ch?: number
  llm_base_url?: string
  llm_api_key?: string
  llm_model?: string
}) {
  savingSettings.value = true
  error.value = ''
  try {
    const r = await fetch('/api/agent/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyPlatformSettings(data)
  } catch (e) {
    error.value = String(e)
  } finally {
    savingSettings.value = false
  }
}

async function saveMaxTurns(next: number) {
  await savePlatformSettings({ max_turns: next })
}

async function loadWorkspace() {
  input.value = ''
  loadDraft()
  await Promise.all([refreshStatus(), loadDocs(), loadElicit(), loadSessions(), loadPlatformSettings()])
  backendLog.value = ''
  frontendLog.value = ''
  backendListening.value = false
  frontendListening.value = false
}

async function resolveTargetFromMeta() {
  let defaultLang: Lang = 'java'
  try {
    const r = await fetch('/api/agent/meta')
    const data = await r.json()
    if (r.ok) {
      if (Array.isArray(data.langs) && data.langs.length) {
        // 与本地 FALLBACK 合并：旧后端 meta 可能仍把 go.has_frontend 标 false
        langMetas.value = data.langs
          .filter((m: LangMeta) => isLang(m.lang))
          .map((m: LangMeta) => {
            const fb = FALLBACK_LANGS.find((x) => x.lang === m.lang)
            return {
              lang: m.lang,
              backend_port: m.backend_port || fb?.backend_port || 8070,
              frontend_port: m.frontend_port ?? fb?.frontend_port ?? null,
              has_frontend: Boolean(m.has_frontend || fb?.has_frontend),
            }
          })
      }
      if (isLang(data.default_lang)) defaultLang = data.default_lang
    }
  } catch {
    /* 用本地 fallback */
  }
  let next: Lang = defaultLang
  try {
    const saved = localStorage.getItem(TARGET_KEY)
    if (isLang(saved)) next = saved
  } catch {
    /* ignore */
  }
  target.value = next
}

async function switchTarget(next: Lang) {
  if (next === target.value || busy.value) return
  saveDraft()
  target.value = next
  try {
    localStorage.setItem(TARGET_KEY, next)
  } catch {
    /* ignore */
  }
  error.value = ''
  result.value = null
  restartInfo.value = null
  frontendStartInfo.value = null
  pipelineNote.value = ''
  readyToConclude.value = false
  readyToPlan.value = false
  elicitation.value = null
  sessions.value = []
  docs.value = []
  conclusionEdit.value = {
    summary: '',
    goals: [],
    scope: [],
    out_of_scope: [],
    nfr: [],
    open_questions: [],
  }
  try {
    await loadWorkspace()
  } catch (e) {
    error.value = String(e)
  }
}

async function bootstrapPlatform() {
  if (bootstrapped) return
  bootstrapped = true
  if (!draftWatchBound) {
    draftWatchBound = true
    watch(input, () => saveDraft())
  }
  error.value = ''
  try {
    await resolveTargetFromMeta()
    await loadWorkspace()
  } catch (e) {
    error.value = String(e)
  }
}

async function onSend() {
  const text = input.value.trim()
  if (!text || !canChat.value) return
  chatting.value = true
  error.value = ''
  try {
    const r = await fetch('/api/agent/elicit/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target.value, content: text }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    readyToConclude.value = !!(data.ready_to_conclude || data.ready_to_plan)
    readyToPlan.value = !!(data.ready_to_plan || data.ready_to_conclude)
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
      body: JSON.stringify({ target: target.value }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    readyToConclude.value = false
    readyToPlan.value = true
  } catch (e) {
    error.value = String(e)
  } finally {
    concluding.value = false
  }
}

async function onPlan() {
  if (!canPlan.value) {
    error.value = sessionClosed.value
      ? '会话已关闭，请先「新开窗口」'
      : '请先输入需求或编辑结论，再点「分析计划」'
    return
  }
  planning.value = true
  analyzing.value = true
  error.value = ''
  result.value = null
  const note = input.value.trim()
  pipelineNote.value = '正在分析计划…'
  pushRunLog({ kind: 'info', title: '分析计划', message: pipelineNote.value })
  try {
    const r = await fetch('/api/agent/elicit/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target: target.value,
        content: note || null,
        conclusion: conclusionEdit.value.summary.trim() ? conclusionEdit.value : null,
      }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    docs.value = data.analyze?.files || []
    activeDoc.value = 0
    readyToConclude.value = false
    readyToPlan.value = false
    if (note) {
      input.value = ''
      clearDraft()
    }
    await Promise.all([refreshStatus(), loadSessions()])
    pipelineNote.value = data.plan_ready ? '计划已就绪，可执行生成' : '计划已处理'
    pushRunLog({
      kind: 'info',
      title: '计划完成',
      message: pipelineNote.value,
      detail: data.elicitation?.last_plan
        ? JSON.stringify(data.elicitation.last_plan, null, 2)
        : undefined,
    })
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
    pushRunLog({ kind: 'error', title: '分析计划失败', message: String(e) })
  } finally {
    planning.value = false
    analyzing.value = false
  }
}

async function onExecute() {
  if (!canExecute.value) {
    error.value = sessionClosed.value
      ? '会话已关闭，请先「新开窗口」'
      : busy.value
        ? '正在执行其它任务，请稍候'
        : '请先点「分析计划」或「分析并改代码」（仅聊天确认不会改代码）'
    pipelineNote.value = error.value
    pushRunLog({ kind: 'error', title: '无法执行生成', message: error.value })
    return
  }
  executing.value = true
  generating.value = true
  error.value = ''
  result.value = null
  restartInfo.value = null
  pipelineNote.value = '正在执行生成代码…'
  pushRunLog({ kind: 'info', title: '执行生成', message: pipelineNote.value })
  try {
    const r = await fetch('/api/agent/elicit/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target.value }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    if (data.generate) result.value = data.generate
    await refreshStatus()
    const smokeMsg =
      data.smoke && typeof data.smoke === 'object' && data.smoke.message
        ? String(data.smoke.message)
        : ''
    pipelineNote.value = smokeMsg
      ? `代码已生成。${smokeMsg}`
      : '代码已生成（未自动启动，请到「运行」页启动）'
    pushRunLog({
      kind: 'info',
      title: '生成完成',
      message: pipelineNote.value,
      detail: data.generate ? JSON.stringify(data.generate, null, 2) : undefined,
    })
  } catch (e) {
    const msg = String(e)
    error.value = msg
    pipelineNote.value = `执行生成失败：${msg}`
    pushRunLog({ kind: 'error', title: '执行生成失败', message: msg, detail: msg })
  } finally {
    executing.value = false
    generating.value = false
  }
}

/** 分析计划 + 执行生成（一键改代码） */
async function onPlanAndExecute() {
  if (!canPlan.value || busy.value) {
    error.value = busy.value
      ? '正在执行其它任务，请稍候'
      : sessionClosed.value
        ? '会话已关闭，请先「新开窗口」'
        : '请先输入需求或编辑结论，再点「分析并改代码」'
    pipelineNote.value = error.value
    return
  }
  await onPlan()
  if (error.value || !planReady.value) {
    if (!error.value) {
      error.value = '计划未就绪，未能继续执行生成'
      pipelineNote.value = error.value
    }
    return
  }
  await onExecute()
}

async function onRestart(opts?: { withFrontend?: boolean }) {
  const withFrontend = opts?.withFrontend !== false && hasFrontend.value
  restarting.value = true
  pipelineNote.value = withFrontend
    ? `正在重启 ${targetLabel.value} 后端 + Vue 前端…`
    : `正在重启 ${targetLabel.value} 后端…`
  pushRunLog({
    kind: 'info',
    title: withFrontend ? '重启后端+前端' : '启动/重启后端',
    message: pipelineNote.value,
  })
  try {
    let r = await fetch('/api/agent/runtime/start-backend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target.value, with_frontend: withFrontend }),
    })
    if (r.status === 404) {
      const q = withFrontend ? '' : '?with_frontend=false'
      r = await fetch(`/api/agent/${target.value}/restart${q}`, { method: 'POST' })
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
    if (typeof backend.listening === 'boolean') {
      backendListening.value = backend.listening
    }
    pushRunLog({
      kind: 'backend',
      title: `${targetLabel.value} 后端`,
      message: msg,
      detail: JSON.stringify(data, null, 2),
      url: typeof backend.url === 'string' ? backend.url : BACKEND_URL.value,
    })
    if (data.frontend) {
      const fe = data.frontend as Record<string, unknown>
      if (typeof fe.listening === 'boolean') {
        frontendListening.value = fe.listening
      }
      pushRunLog({
        kind: 'frontend',
        title: 'Vue 前端',
        message: String(fe.message || '前端已处理'),
        detail: JSON.stringify(fe, null, 2),
        url: typeof fe.url === 'string' ? fe.url : FRONTEND_URL.value,
      })
    }
    await refreshConsoleLogs()
    // 启动接口返回时可能尚未监听：再轮询几次，保证按钮切到「停止」
    for (let i = 0; i < 8 && !backendListening.value; i += 1) {
      await new Promise((r) => setTimeout(r, 1500))
      await refreshConsoleLogs()
    }
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
  pipelineNote.value = `正在启动 ${targetLabel.value} 后端…`
  try {
    const data = await onRestart({ withFrontend: false })
    pipelineNote.value = data.message || `${targetLabel.value} 后端已启动：${BACKEND_URL.value}`
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
  } finally {
    startingBackend.value = false
  }
}

async function onStartFrontend() {
  if (!hasFrontend.value) return
  startingFrontend.value = true
  error.value = ''
  frontendStartInfo.value = null
  pipelineNote.value = `正在启动 ${targetLabel.value} Vue 前端…`
  pushRunLog({ kind: 'info', title: '启动前端', message: pipelineNote.value })
  try {
    const r = await fetch(`/api/agent/${target.value}/frontend/start`, { method: 'POST' })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    if (data && data.ok === false) throw new Error(String(data.message || '前端启动失败'))
    frontendStartInfo.value = data
    const msg = data.message || `Vue 前端已启动：${FRONTEND_URL.value}`
    pipelineNote.value = msg
    pushRunLog({
      kind: 'frontend',
      title: 'Vue 前端',
      message: msg,
      detail: JSON.stringify(data, null, 2),
      url: typeof data.url === 'string' ? data.url : FRONTEND_URL.value,
    })
    await refreshConsoleLogs()
    if (!frontendListening.value) {
      const hint = frontendLog.value?.trim() || '端口未监听，请查看前端日志'
      throw new Error(`前端未就绪：${hint.slice(-800)}`)
    }
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
    pushRunLog({ kind: 'error', title: '前端启动失败', message: String(e) })
    await refreshConsoleLogs()
  } finally {
    startingFrontend.value = false
  }
}

async function onStopBackend() {
  stoppingBackend.value = true
  error.value = ''
  pipelineNote.value = `正在停止 ${targetLabel.value} 后端…`
  pushRunLog({ kind: 'info', title: '停止后端', message: pipelineNote.value })
  try {
    const r = await fetch('/api/agent/runtime/stop-backend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target.value }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    const msg = data.message || `${targetLabel.value} 后端已停止`
    pipelineNote.value = msg
    pushRunLog({
      kind: 'backend',
      title: `${targetLabel.value} 后端`,
      message: msg,
      detail: JSON.stringify(data, null, 2),
    })
    await refreshConsoleLogs()
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
    pushRunLog({ kind: 'error', title: '后端停止失败', message: String(e) })
  } finally {
    stoppingBackend.value = false
  }
}

async function onStopFrontend() {
  if (!hasFrontend.value) return
  stoppingFrontend.value = true
  error.value = ''
  pipelineNote.value = `正在停止 Vue 前端…`
  pushRunLog({ kind: 'info', title: '停止前端', message: pipelineNote.value })
  try {
    const r = await fetch(`/api/agent/${target.value}/frontend/stop`, { method: 'POST' })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    const msg = data.message || 'Vue 前端已停止'
    pipelineNote.value = msg
    pushRunLog({
      kind: 'frontend',
      title: 'Vue 前端',
      message: msg,
      detail: JSON.stringify(data, null, 2),
    })
    await refreshConsoleLogs()
  } catch (e) {
    error.value = String(e)
    pipelineNote.value = ''
    pushRunLog({ kind: 'error', title: '前端停止失败', message: String(e) })
  } finally {
    stoppingFrontend.value = false
  }
}

async function onToggleBackend() {
  if (backendListening.value) await onStopBackend()
  else await onStartBackend()
}

async function onToggleFrontend() {
  if (frontendListening.value) await onStopFrontend()
  else await onStartFrontend()
}

async function onGenerate(opts?: { restart?: boolean }) {
  // 兼容旧入口：默认走执行生成且不自动重启
  if (opts?.restart) {
    await onExecute()
    await onRestart()
    return
  }
  await onExecute()
}

async function onConfirm() {
  // 兼容：仅分析计划，不再自动生成/重启
  await onPlan()
}

async function onNewSession() {
  error.value = ''
  try {
    const r = await fetch('/api/agent/elicit/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target.value }),
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
    readyToPlan.value = false
    input.value = ''
    clearDraft()
    await loadSessions()
  } catch (e) {
    error.value = String(e)
  }
}

async function onCloseSession() {
  if (sessionClosed.value || closingSession.value) return
  closingSession.value = true
  error.value = ''
  try {
    const r = await fetch('/api/agent/elicit/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target.value }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    readyToConclude.value = false
    readyToPlan.value = false
    await loadSessions()
  } catch (e) {
    error.value = String(e)
  } finally {
    closingSession.value = false
  }
}

async function onDeleteSession(sessionId: string) {
  if (!sessionId || deletingSessionId.value) return
  deletingSessionId.value = sessionId
  error.value = ''
  try {
    const r = await fetch(`/api/agent/${target.value}/elicit/sessions/${sessionId}`, {
      method: 'DELETE',
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    await loadSessions()
  } catch (e) {
    error.value = String(e)
  } finally {
    deletingSessionId.value = null
  }
}

export type TreeNode = {
  name: string
  path: string
  type: 'dir' | 'file' | string
  children?: TreeNode[] | null
}

function prefixTreePaths(nodes: TreeNode[], prefix: string): TreeNode[] {
  return nodes.map((n) => ({
    name: n.name,
    path: `${prefix}/${n.path}`,
    type: n.type,
    children: n.children?.length ? prefixTreePaths(n.children, prefix) : n.children ?? null,
  }))
}

function parseQualifiedPath(qualified: string): { target: TreeTarget; rel: string } {
  const raw = qualified.replace(/\\/g, '/').replace(/^\/+/, '')
  const slash = raw.indexOf('/')
  const head = (slash >= 0 ? raw.slice(0, slash) : raw).toLowerCase()
  if (!isTreeTarget(head)) {
    throw new Error(`无效路径（需 java/...、go/... 或 frontend/...）: ${qualified}`)
  }
  const rel = slash >= 0 ? raw.slice(slash + 1) : ''
  if (!rel) throw new Error('请选择具体文件')
  return { target: head, rel }
}

/** 代码页：按目标加载单棵树（路径带 java/、go/ 或 frontend/ 前缀） */
async function loadProjectTree(target: TreeTarget): Promise<{ root: string; tree: TreeNode[] }> {
  const r = await fetch(`/api/agent/${target}/tree`)
  const data = await r.json()
  if (!r.ok) throw new Error(`${target}: ${detailOf(data)}`)
  const children = Array.isArray(data.tree) ? (data.tree as TreeNode[]) : []
  return {
    root: String(data.root || `auto_code/${target}`),
    tree: prefixTreePaths(children, target),
  }
}

/** path 形如 java/src/...、go/... 或 frontend/src/... */
async function loadProjectFile(qualifiedPath: string): Promise<{
  path: string
  content: string
  size: number
  truncated: boolean
  lang: TreeTarget
}> {
  const { target, rel } = parseQualifiedPath(qualifiedPath)
  const q = encodeURIComponent(rel)
  const r = await fetch(`/api/agent/${target}/file?path=${q}`)
  const data = await r.json()
  if (!r.ok) throw new Error(detailOf(data))
  return {
    path: `${target}/${String(data.path || rel)}`,
    content: String(data.content || ''),
    size: Number(data.size || 0),
    truncated: !!data.truncated,
    lang: target,
  }
}

async function onRestore(sessionId: string) {
  error.value = ''
  try {
    const r = await fetch(`/api/agent/elicit/sessions/${sessionId}/restore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target.value }),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(detailOf(data))
    applyElicitation(data.elicitation)
    readyToConclude.value = false
    readyToPlan.value = !!data.elicitation?.plan_ready
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
      body: JSON.stringify({ spec: advancedSpec.value, target: target.value }),
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

/** 在根壳挂载一次，保证跨页共享状态 */
export function usePlatformBootstrap() {
  onMounted(() => {
    void bootstrapPlatform()
  })
}

export function usePlatform() {
  return {
    target,
    langMetas,
    BACKEND_PORT,
    FRONTEND_PORT,
    hasFrontend,
    BACKEND_URL,
    FRONTEND_URL,
    targetLabel,
    logPathHint,
    docs,
    activeDoc,
    status,
    result,
    error,
    analyzing,
    generating,
    chatting,
    concluding,
    confirming,
    planning,
    executing,
    restarting,
    startingBackend,
    startingFrontend,
    stoppingBackend,
    stoppingFrontend,
    readyToConclude,
    readyToPlan,
    pipelineNote,
    restartInfo,
    frontendStartInfo,
    runLogs,
    runLogOpen,
    consoleOpen,
    backendLog,
    frontendLog,
    backendListening,
    frontendListening,
    refreshingLogs,
    elicitation,
    sessions,
    input,
    conclusionEdit,
    showAdvanced,
    advancedSpec,
    maxTurns,
    treeIndentCh,
    platformSettings,
    closingSession,
    deletingSessionId,
    savingSettings,
    messages,
    elicitStatus,
    planReady,
    rollingSummary,
    sessionClosed,
    canChat,
    canConclude,
    canConfirm,
    busy,
    canPlan,
    canExecute,
    canGenerate,
    canConfirmAndGenerate,
    switchTarget,
    refreshConsoleLogs,
    clearRuntimeLogs,
    listToText,
    textToList,
    refreshStatus,
    loadDocs,
    loadPlatformSettings,
    savePlatformSettings,
    saveMaxTurns,
    isTreeTarget,
    treeTargetLabel,
    loadProjectTree,
    loadProjectFile,
    onSend,
    onConclude,
    onPlan,
    onExecute,
    onPlanAndExecute,
    onRestart,
    onStartBackend,
    onStartFrontend,
    onStopBackend,
    onStopFrontend,
    onToggleBackend,
    onToggleFrontend,
    onGenerate,
    onConfirm,
    onNewSession,
    onCloseSession,
    onDeleteSession,
    onRestore,
    onAnalyzeAdvanced,
    onKeydown,
  }
}
