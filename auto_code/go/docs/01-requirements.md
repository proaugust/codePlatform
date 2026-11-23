# 图书管理修改功能增量需求

## 背景
现有 Go net/http 图书管理项目已具备列表、新增、删除与静态页面托管能力，但用户反馈「修改图书接口未生成成功、前端看不到修改入口」。本次为增量补齐修改闭环，不重写系统、不更换技术栈。

## 目标
1. 后端提供可用的修改图书接口 `PUT /api/books/{id}`，按路径 id 更新图书 title、author、stock。
2. 前端图书列表每行提供可见的「编辑」按钮，点击弹出预填表单，保存后调用修改接口并刷新列表。
3. 修复此前修改接口与前端编辑入口缺失的问题。

## 范围
### 后端
- 新增 `PUT /api/books/{id}`：请求体含 title、author、stock；id 以路径参数为准。
- 成功返回更新后的图书数据；图书不存在返回 404 `NOT_FOUND`；非法 id 或校验失败返回 400 `VALIDATION_ERROR`。
- 保留并兼容现有 `GET /api/books`、`POST /api/books`、`GET /api/books/{id}`、`DELETE /api/books/{id}`、`PATCH /api/books/{id}/stock`。
- 保留 `GET /health` 返回 `{"status":"ok"}`。
- 保留根路径与 `/static/` 静态页面托管。

### 前端
- 图书列表每行增加「编辑」按钮。
- 点击后弹出编辑表单，预填当前图书 title、author、stock。
- 保存时调用 `PUT /api/books/{id}`，成功后关闭表单并刷新列表；失败展示错误信息。
- 保留现有新增、删除交互。

## 非功能
- 仅使用 Go 标准库 net/http，不引入第三方 Web 框架。
- 统一 JSON 响应结构与错误码（`VALIDATION_ERROR`、`NOT_FOUND`）。
- 启用 CORS 允许 Vite 5173/5174 开发端口。
- 服务端口 8072，前后端同端口托管。
- 修改操作做基本输入校验：id 必须为正整数，title 非空，stock 为非负整数。

## 假设
- 数据存储沿用内存存储（与现有实现一致），不引入数据库持久化。
- 新增图书 id 由后端自动生成，前端不传 id。
- 端口以 8072 为准。
- 前端为后端托管的静态 HTML/JS 页面，非独立 Vue 工程。
