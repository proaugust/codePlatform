# 架构

## 分层
- **Controller 层**：`BookController`（图书 CRUD，含新增 DELETE）、`HealthController`（`GET /health`）。
- **Service 层**：`BookService`（业务逻辑、事务边界、删除前存在性校验）。
- **Repository 层**：`BookRepository`（JPA，继承 `JpaRepository`）。
- **Entity/DTO 层**：`Book` 实体；`CreateBookRequest`、`UpdateStockRequest`、`BookResponse`。
- **异常层**：`BusinessException`、`ErrorResponse`、`GlobalExceptionHandler`（统一错误响应）。
- **配置层**：`CorsConfig`（允许 Vite 5173/5174）、`application.yml`（数据源、JPA、端口 8070）。

## 技术选型
- Spring Boot 3.2.5 / Java 21 / Maven。
- Spring Web、Spring Data JPA、Validation、H2 内存库。
- 健康检查采用轻量自定义 Controller（不引入 Actuator，满足基线约定）。

## 关键设计
- 删除接口：`DELETE /api/books/{id}`，Service 先 `findById` 校验存在性，不存在抛 `BusinessException(404)`，存在则 `delete`，返回 204。
- 全局异常处理：`BusinessException` → 对应状态码；`MethodArgumentNotValidException` → 400；其他 → 500，统一 `ErrorResponse` 结构。
- 日志：Controller 入口与 Service 关键分支记录 ID 与结果，异常由全局处理器记录异常链。
- 排障基线：启动日志、异常堆栈、`GET /health` 三者构成可复现验证闭环。

## 部署
- 本地 `mvn spring-boot:run` 或 `java -jar` 启动，端口 8070。
- H2 内存库随应用启动初始化，无需外部依赖。
