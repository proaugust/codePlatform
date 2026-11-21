# 接口清单

基础路径：`http://localhost:8070`，统一 JSON。

## 健康检查
### GET /health
- 响应 200：`{"status":"ok"}`
- 错误码：无（轻量端点，不依赖外部组件）

## 图书接口

### GET /api/books
- 响应 200：`BookResponse[]`

### GET /api/books/{id}
- 响应 200：`BookResponse`
- 错误码：404 图书不存在

### POST /api/books
- 请求体：`{"title":"...","author":"...","isbn":"...","stock":10}`
- 响应 201：`BookResponse`
- 错误码：400 参数校验失败；409 ISBN 重复

### PATCH /api/books/{id}/stock
- 请求体：`{"stock":5}`
- 响应 200：`BookResponse`
- 错误码：400 参数非法；404 图书不存在

### DELETE /api/books/{id}（新增）
- 说明：按 ID 删除指定图书，供前端选择目标后调用。
- 路径参数：`id`（Long，必填）
- 响应 204：无响应体
- 错误码：
  - 404：图书不存在（`{"code":"BOOK_NOT_FOUND","message":"图书不存在"}`）
  - 400：ID 格式非法
  - 500：服务器内部错误

## 统一错误响应
```json
{"code":"BOOK_NOT_FOUND","message":"图书不存在","timestamp":"2024-01-01T00:00:00Z"}
```

## 错误码汇总
| HTTP | code | 场景 |
|------|------|------|
| 400 | VALIDATION_ERROR | 参数校验失败 |
| 404 | BOOK_NOT_FOUND | 图书不存在 |
| 409 | ISBN_DUPLICATED | ISBN 重复 |
| 500 | INTERNAL_ERROR | 未预期异常 |
