用 Go 标准库 net/http 实现图书管理 REST API（端口 8072），进程内内存存储，无需外部数据库。
必须提供：
- GET /health 与 GET / → {"status":"ok"}
- GET /api/books （可选 keyword 查询）
- GET /api/books/{id}
- POST /api/books ，body: {"title","author","isbn","stock"}，201
- PATCH /api/books/{id}/stock ，body: {"stock"}
- DELETE /api/books/{id}，204
统一错误 JSON：code/message/path/timestamp；404 图书不存在；409 ISBN 重复。
CORS 允许 http://localhost:5173/5174/5175 与 127.0.0.1 同端口。
只要 go.mod（module example.com/autocode）与必要 .go 源码，禁止第三方 web 框架。
