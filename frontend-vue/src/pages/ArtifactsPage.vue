<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import FileTreeNode from '../components/FileTreeNode.vue'
import { usePlatform, type Lang, type TreeNode } from '../composables/usePlatform'
import { highlightCode, languageFromPath } from '../utils/highlight'
import 'highlight.js/styles/github-dark.css'

const TREE_WIDTH_KEY = 'artifacts_tree_width'
const BROWSE_STATE_KEY = 'artifacts_browse_state'
const TREE_WIDTH_DEFAULT = 420
const TREE_WIDTH_MIN = 260
const TREE_WIDTH_MAX = 720

const { error, target, treeIndentCh, loadProjectTree, loadProjectFile, loadPlatformSettings } = usePlatform()

/** 代码页浏览语言，与顶栏生成目标解耦，默认跟当前 target */
const viewLang = ref<Lang>(target.value)
const tree = ref<TreeNode[]>([])
const rootPath = ref('')
const selectedPath = ref('')
const expandedPaths = ref<string[]>([])
const fileContent = ref('')
const fileTruncated = ref(false)
const loadingTree = ref(false)
const loadingFile = ref(false)
const localError = ref('')
const treeWidth = ref(TREE_WIDTH_DEFAULT)
const dragging = ref(false)
const browserEl = ref<HTMLElement | null>(null)
const hasPersistedExpanded = ref(false)

function loadTreeWidth() {
  try {
    const raw = localStorage.getItem(TREE_WIDTH_KEY)
    const n = raw ? Number(raw) : TREE_WIDTH_DEFAULT
    if (Number.isFinite(n)) {
      treeWidth.value = Math.min(TREE_WIDTH_MAX, Math.max(TREE_WIDTH_MIN, n))
    }
  } catch {
    treeWidth.value = TREE_WIDTH_DEFAULT
  }
}

function saveTreeWidth() {
  try {
    localStorage.setItem(TREE_WIDTH_KEY, String(treeWidth.value))
  } catch {
    /* ignore */
  }
}

function saveBrowseState() {
  try {
    localStorage.setItem(
      BROWSE_STATE_KEY,
      JSON.stringify({
        viewLang: viewLang.value,
        selectedPath: selectedPath.value,
        expandedPaths: expandedPaths.value,
      }),
    )
  } catch {
    /* ignore */
  }
}

function loadBrowseState() {
  try {
    const raw = localStorage.getItem(BROWSE_STATE_KEY)
    if (!raw) return
    const data = JSON.parse(raw) as {
      viewLang?: string
      selectedPath?: string
      expandedPaths?: string[]
    }
    if (data.viewLang === 'java' || data.viewLang === 'go') {
      viewLang.value = data.viewLang
    }
    if (typeof data.selectedPath === 'string') {
      selectedPath.value = data.selectedPath
    }
    if (Array.isArray(data.expandedPaths)) {
      expandedPaths.value = data.expandedPaths.filter((p) => typeof p === 'string')
      hasPersistedExpanded.value = true
    }
  } catch {
    /* ignore */
  }
}

function onResizeMove(e: MouseEvent) {
  if (!dragging.value) return
  const left = browserEl.value?.getBoundingClientRect().left ?? 0
  const next = Math.min(TREE_WIDTH_MAX, Math.max(TREE_WIDTH_MIN, e.clientX - left))
  treeWidth.value = next
}

function onResizeUp() {
  if (!dragging.value) return
  dragging.value = false
  document.body.classList.remove('resizing-tree')
  saveTreeWidth()
}

function onResizeDown(e: MouseEvent) {
  e.preventDefault()
  dragging.value = true
  document.body.classList.add('resizing-tree')
}

async function refreshTree(opts?: { restoreFile?: boolean; resetExpanded?: boolean }) {
  loadingTree.value = true
  localError.value = ''
  const wantRestore = opts?.restoreFile !== false
  const pathToRestore = selectedPath.value
  try {
    const data = await loadProjectTree(viewLang.value)
    tree.value = data.tree
    rootPath.value = data.root
    syncExpandedAfterTree(opts?.resetExpanded === true)
    if (selectedPath.value && !findPath(tree.value, selectedPath.value)) {
      selectedPath.value = ''
      fileContent.value = ''
      fileTruncated.value = false
      saveBrowseState()
    } else if (wantRestore && pathToRestore && findPath(tree.value, pathToRestore)) {
      ensureAncestorsExpanded(pathToRestore)
      await openFile(pathToRestore, { persist: false })
    }
  } catch (e) {
    localError.value = String(e)
    tree.value = []
  } finally {
    loadingTree.value = false
  }
}

function findPath(nodes: TreeNode[], path: string): boolean {
  for (const n of nodes) {
    if (n.path === path) return true
    if (n.children?.length && findPath(n.children, path)) return true
  }
  return false
}

function collectDirPaths(nodes: TreeNode[], out: Set<string>) {
  for (const n of nodes) {
    if (n.type === 'dir') {
      out.add(n.path)
      if (n.children?.length) collectDirPaths(n.children, out)
    }
  }
}

function collectDefaultExpanded(nodes: TreeNode[], depth: number, out: string[]) {
  for (const n of nodes) {
    if (n.type !== 'dir') continue
    if (depth < 2) out.push(n.path)
    if (n.children?.length) collectDefaultExpanded(n.children, depth + 1, out)
  }
}

function findAncestorDirs(nodes: TreeNode[], target: string, trail: string[] = []): string[] | null {
  for (const n of nodes) {
    if (n.path === target) return trail
    if (n.type === 'dir' && n.children?.length) {
      const found = findAncestorDirs(n.children, target, [...trail, n.path])
      if (found) return found
    }
  }
  return null
}

