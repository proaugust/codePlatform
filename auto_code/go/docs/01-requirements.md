# 图书管理 REST API 需求说明

## 背景
当前 `auto_code/go` 为空工程（无 go.mod、无源码）。需从零构建一个基于 Go 标准库 `net/http` 的图书管理后端服务，供前端（Vite 开发服务器 5173/5174/5175）调用。数据采用进程内内存存储，不依赖任何外部数据库或第三方 Web 框架。

## 目标
- 提供图书的增删改查与库存调整 REST 接口。
- 提供健康检查与根路径探活接口。
- 统一错误响应格式，便于前端统一处理。
- 支持跨域访问，满足本地前端联调。

## 范围
### 包含
- `GET /health`、`GET /` 返回 `{"status":"ok"}`。
- `GET /api/books` 列表查询，支持可选 `keyword` 模糊匹配（标题/作者/ISBN）。
- `GET /api/books/{id}` 单本查询。
- `POST /api/books` 新建图书，成功返回 201。
- `PATCH /api/books/{id}/stock` 调整库存。
- `DELETE /api/books/{id}` 删除图书，成功返回 204。
- 统一错误 JSON：`code/message/path/timestamp`。
- 404 图书不存在、409 ISBN 重复。
- CORS 允许 `http://localhost:5173/5174/5175` 与 `http://127.0.0.1:5173/5174/5175`。

### 不包含
- 持久化存储、分页、排序、鉴权、限流、审计日志。
- 图书更新（PUT）接口（仅库存 PATCH）。

## 非功能需求
- 仅使用 Go 标准库，禁止第三方 Web 框架。
- 监听端口 8072。
- 内存存储需并发安全（读写锁保护）。
- 响应统一 `Content-Type: application/json; charset=utf-8`。
- 请求体大小限制（如 1MB），JSON 解析失败返回 400。
- 服务启动日志输出监听地址。

## 假设
- 图书 ID 由服务端自增生成（int64）。
- ISBN 全局唯一，重复创建返回 409。
- `stock` 为非负整数，PATCH 时直接设置为目标值。
- 内存数据在进程重启后丢失，属预期行为。
