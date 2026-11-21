# 架构设计

## 总体架构
采用经典三层结构（Handler / Service / Repository），基于 Go 标准库 `net/http` 与 `http.ServeMux`（Go 1.22 支持方法+路径模式匹配）。

```
浏览器(静态页面) --HTTP--> net/http ServeMux
                              ├── /health            (健康检查)
                              ├── /api/books...      (Handler 层)
                              └── /                  (静态资源托管)
                                    │
                              Service 层（业务校验）
                                    │
                              Repository 层（内存存储 + RWMutex）
```

## 分层与模块
### Handler 层（`internal/handler`）
- 路由注册与请求解析（路径参数 `{id}`、JSON 请求体）。
- 统一响应封装：成功 `{data:...}` 或直接对象；错误 `{error:{code,message}}`。
- CORS 中间件：允许 `http://localhost:5173`、`http://localhost:5174`，方法含 GET/POST/PATCH/DELETE/OPTIONS。
- 静态资源：`GET /` 返回 `web/index.html`，`/static/` 提供 CSS/JS。

### Service 层（`internal/service`）
- 图书业务规则：ID 校验、库存非负、删除存在性校验。
- 将 Repository 错误映射为业务错误（NotFound / InvalidArgument / Conflict）。

### Repository 层（`internal/repository`）
- 内存存储：`map[int]*Book` + 自增 ID 计数器 + `sync.RWMutex`。
- 方法：`List`、`Get`、`Create`、`Delete`、`UpdateStock`。

### 模型（`internal/model`）
- `Book{ID int, Title string, Author string, Stock int}`。

## 技术选型
- 语言：Go 1.22。
- Web：标准库 `net/http`、`encoding/json`。
- 并发：`sync.RWMutex`。
- 前端：原生 HTML/CSS/JS，`fetch` 调用 API，无构建步骤。

## 部署与运行
- 单二进制部署，静态资源通过 `embed.FS` 或相对路径 `web/` 读取（推荐 `embed` 便于打包）。
- 监听端口 8072，可通过环境变量 `PORT` 覆盖（默认 8072）。
- 启动命令：`go run .`。

## 关键设计决策
- 删除接口使用 `DELETE /api/books/{id}`，路径参数为整数 ID。
- 删除不存在返回 404；ID 非法返回 400。
- 删除成功返回 204 No Content（或 200 + JSON，二选一，本设计采用 204）。
- 前端删除后重新 `GET /api/books` 刷新列表。
