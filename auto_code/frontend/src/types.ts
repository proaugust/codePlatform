export interface Book {
  id: number
  title: string
  author: string
  isbn: string
  stock: number
  createdAt?: string
  updatedAt?: string
}

export interface CreateBookRequest {
  title: string
  author: string
  isbn: string
  stock: number
}

export interface UpdateStockRequest {
  stock: number
}

export interface HealthResponse {
  status: string
}
