# 变更报告（Review）

- 语言：`go`
- 模式：从零生成
- 方案摘要：用 Go 标准库 net/http 从零实现端口 8072 的图书管理 REST API，内存并发安全存储，覆盖探活、图书增删查、库存 PATCH、统一错误 JSON 与 5173/5174/5175 的 CORS 预检。
- 生成文件数：2
- 校验通过：是
- 修复次数：0

## 端点

- `GET /health` — 健康检查，返回 200 与 {"status":"ok"}
- `GET /` — 根路径探活，返回 200 与 {"status":"ok"}
- `GET /api/books` — 图书列表，可选 keyword 对 title/author/isbn 忽略大小写模糊匹配，无数据返回 []
- `GET /api/books/{id}` — 按 id 查询单本图书，id 非法 400，不存在 404
- `POST /api/books` — 创建图书，body {title,author,isbn,stock}，成功 201 返回含自增 id 的对象，ISBN 重复 409
- `PATCH /api/books/{id}/stock` — 直接设置库存目标值，body {stock}，成功 200 返回更新后对象，不存在 404
- `DELETE /api/books/{id}` — 删除图书，成功 204 无响应体，再次删除 404
- `OPTIONS /api/books` — CORS 预检，白名单 Origin 返回 204 与允许方法/头

## 文件清单

- `go.mod`
- `main.go`

## 配套 Vue 前端

- 跳过：当前仅支持为 java 生成 Vue 前端，跳过: go
