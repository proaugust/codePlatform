# 接口清单

- 基础地址：`http://localhost:8072`
- 所有响应 `Content-Type: application/json`（静态资源除外）。
- 统一错误响应结构：
```json
{"error":{"code":"NOT_FOUND","message":"book not found"}}
```

## 1. 健康检查
- **GET** `/health`
- 响应 200：
```json
{"status":"ok"}
```

## 2. 图书列表
- **GET** `/api/books`
- 响应 200：
```json
{"data":[{"id":1,"title":"Go 语言","author":"张三","stock":10}]}
```

## 3. 图书详情
- **GET** `/api/books/{id}`
- 路径参数：`id` 整数
- 响应 200：
```json
{"data":{"id":1,"title":"Go 语言","author":"张三","stock":10}}
```
- 错误：400 `INVALID_ID`（ID 非整数）、404 `NOT_FOUND`（图书不存在）

## 4. 创建图书
- **POST** `/api/books`
- 请求体：
```json
{"title":"Go 语言","author":"张三","stock":10}
```
- 响应 201：
```json
{"data":{"id":1,"title":"Go 语言","author":"张三","stock":10}}
```
- 错误：400 `INVALID_ARGUMENT`（title/author 为空或 stock<0）

## 5. 删除图书（核心新增）
- **DELETE** `/api/books/{id}`
- 路径参数：`id` 整数
- 成功响应：204 No Content（无响应体）
- 错误：
  - 400 `INVALID_ID`：ID 非整数
  - 404 `NOT_FOUND`：图书不存在
- 示例：
```
DELETE /api/books/1
→ 204
```

## 6. 调整库存
- **PATCH** `/api/books/{id}/stock`
- 请求体：
```json
{"delta":-1}
```
- 响应 200：
```json
{"data":{"id":1,"title":"Go 语言","author":"张三","stock":9}}
```
- 错误：400 `INVALID_ARGUMENT`（库存不足或参数非法）、404 `NOT_FOUND`

## 7. 静态页面
- **GET** `/`：返回 `index.html`（图书列表 + 删除按钮）。
- **GET** `/static/*`：返回 CSS/JS 静态资源。

## 错误码汇总
| HTTP | code | 说明 |
|------|------|------|
| 400 | INVALID_ID | 路径 ID 非法 |
| 400 | INVALID_ARGUMENT | 请求体参数非法 |
| 404 | NOT_FOUND | 资源不存在 |
| 405 | METHOD_NOT_ALLOWED | 方法不支持 |
| 500 | INTERNAL_ERROR | 服务内部错误 |

## CORS
- 允许来源：`http://localhost:5173`、`http://localhost:5174`
- 允许方法：GET, POST, PATCH, DELETE, OPTIONS
- 允许头：Content-Type
- 预检 `OPTIONS` 返回 204。
