<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { deleteBook, formatError, listBooks, updateBook, updateStock } from '../api/client'
import type { Book } from '../types'

const books = ref<Book[]>([])
const keyword = ref('')
const loading = ref(false)
const savingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const selectedId = ref<number | null>(null)
const errorCode = ref('')
const errorMessage = ref('')
const notice = ref('')
const editing = ref<Record<number, string>>({})

// 编辑弹窗状态
const editVisible = ref(false)
const editSaving = ref(false)
const editErrorCode = ref('')
const editErrorMessage = ref('')
const editForm = reactive({
  id: 0,
  title: '',
  author: '',
  stock: '0'
})

function formatTime(value?: string): string {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

function setError(error: unknown) {
  const info = formatError(error)
  errorCode.value = info.code
  errorMessage.value = info.message
  notice.value = ''
}

function clearMessages() {
  errorCode.value = ''
  errorMessage.value = ''
  notice.value = ''
}

async function load() {
  loading.value = true
  clearMessages()
  try {
    books.value = await listBooks(keyword.value.trim() || undefined)
    if (selectedId.value !== null && !books.value.some((b) => b.id === selectedId.value)) {
      selectedId.value = null
    }
  } catch (error) {
    books.value = []
    setError(error)
  } finally {
    loading.value = false
  }
}

function reset() {
  keyword.value = ''
  void load()
}

function selectBook(book: Book) {
  selectedId.value = selectedId.value === book.id ? null : book.id
}

function startEdit(book: Book) {
  clearMessages()
  editErrorCode.value = ''
  editErrorMessage.value = ''
  editForm.id = book.id
  editForm.title = book.title
  editForm.author = book.author ?? ''
  editForm.stock = String(book.stock)
  editVisible.value = true
}

function closeEdit() {
  if (editSaving.value) return
  editVisible.value = false
}

async function submitEdit() {
  editErrorCode.value = ''
  editErrorMessage.value = ''

  const title = editForm.title.trim()
  const stockValue = Number(editForm.stock)

  if (!title) {
    editErrorCode.value = 'VALIDATION_ERROR'
    editErrorMessage.value = '书名不能为空'
    return
  }
  if (editForm.stock === '' || !Number.isInteger(stockValue) || stockValue < 0) {
    editErrorCode.value = 'VALIDATION_ERROR'
    editErrorMessage.value = '库存必须为大于等于 0 的整数'
    return
  }

  editSaving.value = true
  try {
    const updated = await updateBook(editForm.id, {
      title,
      author: editForm.author.trim(),
      stock: stockValue
    })
    books.value = books.value.map((item) => (item.id === updated.id ? updated : item))
    editVisible.value = false
    notice.value = `《${updated.title}》已更新`
    await load()
  } catch (error) {
    const info = formatError(error)
    editErrorCode.value = info.code
    editErrorMessage.value = info.message
  } finally {
    editSaving.value = false
  }
}

function startStockEdit(book: Book) {
  editing.value = { ...editing.value, [book.id]: String(book.stock) }
  clearMessages()
}

function cancelStockEdit(id: number) {
  const next = { ...editing.value }
  delete next[id]
  editing.value = next
}

async function saveStock(book: Book) {
  const raw = editing.value[book.id]
  const value = Number(raw)
  clearMessages()

  if (raw === undefined || raw === '' || !Number.isInteger(value) || value < 0) {
    errorCode.value = 'VALIDATION_ERROR'
    errorMessage.value = '库存必须为大于等于 0 的整数'
    return
  }

  if (value === book.stock) {
    cancelStockEdit(book.id)
    notice.value = '库存未发生变化'
    return
  }

  savingId.value = book.id
  try {
    const updated = await updateStock(book.id, value)
    books.value = books.value.map((item) => (item.id === updated.id ? updated : item))
    cancelStockEdit(book.id)
    notice.value = `《${updated.title}》库存已更新为 ${updated.stock}`
  } catch (error) {
    setError(error)
  } finally {
    savingId.value = null
  }
}

async function removeBook(book: Book) {
  clearMessages()
  const confirmed = window.confirm(`确定要删除《${book.title}》（ID: ${book.id}）吗？此操作不可恢复。`)
  if (!confirmed) return

  deletingId.value = book.id
  try {
    await deleteBook(book.id)
    books.value = books.value.filter((item) => item.id !== book.id)
    if (selectedId.value === book.id) selectedId.value = null
    cancelStockEdit(book.id)
    notice.value = `《${book.title}》已删除`
    await load()
  } catch (error) {
    setError(error)
  } finally {
    deletingId.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="card">
    <header class="card-head">
      <h2>图书列表</h2>
      <RouterLink class="btn primary" to="/books/new">新增图书</RouterLink>
    </header>

    <form class="search-bar" @submit.prevent="load">
      <input
        v-model="keyword"
        type="text"
        placeholder="按书名 / 作者 / ISBN 模糊搜索"
        maxlength="100"
      />
      <button class="btn primary" type="submit" :disabled="loading">
        {{ loading ? '搜索中…' : '搜索' }}
      </button>
      <button class="btn ghost" type="button" @click="reset">重置</button>
    </form>

    <p v-if="errorMessage" class="alert error">
      <strong>{{ errorCode }}</strong>
      <span>{{ errorMessage }}</span>
    </p>
    <p v-if="notice" class="alert success">{{ notice }}</p>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="books.length === 0" class="muted">暂无图书数据，先新增一本吧。</p>

    <table v-else class="table">
      <thead>
        <tr>
          <th>选择</th>
          <th>ID</th>
          <th>书名</th>
          <th>作者</th>
          <th>ISBN</th>
          <th>库存</th>
          <th>更新时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="book in books" :key="book.id" :class="{ selected: selectedId === book.id }">
          <td>
            <input
              type="radio"
              name="book-select"
              :value="book.id"
              :checked="selectedId === book.id"
              @change="selectBook(book)"
            />
          </td>
          <td>{{ book.id }}</td>
          <td>{{ book.title }}</td>
          <td>{{ book.author }}</td>
          <td>{{ book.isbn }}</td>
          <td>
            <input
              v-if="editing[book.id] !== undefined"
              v-model="editing[book.id]"
              class="stock-input"
              type="number"
              min="0"
              step="1"
            />
            <span v-else>{{ book.stock }}</span>
          </td>
          <td>{{ formatTime(book.updatedAt) }}</td>
          <td class="actions">
            <button class="btn small primary" type="button" @click="startEdit(book)">编辑</button>
            <template v-if="editing[book.id] !== undefined">
              <button
                class="btn small primary"
                type="button"
                :disabled="savingId === book.id"
                @click="saveStock(book)"
              >
                {{ savingId === book.id ? '保存中…' : '保存库存' }}
              </button>
              <button class="btn small ghost" type="button" @click="cancelStockEdit(book.id)">
                取消
              </button>
            </template>
            <button v-else class="btn small ghost" type="button" @click="startStockEdit(book)">
              改库存
            </button>
            <RouterLink class="btn small ghost" :to="`/books/${book.id}`">详情</RouterLink>
            <button
              class="btn small danger"
              type="button"
              :disabled="deletingId === book.id"
              @click="removeBook(book)"
            >
              {{ deletingId === book.id ? '删除中…' : '删除' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="editVisible" class="modal-mask" @click.self="closeEdit">
      <div class="modal">
        <header class="modal-head">
          <h3>编辑图书（ID: {{ editForm.id }}）</h3>
          <button class="btn small ghost" type="button" @click="closeEdit">关闭</button>
        </header>
        <form class="modal-body" @submit.prevent="submitEdit">
          <p v-if="editErrorMessage" class="alert error">
            <strong>{{ editErrorCode }}</strong>
            <span>{{ editErrorMessage }}</span>
          </p>
          <label class="field">
            <span class="label">书名</span>
            <input v-model="editForm.title" type="text" maxlength="200" />
          </label>
          <label class="field">
            <span class="label">作者</span>
            <input v-model="editForm.author" type="text" maxlength="200" />
          </label>
          <label class="field">
            <span class="label">库存</span>
            <input v-model="editForm.stock" type="number" min="0" step="1" />
          </label>
          <div class="modal-actions">
            <button class="btn primary" type="submit" :disabled="editSaving">
              {{ editSaving ? '保存中…' : '保存' }}
            </button>
            <button class="btn ghost" type="button" :disabled="editSaving" @click="closeEdit">
              取消
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>
