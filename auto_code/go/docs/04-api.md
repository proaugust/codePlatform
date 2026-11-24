# 接口清单

统一响应结构（`GET /health` 除外）：
- 成功：`{"code":0,"message":"...","data":...}`
- 失败：`{"code":<HTTP状态>,"message":"<说明>","error":"<错误码>"}`

错误码：`VALIDATION_ERROR`（400）、`NOT_FOUND`（404）、`INTERNAL_ERROR`（500）。

## GET /health
- 描述：健康检查（不包 data 包装）。
- 响应 200：`{"status":"ok"}`

## GET /api/books
- 描述：图书列表。
- 响应 200：`data` 为 Book 数组。

## POST /api/books
- 描述：新增图书，id 由数据库自增。
- 请求体：`{"title":"string","author":"string","stock":0}`
- 响应 201：`data` 为新建 Book。
- 错误：400 `VALIDATION_ERROR`。

## GET /api/books/{id}
- 描述：按 id 查询。
- 响应 200：`data` 为 Book。
- 错误：400 / 404。

## PUT /api/books/{id}
- 描述：修改图书，id 以路径为准。
- 请求体：`{"title":"string","author":"string","stock":0}`
- 响应 200：`data` 为更新后 Book。
- 错误：400 `VALIDATION_ERROR`、404 `NOT_FOUND`。

## DELETE /api/books/{id}
- 描述：删除图书。
- 响应 204：无响应体。
- 错误：400 / 404。

## PATCH /api/books/{id}/stock
- 描述：设置库存（绝对值）。
- 请求体：`{"stock":0}`（**只认 stock，不认 delta**）。
- 响应 200：`data` 为更新后 Book。
- 错误：400 / 404。

## GET /
- 描述：API 占位信息 JSON（业务 UI 在 Vite `:5175`）。
