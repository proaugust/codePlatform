# 工程结构（go）

- 扫描根目录：`D:\code\py\demo\codePlatform\auto_code\go`
- 是否存在代码：是

## 构建（go.mod）

- 路径：`go.mod`
- module：`example.com/autocode`
- go：`1.22`

## 三层路径

### Handler

- `internal/handler/book_handler.go`
- `internal/handler/response.go`
- `internal/handler/static.go`

### Service

- `internal/service/book_service.go`
- `internal/service/errors.go`

### Repository

- `internal/repository/book_repository.go`

### 源码路径摘要

- `internal/handler/book_handler.go`
- `internal/handler/response.go`
- `internal/handler/static.go`
- `internal/model/book.go`
- `internal/repository/book_repository.go`
- `internal/service/book_service.go`
- `internal/service/errors.go`
- `main.go`

## API 面

- `* GET /health` — `main.go`
- `* GET /api/books` — `main.go`
- `* POST /api/books` — `main.go`
- `* GET /api/books/{id}` — `main.go`
- `* PUT /api/books/{id}` — `main.go`
- `* DELETE /api/books/{id}` — `main.go`
- `* PATCH /api/books/{id}/stock` — `main.go`
- `* GET /static/` — `main.go`
- `* GET /{$}` — `main.go`
- `GET /health` — `main.go`
- `GET /api/books` — `main.go`
- `POST /api/books` — `main.go`
- `GET /api/books/{id}` — `main.go`
- `PUT /api/books/{id}` — `main.go`
- `DELETE /api/books/{id}` — `main.go`
- `PATCH /api/books/{id}/stock` — `main.go`
- `GET /static/` — `main.go`
- `GET /{$}` — `main.go`
- `* GET /api/books` — `internal/handler/book_handler.go`
- `* POST /api/books` — `internal/handler/book_handler.go`
- `* GET /api/books/{id}` — `internal/handler/book_handler.go`
- `* PUT /api/books/{id}` — `internal/handler/book_handler.go`
- `* DELETE /api/books/{id}` — `internal/handler/book_handler.go`
- `* PATCH /api/books/{id}/stock` — `internal/handler/book_handler.go`
- `GET /api/books` — `internal/handler/book_handler.go`
- `POST /api/books` — `internal/handler/book_handler.go`
- `GET /api/books/{id}` — `internal/handler/book_handler.go`
- `PUT /api/books/{id}` — `internal/handler/book_handler.go`
- `DELETE /api/books/{id}` — `internal/handler/book_handler.go`
- `PATCH /api/books/{id}/stock` — `internal/handler/book_handler.go`
- `* GET /{$}` — `internal/handler/static.go`
- `* GET /static/` — `internal/handler/static.go`
- `GET /{$}` — `internal/handler/static.go`
- `GET /static/` — `internal/handler/static.go`
