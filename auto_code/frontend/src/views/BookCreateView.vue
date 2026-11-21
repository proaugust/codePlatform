<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { createBook, formatError } from '../api/client'

const router = useRouter()

const title = ref('')
const author = ref('')
const isbn = ref('')
const stock = ref('0')

const submitting = ref(false)
const errorCode = ref('')
const errorMessage = ref('')
const fieldErrors = ref<Record<string, string>>({})

function validate(): boolean {
  const errors: Record<string, string> = {}
  if (!title.value.trim()) errors.title = '书名不能为空'
  else if (title.value.trim().length > 200) errors.title = '书名最多 200 个字符'

  if (!author.value.trim()) errors.author = '作者不能为空'
  else if (author.value.trim().length > 120) errors.author = '作者最多 120 个字符'

  if (!isbn.value.trim()) errors.isbn = 'ISBN 不能为空'
  else if (isbn.value.trim().length > 20) errors.isbn = 'ISBN 最多 20 个字符'

  const stockValue = Number(stock.value)
  if (stock.value === '' || !Number.isInteger(stockValue) || stockValue < 0) {
    errors.stock = '库存必须为大于等于 0 的整数'
  }

  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submit() {
  errorCode.value = ''
  errorMessage.value = ''
  if (!validate()) {
    errorCode.value = 'VALIDATION_ERROR'
    errorMessage.value = '请检查表单填写内容'
    return
  }

  submitting.value = true
  try {
    const created = await createBook({
      title: title.value.trim(),
      author: author.value.trim(),
      isbn: isbn.value.trim(),
      stock: Number(stock.value)
    })
    await router.push(`/books/${created.id}`)
  } catch (error) {
    const info = formatError(error)
    errorCode.value = info.code
    errorMessage.value = info.message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="card">
    <header class="card-head">
      <h2>新增图书</h2>
      <RouterLink class="btn ghost" to="/books">返回列表</RouterLink>
    </header>

    <p v-if="errorMessage" class="alert error">
      <strong>{{ errorCode }}</strong>
      <span>{{ errorMessage }}</span>
    </p>

    <form class="form" @submit.prevent="submit">
      <label class="field">
        <span class="label">书名 <em>*</em></span>
        <input v-model="title" type="text" maxlength="200" placeholder="例如：深入理解计算机系统" />
        <span v-if="fieldErrors.title" class="field-error">{{ fieldErrors.title }}</span>
      </label>

      <label class="field">
        <span class="label">作者 <em>*</em></span>
        <input v-model="author" type="text" maxlength="120" placeholder="例如：Randal E. Bryant" />
        <span v-if="fieldErrors.author" class="field-error">{{ fieldErrors.author }}</span>
      </label>

      <label class="field">
        <span class="label">ISBN <em>*</em></span>
        <input v-model="isbn" type="text" maxlength="20" placeholder="例如：9787111544937" />
        <span v-if="fieldErrors.isbn" class="field-error">{{ fieldErrors.isbn }}</span>
      </label>

      <label class="field">
        <span class="label">库存</span>
        <input v-model="stock" type="number" min="0" step="1" placeholder="默认 0" />
        <span v-if="fieldErrors.stock" class="field-error">{{ fieldErrors.stock }}</span>
      </label>

      <div class="form-actions">
        <button class="btn primary" type="submit" :disabled="submitting">
          {{ submitting ? '提交中…' : '创建图书' }}
        </button>
        <RouterLink class="btn ghost" to="/books">取消</RouterLink>
      </div>
    </form>
  </section>
</template>
