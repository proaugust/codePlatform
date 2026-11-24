# 图书管理修改功能增量需求

## 背景
现有 Go net/http 图书管理 API 已具备列表、新增、删除与库存调整能力，但「修改图书」闭环曾缺失。业务前端为共用 Vue（`auto_code/frontend`，端口 5175）。数据持久化使用 PostgreSQL。

## 目标
1. 后端提供可用的修改图书接口 `PUT /api/books/{id}`，按路径 id 更新 title、author、stock。
2. 前端图书列表每行提供可见「编辑」按钮，弹窗预填表单，保存后调用 PUT 并刷新列表。
3. 库存调整接口 `PATCH /api/books/{id}/stock` 只认绝对值 `{ "stock": N }`。

## 范围
### 后端（入口：`main.go`，`go run .`）
- `PUT /api/books/{id}`：请求体 title、author、stock；id 以路径为准。
- 成功返回统一包装 `{code:0,message,data}`；失败 `{code:<http>,message,error:<码>}`。
- 保留 GET/POST/DELETE 图书接口、`PATCH .../stock`、`GET /health`。
- 监听 `127.0.0.1:8072`；CORS 允许 5173–5175。
- 存储：PostgreSQL（`pgx`），默认 `DATABASE_URL` 或 `postgresql://postgres:postgres@localhost:5435/ai_test`。

### 前端
- 目录：`auto_code/frontend`（Vite 5175），非后端 static 托管。
- 列表「编辑」弹窗 + `updateBook` / 库存只发 `{stock}`。

## 非功能
- Web 框架：Go 标准库 `net/http`；允许 `jackc/pgx` 访问 PostgreSQL。
- 统一 JSON 错误码：`VALIDATION_ERROR`、`NOT_FOUND`、`INTERNAL_ERROR`。

## 假设
- 唯一运行入口为 `main.go`（无 `internal/` 分层包）。
- 新增图书 id 由数据库自增生成。
