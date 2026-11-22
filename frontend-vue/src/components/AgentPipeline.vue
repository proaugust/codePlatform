<script setup lang="ts">
import { computed } from 'vue'
import type { RunPipeline, RunPipelineStep } from '../composables/usePlatform'

const props = defineProps<{
  pipeline: RunPipeline
  live?: boolean
}>()

const NODES = [
  { id: 'INTEL', label: '扫描' },
  { id: 'REQUIRE', label: '需求' },
  { id: 'PLAN', label: '计划' },
  { id: 'CODE', label: '写码' },
  { id: 'VALIDATE', label: '校验' },
  { id: 'FRONTEND', label: '前端' },
  { id: 'REVIEW', label: '报告' },
  { id: 'DONE', label: '完成' },
] as const

type NodeId = (typeof NODES)[number]['id']

function mapStateToNode(state: string): NodeId | null {
  if (state === 'AWAITING_APPROVAL') return 'PLAN'
  if (state === 'INIT' || !state) return null
  if (NODES.some((n) => n.id === state)) return state as NodeId
  return null
}

const failedAt = computed(() => {
  if (props.pipeline.state !== 'FAILED') return null
  const steps = props.pipeline.steps || []
  for (let i = steps.length - 1; i >= 0; i--) {
    const s = steps[i]
    if (s.state && s.state !== 'FAILED') {
      const mapped = mapStateToNode(s.state)
      if (mapped && mapped !== 'DONE') return mapped
    }
  }
  return mapStateToNode(props.pipeline.state)
})

const currentNode = computed(() => {
  if (props.pipeline.state === 'FAILED') return failedAt.value
  return mapStateToNode(props.pipeline.state)
})

const visited = computed(() => {
  const set = new Set<NodeId>()
  for (const step of props.pipeline.steps || []) {
    const id = mapStateToNode(step.state)
    if (id) set.add(id)
  }
  const cur = currentNode.value
  if (cur) set.add(cur)
  // DONE 意味着前面都走过
  if (props.pipeline.state === 'DONE') {
    for (const n of NODES) set.add(n.id)
  }
  return set
})

function nodeClass(id: NodeId): string {
  const cur = currentNode.value
  const failed = props.pipeline.state === 'FAILED' && failedAt.value === id
  if (failed) return 'node failed'
  if (props.pipeline.state === 'DONE' && id === 'DONE') return 'node done current'
  if (cur === id && props.pipeline.state !== 'DONE') return 'node current'
  if (visited.value.has(id) && cur && NODES.findIndex((n) => n.id === id) < NODES.findIndex((n) => n.id === cur)) {
    return 'node done'
  }
  if (visited.value.has(id) && props.pipeline.state === 'DONE') return 'node done'
  if (visited.value.has(id) && id !== cur) return 'node done'
  return 'node pending'
}

const statusLine = computed(() => {
  const msg = props.pipeline.message || ''
  const hint = (props.pipeline.repair_hint || '').trim()
  if (props.pipeline.state === 'FAILED') {
    const base = props.pipeline.error || msg || '失败'
    return hint ? `${base} · ${hint}` : base
  }
  return msg
})

const recentSteps = computed(() => {
  const steps: RunPipelineStep[] = props.pipeline.steps || []
  return steps.slice(-8)
})
</script>

<template>
  <div class="agent-pipeline" :class="{ live: !!live }">
    <div class="pipeline-head">
      <strong>Agent 流水线</strong>
      <span v-if="live" class="live-dot" title="实时推送中">LIVE</span>
      <span class="muted">{{ pipeline.state || 'INIT' }}</span>
    </div>
    <ol class="pipeline-nodes" aria-label="agent 执行阶段">
      <li v-for="(n, i) in NODES" :key="n.id" :class="nodeClass(n.id)">
        <span class="node-dot" />
        <span class="node-label">{{ n.label }}</span>
        <span v-if="i < NODES.length - 1" class="node-edge" aria-hidden="true" />
      </li>
    </ol>
    <p v-if="statusLine" class="pipeline-status" :class="{ err: pipeline.state === 'FAILED' }">
      {{ statusLine }}
    </p>
    <ul v-if="recentSteps.length" class="pipeline-trail muted">
      <li v-for="(s, i) in recentSteps" :key="`${s.state}-${s.at}-${i}`">
        {{ s.state }}<template v-if="s.message"> · {{ s.message }}</template>
      </li>
    </ul>
  </div>
</template>
