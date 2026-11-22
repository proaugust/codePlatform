import type { Book, CreateBookRequest, HealthResponse } from '../types'

export interface ApiErrorShape {
  code: string
  message: string
  path?: string
  timestamp?: string
}

export class ApiError extends Error {
  status: number
  code: string
  path?: string
  timestamp?: string

  constructor(status: number, code: string, message: string, path?: string, timestamp?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.path = path
    this.timestamp = timestamp
  }
}

export function formatError(error: unknown): ApiErrorShape {
  if (error instanceof ApiError) {
    return {
      code: error.code,
      message: error.message,
      path: error.path,
      timestamp: error.timestamp
    }
  }
  if (error instanceof Error) {
    return { code: 'CLIENT_ERROR', message: error.message }
  }
  return { code: 'UNKNOWN_ERROR', message: '发生未知错误' }
}

/** 后端统一包装 { code, message, data }，取出 data 字段。 */
function unwrapData(payload: unknown): unknown {
  if (payload && typeof payload === 'object' && !Array.isArray(payload) && 'data' in payload) {
    return (payload as { data: unknown }).data
  }
  return payload
}

function readErrorFields(payload: unknown): {
  code?: string
  message?: string
  path?: string
  timestamp?: string
} {
  if (!payload || typeof payload !== 'object') return {}
  const root = payload as Record<string, unknown>
  const nested =
    root.error && typeof root.error === 'object' ? (root.error as Record<string, unknown>) : null
  const src = nested ?? root
  return {
    code: typeof src.code === 'string' ? src.code : undefined,
    message: typeof src.message === 'string' ? src.message : undefined,
    path: typeof src.path === 'string' ? src.path : typeof root.path === 'string' ? root.path : undefined,
    timestamp:
      typeof src.timestamp === 'string'
        ? src.timestamp
        : typeof root.timestamp === 'string'
          ? root.timestamp
          : undefined
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...((init.headers as Record<string, string> | undefined) ?? {})
  }
  if (init.body !== undefined && init.body !== null) {
    headers['Content-Type'] = 'application/json'
  }

  let response: Response
  try {
    response = await fetch(path, { ...init, headers })
  } catch {
    throw new ApiError(
      0,
      'NETWORK_ERROR',
      '无法连接后端服务，请确认业务后端已在 8072 端口启动',
      path
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!response.ok) {
    const err = readErrorFields(data)
    throw new ApiError(
      response.status,
      err.code || `HTTP_${response.status}`,
      err.message ||
        (typeof data === 'string' && data ? data : `请求失败（HTTP ${response.status}）`),
      err.path || path,
      err.timestamp
    )
  }

  return unwrapData(data) as T
}

export function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function listBooks(keyword?: string): Promise<Book[]> {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''
  return request<Book[]>(`/api/books${query}`)
}

export function getBook(id: number): Promise<Book> {
  return request<Book>(`/api/books/${id}`)
}

export function createBook(payload: CreateBookRequest): Promise<Book> {
  return request<Book>('/api/books', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

/** 调整库存：后端以 delta 变更（正数增加、负数减少）。 */
export function updateStock(id: number, delta: number): Promise<Book> {
  return request<Book>(`/api/books/${id}/stock`, {
    method: 'PATCH',
    body: JSON.stringify({ delta })
  })
}

/** 删除图书：成功返回 { id }。 */
export function deleteBook(id: number): Promise<{ id: number }> {
  return request<{ id: number }>(`/api/books/${id}`, { method: 'DELETE' })
}
