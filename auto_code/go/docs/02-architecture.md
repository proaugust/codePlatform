# 架构

## 分层
- **Handler 层**（`internal/handler`）：解析 HTTP 请求、路径参数、JSON 请求体，调用 Service，统一输出 JSON 与错误码；`response.go` 提供统一响应封装；`static.go` 托管静态页面。
- **Service 层**（`internal/service`）：业务校验与编排，定义领域错误（`errors.go`），如 `ErrValidation`、`ErrNotFound`。
- **Repository 层**（`internal/repository`）：内存数据存储，提供按 id 查询、更新、删除、列表等操作，使用互斥锁保证并发安全。
- **Model 层**（`internal/model`）：`Book` 结构体（ID、Title、Author、Stock）。

## 技术选型
- 语言：Go 1.22，module `example.com/autocode`。
- Web：标准库 `net/http`，使用 Go 1.22 的 `ServeMux` 路径模式（`GET /api/books/{id}` 等）。
- 存储：进程内内存（map + sync.RWMutex）。
- 前端：静态 HTML/JS/CSS，由后端同端口托管于 `/` 与 `/static/`。

## 部署
- 单进程监听 `:8072`，同时提供 API 与静态页面。
- 启动方式：在「运行」页启动进程，访问 `http://localhost:8072/`。
- CORS：允许 `http://localhost:5173`、`http://localhost:5174` 的跨域请求（便于 Vite 开发调试）。

## 请求处理流程（修改图书）
1. 路由匹配 `PUT /api/books/{id}`。
2. Handler 解析 id，非法则返回 400 `VALIDATION_ERROR`。
3. 解析 JSON 请求体，校验 title 非空、stock 非负。
4. Service 调用 Repository 更新；不存在返回 404 `NOT_FOUND`。
5. 返回 200 与更新后的图书 JSON。
