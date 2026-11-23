# 架构设计

## 分层
沿用现有三层结构：
- Handler 层：`internal/handler/book_handler.go` 负责路由解析、请求解码、响应输出；`response.go` 统一 JSON 与错误码；`static.go` 托管静态页面。
- Service 层：`internal/service/book_service.go` 承载业务校验与更新逻辑；`errors.go` 定义业务错误。
- Repository 层：`internal/repository/book_repository.go` 内存存储，提供按 id 查询与更新。
- Model 层：`internal/model/book.go` 定义 Book 结构体。

## 技术选型
- 语言：Go 1.22，module `example.com/autocode`。
- Web：标准库 `net/http`，使用 `http.ServeMux` 路径模式（含 `{id}` 路径参数）。
- 存储：进程内内存 map/slice，带读写锁。
- 前端：静态 HTML + 原生 JS，由后端同端口托管。

## 模块职责
- `main.go`：注册路由、CORS 中间件、启动 8072 端口。
- `book_handler.go`：新增 `UpdateBook` 处理函数，解析路径 id、解码请求体、调用 service、输出结果。
- `book_service.go`：新增 `UpdateBook(id, input)`，校验 id/title/stock，调用 repository 更新，返回更新后实体或错误。
- `book_repository.go`：新增 `Update(book)` 方法，存在则覆盖并返回，不存在返回未找到。
- 前端页面：列表渲染每行追加「编辑」按钮，弹窗表单提交 PUT 请求。

## 部署
单进程监听 `:8072`，静态资源与 API 同源，无需额外反向代理。
