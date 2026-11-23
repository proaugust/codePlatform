# 接口清单

统一响应结构：
- 成功：`{"code":0,"message":"ok","data":{...}}`
- 失败：`{"code":<非0>,"message":"<错误信息>","error":"<错误码>"}`

错误码：`VALIDATION_ERROR`（400）、`NOT_FOUND`（404）、`INTERNAL_ERROR`（500）。

## GET /health
- 描述：健康检查。
- 响应 200：`{"status":"ok"}`

## GET /api/books
- 描述：图书列表。
- 响应 200：`data` 为 Book 数组。

## POST /api/books
- 描述：新增图书，id 由后端生成。
- 请求体：`{"title":"string","author":"string","stock":0}`
- 响应 201：`data` 为新建 Book。
- 错误：400 `VALIDATION_ERROR`（title 为空或 stock 为负）。

## GET /api/books/{id}
- 描述：按 id 查询。
- 响应 200：`data` 为 Book。
- 错误：400 `VALIDATION_ERROR`（id 非正整数）、404 `NOT_FOUND`。

## PUT /api/books/{id}
- 描述：修改图书，id 以路径为准。
- 路径参数：`id` 正整数。
- 请求体：`{"title":"string","author":"string","stock":0}`
- 响应 200：`data` 为更新后的 Book。
- 错误：
  - 400 `VALIDATION_ERROR`：id 非正整数、title 为空、stock 为负或请求体非法 JSON。
  - 404 `NOT_FOUND`：图书不存在。

## DELETE /api/books/{id}
- 描述：删除图书。
- 响应 204：无响应体。
- 错误：400 `VALIDATION_ERROR`（id 非正整数）、404 `NOT_FOUND`。

## PATCH /api/books/{id}/stock
- 描述：调整库存（保留现有能力）。
- 请求体：`{"stock":0}`
- 响应 200：`data` 为更新后的 Book。
- 错误：400 `VALIDATION_ERROR`、404 `NOT_FOUND`。

## GET / 与 GET /static/
- 描述：托管前端静态页面。
- 响应 200：HTML/JS/CSS 资源。
