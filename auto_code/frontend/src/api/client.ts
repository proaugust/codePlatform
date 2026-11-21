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
      '无法连接后端服务，请确认服务已在 127.0.0.1:8070 启动',
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
    const payload = (data ?? {}) as Record<string, unknown>
    const code =
      typeof payload.code === 'string' && payload.code
        ? payload.code
        : `HTTP_${response.status}`
    const message =
      typeof payload.message === 'string' && payload.message
        ? payload.message
        : typeof data === 'string' && data
          ? data
          : `请求失败（HTTP ${response.status}）`
    throw new ApiError(
      response.status,
      code,
      message,
      typeof payload.path === 'string' ? payload.path : path,
      typeof payload.timestamp === 'string' ? payload.timestamp : undefined
    )
  }

  return data as T
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

export function updateStock(id: number, stock: number): Promise<Book> {
  return request<Book>(`/api/books/${id}/stock`, {
    method: 'PATCH',
    body: JSON.stringify({ stock })
  })
}
