# 需求结论（澄清确认）

## 摘要
在现有 Go net/http 图书 API 上补齐修改图书闭环；业务前端为 `auto_code/frontend`（Vite 5175）。**已确认**：唯一入口 `main.go`；持久化 **PostgreSQL（pgx）**；库存 PATCH **只认 `{stock}`**；删除未接线 `internal/`。

## 目标
- 提供可用的 `PUT /api/books/{id}` 修改接口
- 前端列表可见编辑入口，保存后刷新列表
- 统一响应包装与库存绝对值契约

## 范围
- 后端：`main.go` + PostgreSQL
- 前端：`auto_code/frontend` Vue
- 保留列表/新增/删除/库存/健康检查

## 不在范围
- 不恢复 `internal/` 分层
- 不以后端 static 作为主 UI
- 不引入登录权限

## 非功能
- Web：net/http；DB：允许 pgx
- 监听 `127.0.0.1:8072`
- 默认 DB：`postgresql://postgres:postgres@localhost:5435/ai_test`（可用 `DATABASE_URL`）

## 已确认决策
- 存储：PostgreSQL（非内存）
- 库存：只认 `{stock}` 绝对值
- 前端：Vue@5175
- 入口：`go run .` → `main.go`

## 硬约束
- 必须提供 GET /health
- 增量修改，禁止无故改成无关新业务
