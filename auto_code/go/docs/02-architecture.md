# 架构设计

## 入口
- **唯一进程入口**：`main.go`（`go run .` / 运行页启动）。
- 路由、CORS、PostgreSQL Store、统一响应均在 `main.go` 内实现。
- 已移除未接线的 `internal/` 分层包，避免双轨实现。

## 技术选型
- 语言：Go 1.22，module `example.com/autocode`。
- Web：标准库 `net/http` + ServeMux 方法路由。
- 存储：PostgreSQL，驱动 `github.com/jackc/pgx/v5`。
- 业务前端：共用 Vue 工程 `auto_code/frontend`（端口 5175），经 Vite 代理访问 8072。

## 部署
- API 监听 `127.0.0.1:8072`（避免绑定 `0.0.0.0` 触发 Windows 防火墙）。
- 环境变量 `DATABASE_URL` 可选；缺省连接本地 `localhost:5435/ai_test`。
- CORS：localhost / 127.0.0.1 的 5173–5175。

## 请求处理（修改图书）
1. 匹配 `PUT /api/books/{id}`。
2. 解析 id；非法 → 400 `VALIDATION_ERROR`。
3. 解码 JSON；校验 title 非空、stock ≥ 0。
4. 更新 PG 行；不存在 → 404 `NOT_FOUND`。
5. 返回 200，`data` 为更新后 Book。