function ensureAncestorsExpanded(path: string) {
  const ancestors = findAncestorDirs(tree.value, path)
  if (!ancestors?.length) return
  const set = new Set(expandedPaths.value)
  let changed = false
  for (const p of ancestors) {
    if (!set.has(p)) {
      set.add(p)
      changed = true
    }
  }
  if (changed) {
    expandedPaths.value = [...set]
    saveBrowseState()
  }
}

function syncExpandedAfterTree(reset: boolean) {
  const existing = new Set<string>()
  collectDirPaths(tree.value, existing)
  if (reset || (!hasPersistedExpanded.value && expandedPaths.value.length === 0)) {
    const defaults: string[] = []
    collectDefaultExpanded(tree.value, 0, defaults)
    expandedPaths.value = defaults
    hasPersistedExpanded.value = true
    saveBrowseState()
    return
  }
  const pruned = expandedPaths.value.filter((p) => existing.has(p))
  if (pruned.length !== expandedPaths.value.length) {
    expandedPaths.value = pruned
    saveBrowseState()
  }
}

function onToggleExpand(path: string) {
  const i = expandedPaths.value.indexOf(path)
  expandedPaths.value =
    i >= 0 ? expandedPaths.value.filter((p) => p !== path) : [...expandedPaths.value, path]
  hasPersistedExpanded.value = true
  saveBrowseState()
}

const highlightedHtml = computed(() =>
  fileContent.value ? highlightCode(fileContent.value, selectedPath.value) : '',
)
const detectedLang = computed(() => languageFromPath(selectedPath.value) || '')

async function openFile(path: string, opts?: { persist?: boolean }) {
  selectedPath.value = path
  if (opts?.persist !== false) saveBrowseState()
  loadingFile.value = true
  localError.value = ''
  try {
    const data = await loadProjectFile(path)
    fileContent.value = data.content
    fileTruncated.value = data.truncated
  } catch (e) {
    fileContent.value = ''
    fileTruncated.value = false
    localError.value = String(e)
  } finally {
    loadingFile.value = false
  }
}

async function onSelect(path: string) {
  await openFile(path)
}

function onSwitchViewLang(lang: Lang) {
  if (lang === viewLang.value) return
  viewLang.value = lang
  selectedPath.value = ''
  fileContent.value = ''
  fileTruncated.value = false
  expandedPaths.value = []
  hasPersistedExpanded.value = false
  saveBrowseState()
  void refreshTree({ restoreFile: false, resetExpanded: true })
}

onMounted(() => {
  loadTreeWidth()
  loadBrowseState()
  if (!selectedPath.value) {
    viewLang.value = target.value
  }
  window.addEventListener('mousemove', onResizeMove)
  window.addEventListener('mouseup', onResizeUp)
  void loadPlatformSettings().then(() => refreshTree({ restoreFile: true }))
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onResizeMove)
  window.removeEventListener('mouseup', onResizeUp)
  document.body.classList.remove('resizing-tree')
})

watch(target, (t) => {
  if (t !== viewLang.value) {
    viewLang.value = t
    selectedPath.value = ''
    fileContent.value = ''
    fileTruncated.value = false
    expandedPaths.value = []
    hasPersistedExpanded.value = false
    saveBrowseState()
    void refreshTree({ restoreFile: false, resetExpanded: true })
  }
})
</script>

<template>
  <div class="page-toolbar">
    <div class="lang-switch" role="group" aria-label="浏览语言">
      <button
        type="button"
        :class="['lang-btn', { active: viewLang === 'java' }]"
        @click="onSwitchViewLang('java')"
      >
        Java
      </button>
      <button
        type="button"
        :class="['lang-btn', { active: viewLang === 'go' }]"
        @click="onSwitchViewLang('go')"
      >
        Go
      </button>
    </div>
    <button type="button" class="btn-ghost" :disabled="loadingTree" @click="refreshTree">
      {{ loadingTree ? '加载中…' : '刷新文件树' }}
    </button>
    <span class="muted">分别浏览 {{ viewLang === 'java' ? 'Java' : 'Go' }} 源码 · 拖中间分隔条可拉宽文件树</span>
  </div>

  <div ref="browserEl" class="code-browser" :class="{ dragging }">
    <aside class="code-tree" :style="{ width: `${treeWidth}px` }">
      <div class="code-tree-head">
        <strong>{{ viewLang === 'java' ? 'Java' : 'Go' }} 文件树</strong>
        <span v-if="rootPath" class="muted tree-root" :title="rootPath">{{ rootPath }}</span>
      </div>
      <div class="code-tree-body">
        <div v-if="!tree.length && !loadingTree" class="muted tree-empty">暂无文件（先生成代码）</div>
        <FileTreeNode
          v-for="n in tree"
          :key="n.path"
          :node="n"
          :selected-path="selectedPath"
          :expanded-paths="expandedPaths"
          :depth="0"
          :indent-ch="treeIndentCh"
          @select="onSelect"
          @toggle="onToggleExpand"
        />
      </div>
    </aside>
    <div
      class="code-splitter"
      title="拖动调整宽度"
      @mousedown="onResizeDown"
    />
    <section class="code-preview">
      <div class="code-preview-head">
        <strong>{{ selectedPath || '源码预览' }}</strong>
        <span v-if="detectedLang" class="muted">{{ detectedLang }}</span>
        <span v-if="fileTruncated" class="muted">已截断（过大）</span>
        <span v-else-if="loadingFile" class="muted">读取中…</span>
      </div>
      <pre v-if="fileContent" class="code-body hljs"><code v-html="highlightedHtml"></code></pre>
      <p v-else class="muted code-empty">展开左侧目录，点击文件查看内容</p>
    </section>
  </div>

  <pre v-if="localError || error" class="error">{{ localError || error }}</pre>
</template>
