# 架构设计

## 分层结构
采用经典三层结构，全部位于 `auto_code/go` 根目录下的包内：

- **Handler 层**：HTTP 路由注册、请求解析、参数校验、响应序列化、CORS 与错误中间件。
- **Service 层**：业务规则（ISBN 唯一性校验、库存非负校验、ID 生成、关键字过滤）。
- **Repository 层**：内存存储实现，使用 `sync.RWMutex` + `map[int64]*Book` 保证并发安全。

## 模块划分
- `main.go`：程序入口，初始化依赖、注册路由、启动 `http.Server`（端口 8072）。
- `model.go`：`Book` 实体与请求/响应 DTO 定义。
- `repository.go`：内存仓储接口与实现。
- `service.go`：业务服务。
- `handler.go`：HTTP 处理器与路由分发。
- `middleware.go`：CORS、统一错误响应、panic 恢复。
- `errors.go`：业务错误类型与错误码常量。

## 技术选型
- 语言：Go（建议 1.21+，使用标准库 `net/http`、`encoding/json`、`sync`、`strconv`、`strings`、`time`）。
- 路由：`http.ServeMux`（Go 1.22+ 支持方法+路径参数模式，如 `GET /api/books/{id}`）；若使用较低版本则手动解析路径。
- 存储：进程内 `map` + 读写锁。
- 无第三方依赖。

## 部署
- 单二进制部署，`go build -o bookapi .` 后运行，默认监听 `:8072`。
- 可通过环境变量 `PORT` 覆盖端口（默认 8072）。

## 关键设计
- 统一错误结构体 `ErrorResponse{Code, Message, Path, Timestamp}`。
- CORS 中间件对白名单 Origin 回写 `Access-Control-Allow-Origin`，处理 `OPTIONS` 预检返回 204。
- 请求体使用 `http.MaxBytesReader` 限制大小。
