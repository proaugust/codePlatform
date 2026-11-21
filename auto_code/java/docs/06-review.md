# 变更报告（Review）

- 语言：`java`
- 模式：从零生成
- 方案摘要：从零构建 Spring Boot 3.x + JPA + H2 的简易图书管理后端，提供健康检查、图书查询/新增、库存覆盖更新，统一错误响应并支持 Vite 跨域。
- 生成文件数：16
- 校验通过：是
- 修复次数：0

## 端点

- `GET /health` — 健康检查，固定返回 {"status":"ok"}，不依赖数据库
- `GET /api/books` — 查询图书列表，支持可选 keyword 对书名/作者/ISBN 做不区分大小写模糊匹配，按 id 升序返回
- `GET /api/books/{id}` — 按 id 查询单本图书，不存在返回 404 BOOK_NOT_FOUND，id 非法返回 400 VALIDATION_ERROR
- `POST /api/books` — 新增图书，返回 201 Created 与 Location 头，ISBN 重复返回 409 ISBN_ALREADY_EXISTS
- `PATCH /api/books/{id}/stock` — 按 id 覆盖更新库存（绝对值），库存为负返回 400，图书不存在返回 404 BOOK_NOT_FOUND

## 文件清单

- `pom.xml`
- `src/main/resources/application.yml`
- `src/main/java/com/example/autocode/AutoCodeApplication.java`
- `src/main/java/com/example/autocode/entity/Book.java`
- `src/main/java/com/example/autocode/repository/BookRepository.java`
- `src/main/java/com/example/autocode/dto/CreateBookRequest.java`
- `src/main/java/com/example/autocode/dto/UpdateStockRequest.java`
- `src/main/java/com/example/autocode/dto/BookResponse.java`
- `src/main/java/com/example/autocode/exception/BusinessException.java`
- `src/main/java/com/example/autocode/exception/ErrorResponse.java`
- `src/main/java/com/example/autocode/exception/GlobalExceptionHandler.java`
- `src/main/java/com/example/autocode/service/BookService.java`
- `src/main/java/com/example/autocode/controller/BookController.java`
- `src/main/java/com/example/autocode/controller/HealthController.java`
- `src/main/java/com/example/autocode/config/CorsConfig.java`
- `src/test/java/com/example/autocode/BookApiTest.java`
