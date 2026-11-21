# 接口清单

基础地址：`http://localhost:8072`
所有响应 `Content-Type: application/json; charset=utf-8`。

## 通用错误响应
```json
{
  "code": "BOOK_NOT_FOUND",
  "message": "图书不存在",
  "path": "/api/books/99",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

错误码约定：
- `BAD_REQUEST` 400：请求体非法/参数缺失。
- `BOOK_NOT_FOUND` 404：图书不存在。
- `ISBN_CONFLICT` 409：ISBN 重复。
- `METHOD_NOT_ALLOWED` 405：方法不支持。
- `INTERNAL_ERROR` 500：服务内部错误。

## 1. GET /health
响应 200：
```json
{"status":"ok"}
```

## 2. GET /
响应 200：
```json
{"status":"ok"}
```

## 3. GET /api/books
查询参数：`keyword`（可选，匹配 title/author/isbn，忽略大小写）。
响应 200：
```json
[
  {"id":1,"title":"Go 语言","author":"张三","isbn":"978-7-111","stock":10,"createdAt":"...","updatedAt":"..."}
]
```
无数据返回 `[]`。

## 4. GET /api/books/{id}
路径参数：`id`（int64）。
响应 200：单本图书对象。
错误：400（id 非法）、404（不存在）。

## 5. POST /api/books
请求体：
```json
{"title":"Go 语言","author":"张三","isbn":"978-7-111","stock":10}
```
校验：title/author/isbn 非空，stock >= 0。
响应 201：创建后的图书对象（含 id、createdAt、updatedAt）。
错误：400（校验失败）、409（ISBN 重复）。

## 6. PATCH /api/books/{id}/stock
请求体：
```json
{"stock":5}
```
校验：stock >= 0。
响应 200：更新后的图书对象。
错误：400（stock 非法）、404（不存在）。

## 7. DELETE /api/books/{id}
响应 204：无响应体。
错误：400（id 非法）、404（不存在）。

## CORS
对白名单 Origin（`http://localhost:5173|5174|5175`、`http://127.0.0.1:5173|5174|5175`）返回：
- `Access-Control-Allow-Origin: <origin>`
- `Access-Control-Allow-Methods: GET,POST,PATCH,DELETE,OPTIONS`
- `Access-Control-Allow-Headers: Content-Type`
- `Access-Control-Max-Age: 86400`
`OPTIONS` 预检返回 204。
