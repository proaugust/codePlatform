<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { deleteBook, formatError, getBook, updateBook, updateStock } from '../api/client'
import type { Book } from '../types'

const props = defineProps<{ id: string }>()
const router = useRouter()

const book = ref<Book | null>(null)
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const stockInput = ref('')
const errorCode = ref('')
const errorMessage = ref('')
const notice = ref('')

// 编辑表单
const editVisible = ref(false)
const editSaving = ref(false)
const editErrorCode = ref('')
const editErrorMessage = ref('')
const editForm = reactive({ title: '', author: '', stock: '0' })

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
  notice.value = ''
  editVisible.value = false
  const id = Number(props.id)
  if (!Number.isInteger(id) || id <= 0) {
    book.value = null
    errorCode.value = 'VALIDATION_ERROR'
    errorMessage.value = '图书 id 必须为大于 0 的整数'
    loading.value = false
    return
  }
  try {
    const data = await getBook(id)
    book.value = data
    stockInput.value = String(data.stock)
  } catch (error) {
    book.value = null
    setError(error)
  } finally {
    loading.value = false
  }
}

function openEdit() {
  if (!book.value) return
  errorCode.value = ''
  errorMessage.value = ''
  notice.value = ''
  editErrorCode.value = ''
  editErrorMessage.value = ''
  editForm.title = book.value.title
  editForm.author = book.value.author ?? ''
  editForm.stock = String(book.value.stock)
  editVisible.value = true
}

function closeEdit() {
  if (editSaving.value) return
  editVisible.value = false
}

async function submitEdit() {
  if (!book.value) return
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
    const updated = await updateBook(book.value.id, {
      title,
      author: editForm.author.trim(),
      stock: stockValue
    })
    book.value = updated
    stockInput.value = String(updated.stock)
    editVisible.value = false
    notice.value = '图书信息已更新'
  } catch (error) {
    const info = formatError(error)
    editErrorCode.value = info.code
    editErrorMessage.value = info.message
  } finally {
    editSaving.value = false
  }
}

async function saveStock() {
  if (!book.value) return
  errorCode.value = ''
  errorMessage.value = ''
  notice.value = ''

  const value = Number(stockInput.value)
  if (stockInput.value === '' || !Number.isInteger(value) || value < 0) {
    errorCode.value = 'VALIDATION_ERROR'
    errorMessage.value = '库存必须为大于等于 0 的整数'
    return
  }

  if (value === book.value.stock) {
    notice.value = '库存未发生变化'
    return
  }

  saving.value = true
  try {
    const updated = await updateStock(book.value.id, value)
    book.value = updated
    stockInput.value = String(updated.stock)
    notice.value = '库存更新成功'
  } catch (error) {
    setError(error)
  } finally {
    saving.value = false
  }
}

async function removeBook() {
  if (!book.value) return
  errorCode.value = ''
  errorMessage.value = ''
  notice.value = ''

  const confirmed = window.confirm(
    `确定要删除《${book.value.title}》（ID: ${book.value.id}）吗？此操作不可恢复。`
  )
  if (!confirmed) return

  deleting.value = true
  try {
    await deleteBook(book.value.id)
    await router.push('/books')
  } catch (error) {
    setError(error)
  } finally {
    deleting.value = false
  }
}

watch(() => props.id, load)
onMounted(load)
</script>

<template>
  <section class="card">
    <header class="card-head">
      <h2>图书详情</h2>
      <RouterLink class="btn ghost" to="/books">返回列表</RouterLink>
    </header>

    <p v-if="errorMessage" class="alert error">
      <strong>{{ errorCode }}</strong>
      <span>{{ errorMessage }}</span>
    </p>
    <p v-if="notice" class="alert success">{{ notice }}</p>

    <p v-if="loading" class="muted">加载中…</p>

    <template v-else-if="book">
      <dl class="detail">
        <div><dt>ID</dt><dd>{{ book.id }}</dd></div>
        <div><dt>书名</dt><dd>{{ book.title }}</dd></div>
        <div><dt>作者</dt><dd>{{ book.author }}</dd></div>
        <div><dt>ISBN</dt><dd>{{ book.isbn }}</dd></div>
        <div><dt>库存</dt><dd>{{ book.stock }}</dd></div>
        <div><dt>创建时间</dt><dd>{{ formatTime(book.createdAt) }}</dd></div>
        <div><dt>更新时间</dt><dd>{{ formatTime(book.updatedAt) }}</dd></div>
      </dl>

      <div class="edit-panel">
        <h3>修改图书</h3>
        <button class="btn primary" type="button" @click="openEdit">编辑图书信息</button>
      </div>

      <div class="stock-panel">
        <h3>更新库存</h3>
        <form class="inline-form" @submit.prevent="saveStock">
          <label class="field">
            <span class="label">最新库存（绝对值覆盖）</span>
            <input v-model="stockInput" type="number" min="0" step="1" />
          </label>
          <button class="btn primary" type="submit" :disabled="saving">
            {{ saving ? '保存中…' : '保存库存' }}
          </button>
        </form>
      </div>

      <div class="danger-panel">
        <h3>删除图书</h3>
        <p class="muted">删除后不可恢复，请谨慎操作。</p>
        <button class="btn danger" type="button" :disabled="deleting" @click="removeBook">
          {{ deleting ? '删除中…' : '删除该图书' }}
        </button>
      </div>

      <div v-if="editVisible" class="modal-mask" @click.self="closeEdit">
        <div class="modal">
          <header class="modal-head">
            <h3>编辑图书（ID: {{ book.id }}）</h3>
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
    </template>

    <p v-else-if="!errorMessage" class="muted">暂无数据</p>
  </section>
</template>
