<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { usePlatform } from '../composables/usePlatform'

const {
  advancedSpec,
  analyzing,
  error,
  onAnalyzeAdvanced,
  maxTurns,
  treeIndentCh,
  platformSettings,
  savingSettings,
  closingSession,
  deletingSessionId,
  sessionClosed,
  sessions,
  elicitation,
  busy,
  loadPlatformSettings,
  savePlatformSettings,
  onCloseSession,
  onDeleteSession,
  onNewSession,
} = usePlatform()

const draftTurns = ref(maxTurns.value)
const draftIndentCh = ref(treeIndentCh.value)
const draftLlmBaseUrl = ref('')
const draftLlmModel = ref('')
const draftLlmApiKey = ref('')

watch(
  maxTurns,
  (v) => {
    draftTurns.value = v
  },
  { immediate: true },
)

watch(
  treeIndentCh,
  (v) => {
    draftIndentCh.value = v
  },
  { immediate: true },
)

watch(
  platformSettings,
  (s) => {
    if (!s) return
    draftLlmBaseUrl.value = s.llm_base_url || ''
    draftLlmModel.value = s.llm_model || ''
    draftLlmApiKey.value = ''
  },
  { immediate: true },
)

const turnsHint = computed(() => {
  const min = platformSettings.value?.min_max_turns ?? 3
  const max = platformSettings.value?.max_max_turns ?? 50
  return `${min}～${max}`
})

const indentHint = computed(() => {
  const min = platformSettings.value?.min_tree_indent_ch ?? 1
  const max = platformSettings.value?.max_tree_indent_ch ?? 8
  return `${min}～${max}`
})

const keyPlaceholder = computed(() => {
  const s = platformSettings.value
  if (s?.has_llm_api_key && s.llm_api_key_masked) {
    return `已配置 ${s.llm_api_key_masked}（留空不修改）`
  }
  return '输入 API Key'
})

async function onSaveProjectSettings() {
  const patch: {
    max_turns: number
    tree_indent_ch: number
    llm_base_url: string
    llm_model: string
    llm_api_key?: string
  } = {
    max_turns: Number(draftTurns.value),
    tree_indent_ch: Number(draftIndentCh.value),
    llm_base_url: draftLlmBaseUrl.value.trim(),
    llm_model: draftLlmModel.value.trim(),
  }
  const key = draftLlmApiKey.value.trim()
  if (key) {
    patch.llm_api_key = key
  }
  await savePlatformSettings(patch)
  draftLlmApiKey.value = ''
}

async function onRefreshSettings() {
  await loadPlatformSettings()
}

function onDelete(sessionId: string) {
  if (!confirm(`删除历史会话 ${sessionId}？不可恢复。`)) return
  void onDeleteSession(sessionId)
}
</script>

<template>
  <div class="settings-panel">
    <div class="page-toolbar settings-toolbar">
      <h2 class="settings-title">项目设置</h2>
      <button type="button" class="btn-ghost" @click="onRefreshSettings">刷新</button>
    </div>

    <label class="label" for="max-turns">会话自动总结轮次（用户发言达上限后自动总结并关闭）</label>
    <div class="row">
      <input
        id="max-turns"
        v-model.number="draftTurns"
        class="turns-input"
        type="number"
        :min="platformSettings?.min_max_turns ?? 3"
        :max="platformSettings?.max_max_turns ?? 50"
      />
      <span class="muted">范围 {{ turnsHint }} · 当前 {{ maxTurns }}</span>
    </div>

    <label class="label" for="tree-indent">代码文件树每层缩进（字符宽 ch）</label>
    <div class="row">
      <input
        id="tree-indent"
        v-model.number="draftIndentCh"
        class="turns-input"
        type="number"
        :min="platformSettings?.min_tree_indent_ch ?? 1"
        :max="platformSettings?.max_tree_indent_ch ?? 8"
      />
      <span class="muted">默认 2 · 范围 {{ indentHint }} · 当前 {{ treeIndentCh }}ch</span>
    </div>

    <h3 class="settings-subtitle">LLM 配置</h3>
    <p class="muted">优先使用此处配置；留空则回退服务端 .env。API Key 不会明文回传。</p>

    <label class="label" for="llm-base-url">Base URL</label>
    <div class="row">
      <input
        id="llm-base-url"
        v-model="draftLlmBaseUrl"
        class="settings-text-input"
        type="text"
        spellcheck="false"
        placeholder="https://api.deepseek.com"
      />
    </div>

    <label class="label" for="llm-model">模型</label>
    <div class="row">
      <input
        id="llm-model"
        v-model="draftLlmModel"
        class="settings-text-input"
        type="text"
        spellcheck="false"
        placeholder="deepseek-chat"
      />
    </div>

    <label class="label" for="llm-api-key">API Key</label>
    <div class="row">
      <input
        id="llm-api-key"
        v-model="draftLlmApiKey"
        class="settings-text-input"
        type="password"
        autocomplete="off"
        spellcheck="false"
        :placeholder="keyPlaceholder"
      />
    </div>

    <div class="row">
      <button type="button" :disabled="savingSettings || busy" @click="onSaveProjectSettings">
        {{ savingSettings ? '保存中…' : '保存项目设置' }}
      </button>
    </div>

    <div v-if="platformSettings" class="settings-readonly muted">
      <div>代码根：<code>{{ platformSettings.auto_code_root }}</code></div>
      <div>默认语言 {{ platformSettings.default_lang }}</div>
    </div>
  </div>

  <div class="settings-panel">
    <h2 class="settings-title">会话操作</h2>
    <div class="row">
      <button
        type="button"
        class="btn-secondary"
        :disabled="sessionClosed || closingSession || busy"
        @click="onCloseSession"
      >
        {{ closingSession ? '关闭中…' : '关闭当前会话（总结归档）' }}
      </button>
      <button type="button" class="btn-ghost" :disabled="busy" @click="onNewSession">新开窗口</button>
      <span v-if="elicitation" class="muted">
        当前 {{ elicitation.session_id }} · {{ elicitation.status }}
      </span>
    </div>

    <h3>历史会话</h3>
    <ul v-if="sessions.length" class="settings-session-list">
      <li v-for="s in sessions" :key="s.session_id" class="settings-session-item">
        <div>
          <code>{{ s.session_id }}</code>
          <span class="muted"> · {{ s.status || '—' }} · 消息 {{ s.message_count || 0 }}</span>
          <div class="muted">{{ s.summary || '（无摘要）' }}</div>
        </div>
        <button
          type="button"
          class="btn-danger"
          :disabled="deletingSessionId === s.session_id"
          @click="onDelete(s.session_id)"
        >
          {{ deletingSessionId === s.session_id ? '删除中…' : '删除' }}
        </button>
      </li>
    </ul>
    <p v-else class="muted">暂无归档会话</p>
  </div>

  <div class="advanced settings-panel">
    <h2>高级：直接粘贴需求（跳过澄清）</h2>
    <p class="muted">粘贴完整需求后生成文档，再回「聊天」或「代码」继续生成代码。</p>
    <textarea v-model="advancedSpec" class="spec-area" spellcheck="false" />
    <div class="row">
      <button type="button" :disabled="analyzing || !advancedSpec.trim()" @click="onAnalyzeAdvanced">
        {{ analyzing ? '分析中…' : '生成文档' }}
      </button>
    </div>
  </div>

  <pre v-if="error" class="error">{{ error }}</pre>
</template>
