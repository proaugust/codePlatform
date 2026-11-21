<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { formatError, listBooks, updateStock } from '../api/client'
import type { Book } from '../types'

const books = ref<Book[]>([])
const keyword = ref('')
const loading = ref(false)
const savingId = ref<number | null>(null)
const errorCode = ref('')
const errorMessage = ref('')
const notice = ref('')
const editing = ref<Record<number, string>>({})

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

async function load() {
  loading.value = true
  errorCode.value = ''
  errorMessage.value = ''
  try {
    books.value = await listBooks(keyword.value.trim() || undefined)
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

function startEdit(book: Book) {
  editing.value = { ...editing.value, [book.id]: String(book.stock) }
  errorCode.value = ''
  errorMessage.value = ''
  notice.value = ''
}

function cancelEdit(id: number) {
  const next = { ...editing.value }
  delete next[id]
  editing.value = next
}

async function saveStock(book: Book) {
  const raw = editing.value[book.id]
  const value = Number(raw)
  errorCode.value = ''
  errorMessage.value = ''
  notice.value = ''

  if (raw === undefined || raw === '' || !Number.isInteger(value) || value < 0) {
    errorCode.value = 'VALIDATION_ERROR'
    errorMessage.value = '库存必须为大于等于 0 的整数'
    return
  }

  savingId.value = book.id
  try {
    const updated = await updateStock(book.id, value)
    books.value = books.value.map((item) => (item.id === updated.id ? updated : item))
    cancelEdit(book.id)
    notice.value = `《${updated.title}》库存已更新为 ${updated.stock}`
  } catch (error) {
    setError(error)
  } finally {
    savingId.value = null
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
        <tr v-for="book in books" :key="book.id">
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
            <RouterLink class="btn small" :to="`/books/${book.id}`">详情</RouterLink>
            <template v-if="editing[book.id] !== undefined">
              <button
                class="btn small primary"
                type="button"
                :disabled="savingId === book.id"
                @click="saveStock(book)"
              >
                {{ savingId === book.id ? '保存中…' : '保存' }}
              </button>
              <button class="btn small ghost" type="button" @click="cancelEdit(book.id)">
                取消
              </button>
            </template>
            <button v-else class="btn small" type="button" @click="startEdit(book)">
              改库存
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
