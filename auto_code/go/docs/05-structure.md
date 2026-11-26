# 工程结构（go）

- 扫描根目录：`D:\code\py\demo\codePlatform\auto_code\go`
- 是否存在代码：是

## 构建（go.mod）

- 路径：`go.mod`
- module：`example.com/autocode`
- go：`1.22`
- 依赖：`github.com/jackc/pgx/v5`（PostgreSQL）

## 源码（分层）

- `main.go`：组装 repository → service → handler，监听 `127.0.0.1:8072`
- `internal/model`：`Book` 与请求体
- `internal/repository`：PostgreSQL 访问与建表
- `internal/service`：校验与业务错误
- `internal/handler`：HTTP 路由、统一 JSON 响应、CORS

## 配套前端

- `auto_code/frontend`（与 go 同级），端口 5175

## API 面

- `GET /health`
- `GET /api/books`
- `POST /api/books`
- `GET /api/books/{id}`
- `PUT /api/books/{id}`
- `DELETE /api/books/{id}`
- `PATCH /api/books/{id}/stock`
- `GET /`
