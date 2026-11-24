# 工程结构（go）

- 扫描根目录：`D:\code\py\demo\codePlatform\auto_code\go`
- 是否存在代码：是

## 构建（go.mod）

- 路径：`go.mod`
- module：`example.com/autocode`
- go：`1.22`
- 依赖：`github.com/jackc/pgx/v5`（PostgreSQL）

## 源码

- **唯一入口**：`main.go`（路由 + Store + 响应）
- 已删除：`internal/`（历史分层，未接线）

## 配套前端

- `auto_code/frontend`（与 go 同级），端口 5175

## API 面（均在 main.go）

- `GET /health`
- `GET /api/books`
- `POST /api/books`
- `GET /api/books/{id}`
- `PUT /api/books/{id}`
- `DELETE /api/books/{id}`
- `PATCH /api/books/{id}/stock`
- `GET /`
