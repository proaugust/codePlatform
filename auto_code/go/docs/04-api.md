# 接口清单

## 通用约定
- 请求/响应均为 `application/json`（静态页面除外）。
- 错误响应统一结构：
```json
{"error":{"code":"NOT_FOUND","message":"book not found"}}
```
- 启用 CORS，允许来源 `http://localhost:5173`、`http://localhost:5174`。

## 1. 健康检查
- **GET** `/health`
- 响应 200：`{"status":"ok"}`

## 2. 图书列表
- **GET** `/api/books`
- 响应 200：`[{"id":1,"title":"...","author":"...","stock":10,"created_at":"..."}]`

## 3. 新增图书
- **POST** `/api/books`
- 请求：`{"title":"...","author":"...","stock":10}`
- 响应 201：图书对象
- 错误：400 参数非法

## 4. 图书详情
- **GET** `/api/books/{id}`
- 响应 200：图书对象
- 错误：400 ID 非法；404 图书不存在

## 5. 删除图书（核心）
- **DELETE** `/api/books/{id}`
- 路径参数：`id` 整数
- 响应 200：`{"deleted":true,"id":1}`
- 错误：
  - 400 `INVALID_ID`：ID 非整数
  - 404 `NOT_FOUND`：图书不存在
  - 500 `INTERNAL`：内部错误

## 6. 库存调整
- **PATCH** `/api/books/{id}/stock`
- 请求：`{"delta":-1}`
- 响应 200：更新后的图书对象
- 错误：400 参数非法；404 图书不存在

## 7. 静态页面
- **GET** `/`：返回 `index.html`，页面内通过 fetch 调用上述 API。
