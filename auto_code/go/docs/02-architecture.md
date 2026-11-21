# 架构

## 分层
- **Handler 层**（`internal/handler`）：HTTP 路由处理、参数解析与校验、JSON 响应封装、CORS、静态资源托管。
- **Service 层**（`internal/service`）：业务规则（删除前存在性校验、错误语义映射），返回领域错误。
- **Repository 层**（`internal/repository`）：内存存储读写，使用 `sync.RWMutex` 保证并发安全。
- **Model 层**（`internal/model`）：图书实体定义。

## 模块与技术选型
- 语言/运行时：Go 1.22，module `example.com/autocode`。
- Web：标准库 `net/http`，使用 `http.ServeMux` 的路径模式（`GET /api/books/{id}`、`DELETE /api/books/{id}`）。
- 静态托管：`internal/handler/static.go` 提供 `/` 与 `/static/` 静态文件服务。
- 并发：Repository 内 `sync.RWMutex`。
- 前端：纯静态 HTML/CSS/JS（`fetch` 调用 API），无构建步骤。

## 请求处理流程（删除）
1. 前端选中图书，点击删除并二次确认。
2. 发起 `DELETE /api/books/{id}`。
3. Handler 解析并校验 `id`（必须为大于 0 的整数，否则 400 `VALIDATION_ERROR`）。
4. Service 调用 Repository 删除；不存在返回 404 `NOT_FOUND`。
5. 成功返回 200/204 与统一 JSON；前端刷新列表。

## 部署
- 单进程二进制，监听 `:8072`，同时提供 API 与静态页面。
- 访问入口：`http://localhost:8072/`；健康检查：`http://localhost:8072/health`。
