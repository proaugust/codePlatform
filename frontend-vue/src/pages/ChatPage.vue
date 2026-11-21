<script setup lang="ts">
import { computed } from 'vue'
import { usePlatform } from '../composables/usePlatform'

const {
  sessions,
  elicitation,
  messages,
  input,
  chatting,
  planning,
  executing,
  busy,
  canChat,
  canPlan,
  canExecute,
  readyToPlan,
  planReady,
  rollingSummary,
  sessionClosed,
  pipelineNote,
  status,
  elicitStatus,
  conclusionEdit,
  error,
  listToText,
  textToList,
  maxTurns,
  target,
  switchTarget,
  onNewSession,
  onRestore,
  onSend,
  onPlan,
  onExecute,
  onPlanAndExecute,
  onKeydown,
} = usePlatform()

const applying = computed(() => planning.value || executing.value)
</script>

<template>
  <div class="elicit-layout">
    <aside class="history-panel">
      <div class="history-head">
        <strong>历史记录</strong>
        <div class="history-head-actions">
          <div class="lang-switch" role="group" aria-label="生成目标语言">
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
          <button type="button" class="btn-ghost" @click="onNewSession">新开窗口</button>
        </div>
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
        <strong>分析窗口</strong>
        <span class="muted">
          Enter 发送澄清 · 满 {{ maxTurns }} 轮自动总结关闭
          <template v-if="planReady"> · 计划就绪</template>
          <template v-if="sessionClosed"> · 已关闭</template>
        </span>
      </div>
      <div v-if="rollingSummary" class="chat-summary muted">
        <strong>滚动摘要：</strong>{{ rollingSummary }}
      </div>
      <div class="chat-log">
        <div v-if="!messages.length" class="muted chat-empty">
          描述需求后点「分析并改代码」：会先出计划再写前后端。也可只点「仅分析计划」预览后再改。
        </div>
        <div
          v-for="(m, i) in messages"
          :key="i"
          :class="m.role === 'user' ? 'bubble user' : 'bubble assistant'"
        >
          <div class="bubble-role">
            {{ m.role === 'user' ? '你' : '助手' }}
            <span v-if="m.mode && m.mode !== 'chat'" class="muted"> · {{ m.mode }}</span>
          </div>
          <div class="bubble-body">{{ m.content }}</div>
        </div>
      </div>

      <div class="chat-input-row">
        <textarea
          v-model="input"
          class="chat-input"
          rows="3"
          placeholder="输入需求…（Enter 发送澄清，Shift+Enter 换行；改代码用下方按钮）"
          :disabled="!canChat"
          @keydown="onKeydown"
        />
        <div class="chat-actions">
          <button type="button" :disabled="!input.trim() || !canChat" @click="onSend">
            {{ chatting ? '发送中…' : '发送' }}
          </button>
          <button
            type="button"
            class="btn-gen"
            :disabled="!canPlan || busy"
            @click="onPlanAndExecute"
          >
            {{
              planning
                ? '分析中…'
                : executing
                  ? '改代码中…'
                  : '分析并改代码'
            }}
          </button>
          <button type="button" class="btn-secondary" :disabled="!canPlan" @click="onPlan">
            {{ planning && !executing ? '分析中…' : '仅分析计划' }}
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="!canExecute"
            :title="canExecute ? '按当前计划生成/改代码' : '需先「分析计划」；仅聊天确认不会改代码'"
            @click="onExecute"
          >
            {{ executing && !planning ? '改代码中…' : '仅执行生成' }}
          </button>
          <span v-if="applying && pipelineNote" class="muted">{{ pipelineNote }}</span>
          <span v-else-if="planReady" class="muted">可改代码</span>
          <span v-else-if="readyToPlan" class="muted">可分析</span>
          <span v-else class="muted">先分析计划再执行（聊天确认无效）</span>
        </div>
      </div>

      <div class="chat-gen-row">
        <span class="muted">
          流程：澄清（可选）→ 分析并改代码 → 到「运行」页启动
          <template v-if="status"> · 文档 {{ status.has_docs ? '已就绪' : '未生成' }}</template>
          <template v-if="elicitStatus"> · {{ elicitStatus }}</template>
        </span>
      </div>
    </div>
  </div>

  <div
    v-if="conclusionEdit.summary || elicitStatus === 'planned' || rollingSummary"
    class="result"
  >
    <h2>结论（可编辑；分析时一并提交）</h2>
    <label class="label" for="c-summary">摘要</label>
    <textarea
      id="c-summary"
      v-model="conclusionEdit.summary"
      class="concl-area"
      rows="3"
      :disabled="sessionClosed"
    />
    <div class="concl-grid">
      <div>
        <label class="label">目标（每行一条）</label>
        <textarea
          class="concl-area"
          rows="4"
          :value="listToText(conclusionEdit.goals)"
          :disabled="sessionClosed"
          @input="conclusionEdit.goals = textToList(($event.target as HTMLTextAreaElement).value)"
        />
      </div>
      <div>
        <label class="label">范围</label>
        <textarea
          class="concl-area"
          rows="4"
          :value="listToText(conclusionEdit.scope)"
          :disabled="sessionClosed"
          @input="conclusionEdit.scope = textToList(($event.target as HTMLTextAreaElement).value)"
        />
      </div>
      <div>
        <label class="label">不在范围</label>
        <textarea
          class="concl-area"
          rows="4"
          :value="listToText(conclusionEdit.out_of_scope)"
          :disabled="sessionClosed"
          @input="conclusionEdit.out_of_scope = textToList(($event.target as HTMLTextAreaElement).value)"
        />
      </div>
      <div>
        <label class="label">非功能</label>
        <textarea
          class="concl-area"
          rows="4"
          :value="listToText(conclusionEdit.nfr)"
          :disabled="sessionClosed"
          @input="conclusionEdit.nfr = textToList(($event.target as HTMLTextAreaElement).value)"
        />
      </div>
    </div>
  </div>

  <pre v-if="error" class="error">{{ error }}</pre>
</template>
