<script setup lang="ts">
import { computed } from 'vue'
import AgentPipeline from '../components/AgentPipeline.vue'
import { usePlatform } from '../composables/usePlatform'

const {
  sessions,
  elicitation,
  messages,
  input,
  planning,
  executing,
  busy,
  canChat,
  canPlan,
  readyToPlan,
  planReady,
  rollingSummary,
  sessionClosed,
  pipelineNote,
  runPipeline,
  runEventsLive,
  status,
  elicitStatus,
  error,
  maxTurns,
  target,
  switchTarget,
  onNewSession,
  onRestore,
  onPlan,
  onPlanAndExecute,
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
          分析 = plan · 执行 = agent · 满 {{ maxTurns }} 轮自动总结关闭
          <template v-if="planReady"> · 计划就绪</template>
          <template v-if="sessionClosed"> · 已关闭</template>
        </span>
      </div>
      <div v-if="rollingSummary" class="chat-summary muted">
        <strong>滚动摘要：</strong>{{ rollingSummary }}
      </div>
      <div class="chat-log">
        <div v-if="!messages.length" class="muted chat-empty">
          描述需求后选：分析（计划）只出方案；执行（分析并改代码）会先计划再改代码。
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
          placeholder="输入需求…"
          :disabled="!canChat"
        />
        <div class="chat-actions">
          <button
            type="button"
            class="btn-secondary"
            :disabled="!canPlan"
            title="plan：只分析并产出计划，不改代码"
            @click="onPlan"
          >
            {{ planning && !executing ? '分析中…' : '分析（计划）' }}
          </button>
          <button
            type="button"
            class="btn-gen"
            :disabled="!canPlan || busy"
            title="agent：分析计划并改代码"
            @click="onPlanAndExecute"
          >
            {{
              planning
                ? '分析中…'
                : executing
                  ? '改代码中…'
                  : '执行（分析并改代码）'
            }}
          </button>
          <span v-if="applying && pipelineNote" class="muted">{{ pipelineNote }}</span>
          <span v-else-if="planReady" class="muted">计划就绪</span>
          <span v-else-if="readyToPlan" class="muted">可分析</span>
          <span v-else class="muted">分析 = plan · 执行 = agent</span>
        </div>
      </div>

      <div class="chat-gen-row">
        <span class="muted">
          流程：分析（计划）→ 执行（分析并改代码）→ 到「运行」页启动
          <template v-if="status"> · 文档 {{ status.has_docs ? '已就绪' : '未生成' }}</template>
          <template v-if="elicitStatus"> · {{ elicitStatus }}</template>
        </span>
      </div>

      <AgentPipeline :pipeline="runPipeline" :live="runEventsLive || applying" />
    </div>
  </div>

  <pre v-if="error" class="error">{{ error }}</pre>
</template>
