# 总需求

## 背景
现有 Go 标准库 net/http 图书管理项目已具备图书列表、新增、删除与静态页面托管能力，但「修改图书」闭环缺失：后端修改接口未成功落地，前端页面也没有可见的编辑入口。本次为增量补齐，不重写为无关新系统。

## 目标
1. 提供可用的修改图书后端接口，按 id 更新图书信息（title、author、stock）。
2. 在前端图书列表每行提供可见、可操作的「编辑」入口，保存后刷新列表。
3. 修复此前修改接口与前端编辑入口未生成成功的问题。

## 范围
### 后端
- 新增 `PUT /api/books/{id}`：请求体包含 title、author、stock，id 以路径参数为准。
- 成功返回更新后的图书数据；图书不存在返回 404 `NOT_FOUND`；非法 id 或校验失败返回 400 `VALIDATION_ERROR`。
- 保留并兼容现有 `GET /api/books`、`POST /api/books`、`GET /api/books/{id}`、`DELETE /api/books/{id}`、`PATCH /api/books/{id}/stock`。
- 保留 `GET /health` 返回 `{"status":"ok"}`。
- 为 Vite 5173/5174 开启 CORS。

### 前端
- 图书列表每行增加「编辑」按钮。
- 点击后弹出编辑表单，预填当前图书 title、author、stock。
- 保存时调用 `PUT /api/books/{id}`，成功后关闭表单并刷新列表；失败时展示错误信息。
- 保留现有新增、删除交互与根路径静态页面托管。

## 非功能
- 仅使用 Go 标准库 net/http，不引入第三方 Web 框架。
- 统一 JSON 响应结构与错误码（`VALIDATION_ERROR`、`NOT_FOUND`）。
- 前后端同端口 8072 托管，静态页面可直接访问。
- 修改操作做基本输入校验：id 必须为大于 0 的整数，title 非空，stock 为非负整数。
- 与现有新增、删除接口风格保持一致，便于前端复用。

## 假设
- 数据存储沿用内存实现（见 assumptions）。
- 服务端口以基线 8072 为准。
- 新增图书 id 由后端自动生成，前端不传 id。
