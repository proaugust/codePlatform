# 架构

## 分层
- **Handler 层**：`net/http` 路由与请求解析、参数校验、JSON 响应封装。
- **Service 层**：图书业务逻辑（新增、查询、删除、库存调整），负责 ID 生成与存在性校验。
- **Repository 层**：内存存储，使用 `sync.RWMutex` 保证并发安全。
- **静态资源层**：`/` 托管前端页面（HTML/CSS/JS），与 API 同端口。

## 模块
- `main.go`：服务启动、路由注册、CORS 中间件、静态文件服务。
- `handler`：`GET /health`、`GET /api/books`、`POST /api/books`、`GET /api/books/{id}`、`DELETE /api/books/{id}`、`PATCH /api/books/{id}/stock`。
- `service`：图书业务方法，含 `DeleteBook(id int) error`。
- `repository`：内存 `map[int]Book` 或切片 + 锁。
- `static/`：`index.html`、`app.js`、`style.css`。

## 技术选型
- 语言：Go 1.22（`go.mod` module `example.com/autocode`）。
- Web：标准库 `net/http`，使用 Go 1.22 路由模式（`GET /api/books/{id}`）。
- 存储：进程内内存，无外部依赖。
- 前端：原生 HTML + JavaScript（fetch API），无构建步骤。

## 部署
- 单进程部署，监听 `:8080`（可通过环境变量 `PORT` 覆盖，默认 8080）。
- 静态页面与 API 同源，访问 `http://localhost:8080/`。
- 健康检查 `GET /health` 用于探活。
