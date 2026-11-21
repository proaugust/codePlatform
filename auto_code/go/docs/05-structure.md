# 工程结构（go）

- 扫描根目录：`D:\code\py\demo\codePlatform\auto_code\go`
- 是否存在代码：是

## 构建（go.mod）

- 路径：`go.mod`
- module：`example.com/autocode`
- go：`1.22`

## 三层路径

### Handler

- （无）

### Service

- （无）

### Repository

- （无）

> 未按命名约定识别到三层目录/类；见下方文件树摘要。

### 源码路径摘要

- `main.go`

## API 面

- `* GET /health` — `main.go`
- `* GET /{$}` — `main.go`
- `* GET /api/books` — `main.go`
- `* POST /api/books` — `main.go`
- `* GET /api/books/{id}` — `main.go`
- `* DELETE /api/books/{id}` — `main.go`
- `* PATCH /api/books/{id}/stock` — `main.go`
- `* /` — `main.go`
- `GET /health` — `main.go`
- `GET /{$}` — `main.go`
- `GET /api/books` — `main.go`
- `POST /api/books` — `main.go`
- `GET /api/books/{id}` — `main.go`
- `DELETE /api/books/{id}` — `main.go`
- `PATCH /api/books/{id}/stock` — `main.go`
