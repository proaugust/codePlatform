# 接口清单

统一响应结构：
- 成功：`{"code":"OK","message":"success","data":...}`
- 失败：`{"code":"<ERROR_CODE>","message":"<描述>","data":null}`

## GET /health
- 描述：健康检查。
- 响应 200：`{"status":"ok"}`

## GET /api/books
- 描述：图书列表。
- 响应 200：`{"code":"OK","message":"success","data":[{"id":1,"title":"...","author":"...","stock":10}]}`

## POST /api/books
- 描述：新增图书。
- 请求体：`{"title":"...","author":"...","stock":10}`
- 校验：`title`/`author` 非空；`stock >= 0`；若请求携带 `id`，必须为大于 0 的整数，否则返回 400 `VALIDATION_ERROR`（消息：`图书 id 必须为大于 0 的整数`）。
- 响应 201：`{"code":"OK","message":"success","data":{"id":2,...}}`
- 错误：400 `VALIDATION_ERROR`

## GET /api/books/{id}
- 描述：图书详情。
- 路径参数：`id` 必须为大于 0 的整数。
- 响应 200：`{"code":"OK","message":"success","data":{...}}`
- 错误：400 `VALIDATION_ERROR`；404 `NOT_FOUND`

## DELETE /api/books/{id}
- 描述：删除指定图书（用户硬需求）。
- 路径参数：`id` 必须为大于 0 的整数。
- 响应 200：`{"code":"OK","message":"deleted","data":{"id":1}}`
- 错误：
  - 400 `VALIDATION_ERROR`：id 非法（非整数或 <= 0），消息 `图书 id 必须为大于 0 的整数`
  - 404 `NOT_FOUND`：图书不存在，消息 `图书不存在`
  - 500 `INTERNAL_ERROR`：内部错误

## PATCH /api/books/{id}/stock
- 描述：调整库存（沿用现有能力）。
- 请求体：`{"delta":-1}`
- 响应 200：`{"code":"OK","message":"success","data":{...}}`
- 错误：400 `VALIDATION_ERROR`；404 `NOT_FOUND`

## 错误码汇总
| 错误码 | HTTP 状态 | 说明 |
| --- | --- | --- |
| VALIDATION_ERROR | 400 | 参数校验失败 |
| NOT_FOUND | 404 | 资源不存在 |
| INTERNAL_ERROR | 500 | 服务内部错误 |

## CORS
- 允许来源：`http://localhost:5173`、`http://localhost:5174`
- 允许方法：GET、POST、PATCH、DELETE、OPTIONS
- 允许头：Content-Type
