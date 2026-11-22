# 接口清单

统一响应约定：
- 成功：直接返回业务 JSON 对象或数组。
- 失败：`{"error":{"code":"VALIDATION_ERROR|NOT_FOUND","message":"..."}}`。
- 所有接口支持 CORS（允许 5173/5174）。

## GET /health
- 说明：健康检查。
- 响应 200：`{"status":"ok"}`。

## GET /api/books
- 说明：图书列表。
- 响应 200：`[{"id":1,"title":"...","author":"...","stock":10}]`。

## POST /api/books
- 说明：新增图书，id 由后端生成。
- 请求体：`{"title":"...","author":"...","stock":10}`。
- 响应 201：新增后的图书对象。
- 错误 400 `VALIDATION_ERROR`：title 为空或 stock 为负。

## GET /api/books/{id}
- 说明：按 id 查询图书。
- 响应 200：图书对象。
- 错误 400 `VALIDATION_ERROR`：id 非法。
- 错误 404 `NOT_FOUND`：图书不存在。

## PUT /api/books/{id}
- 说明：修改图书，id 以路径参数为准，请求体中的 id 被忽略。
- 请求体：`{"title":"...","author":"...","stock":10}`。
- 响应 200：更新后的图书对象。
- 错误 400 `VALIDATION_ERROR`：id 非法、title 为空、stock 为负。
- 错误 404 `NOT_FOUND`：图书不存在。

## DELETE /api/books/{id}
- 说明：删除图书。
- 响应 204：无响应体。
- 错误 400 `VALIDATION_ERROR`：id 非法。
- 错误 404 `NOT_FOUND`：图书不存在。

## PATCH /api/books/{id}/stock
- 说明：调整库存。
- 请求体：`{"stock":5}`。
- 响应 200：更新后的图书对象。
- 错误 400 `VALIDATION_ERROR`：id 非法或 stock 为负。
- 错误 404 `NOT_FOUND`：图书不存在。

## GET / 与 GET /static/
- 说明：静态页面与资源托管，返回前端页面。
