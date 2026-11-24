# 变更报告（Review）

- 语言：`go`
- 模式：增量对齐（入口 / 响应 / 库存 / PG 文档）
- 方案摘要：以 `main.go` + PostgreSQL 为唯一运行入口；统一 `{code,message,data|error}`；库存只认 `{stock}`；删除未接线 `internal/`；文档与 Vue 前端对齐。
- 校验：需本地 `go build ./...`（依赖 PG 仅运行期）
- 修复次数：—

## 端点

- `GET /health` — `{"status":"ok"}`
- `GET/POST /api/books`、`GET/PUT/DELETE /api/books/{id}`
- `PATCH /api/books/{id}/stock` — body 仅 `{stock}`
- `GET /` — API 占位 JSON

## 文件清单

- `main.go`
- `go.mod` / `go.sum`（pgx）
- 删除：`internal/**`
- 文档：`docs/01`～`06`、`docs/ir/spec.json`、`docs/ir/change_plan.json`
- 前端：`auto_code/frontend/src/api/client.ts`、`BookListView.vue`、`BookDetailView.vue`

## 配套 Vue 前端

- 目录：`D:\code\py\demo\codePlatform\auto_code\frontend`
- 端口：`5175`
- 启动：`cd auto_code/frontend && npm install && npm run dev`
