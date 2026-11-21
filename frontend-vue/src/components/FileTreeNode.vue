<script setup lang="ts">
import { computed } from 'vue'
import type { TreeNode } from '../composables/usePlatform'

const props = withDefaults(
  defineProps<{
    node: TreeNode
    selectedPath: string
    expandedPaths: string[]
    depth?: number
    /** 每层缩进字符宽，默认 2ch */
    indentCh?: number
  }>(),
  {
    depth: 0,
    indentCh: 2,
  },
)

const emit = defineEmits<{
  select: [path: string]
  toggle: [path: string]
}>()

const open = computed(
  () => props.node.type === 'dir' && props.expandedPaths.includes(props.node.path),
)

/** 子节点嵌套在父节点内，只加本层相对缩进，避免 depth×indent 累加 */
const padLeft = computed(() =>
  props.depth <= 0 ? '0' : `${Math.max(1, props.indentCh)}ch`,
)

function onToggle() {
  if (props.node.type === 'dir') emit('toggle', props.node.path)
}

function onClick() {
  if (props.node.type === 'file') emit('select', props.node.path)
  else onToggle()
}
</script>

<template>
  <div class="ft-node" :style="{ paddingLeft: padLeft }">
    <button
      type="button"
      class="ft-row"
      :class="{
        file: node.type === 'file',
        dir: node.type === 'dir',
        active: node.type === 'file' && node.path === selectedPath,
      }"
      :title="node.path"
      @click="onClick"
    >
      <span class="ft-mark">{{ node.type === 'dir' ? (open ? '▾' : '▸') : '·' }}</span>
      <span class="ft-name">{{ node.name }}</span>
    </button>
    <template v-if="node.type === 'dir' && open && node.children?.length">
      <FileTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :selected-path="selectedPath"
        :expanded-paths="expandedPaths"
        :depth="depth + 1"
        :indent-ch="indentCh"
        @select="emit('select', $event)"
        @toggle="emit('toggle', $event)"
      />
    </template>
  </div>
</template>
