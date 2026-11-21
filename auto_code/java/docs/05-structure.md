# 工程结构（java）

- 扫描根目录：`D:\code\py\demo\codePlatform\auto_code\java`
- 是否存在代码：是

## 构建（pom.xml）

- 路径：`pom.xml`
- parent：`spring-boot-starter-parent:3.2.5`
- 关键依赖：
  - `com.h2database:h2`
  - `org.springframework.boot:spring-boot-starter-data-jpa`
  - `org.springframework.boot:spring-boot-starter-test`
  - `org.springframework.boot:spring-boot-starter-validation`
  - `org.springframework.boot:spring-boot-starter-web`

## JPA

- 依赖启用：是
- Entity：
  - `src/main/java/com/example/autocode/entity/Book.java`
- Repository：
  - `src/main/java/com/example/autocode/repository/BookRepository.java`
- 配置线索：
  - `src/main/resources/application.yml: datasource:`
  - `src/main/resources/application.yml: jpa:`
  - `src/main/resources/application.yml: hibernate:`
  - `src/main/resources/application.yml: hibernate:`

## 三层路径

### Controller

- `src/main/java/com/example/autocode/controller/BookController.java`
- `src/main/java/com/example/autocode/controller/HealthController.java`
- `src/main/java/com/example/autocode/exception/GlobalExceptionHandler.java`

### Service

- `src/main/java/com/example/autocode/service/BookService.java`

### Repository

- `src/main/java/com/example/autocode/repository/BookRepository.java`

### 源码路径摘要

- `src/main/java/com/example/autocode/AutoCodeApplication.java`
- `src/main/java/com/example/autocode/config/CorsConfig.java`
- `src/main/java/com/example/autocode/controller/BookController.java`
- `src/main/java/com/example/autocode/controller/HealthController.java`
- `src/main/java/com/example/autocode/dto/BookResponse.java`
- `src/main/java/com/example/autocode/dto/CreateBookRequest.java`
- `src/main/java/com/example/autocode/dto/UpdateStockRequest.java`
- `src/main/java/com/example/autocode/entity/Book.java`
- `src/main/java/com/example/autocode/exception/BusinessException.java`
- `src/main/java/com/example/autocode/exception/ErrorResponse.java`
- `src/main/java/com/example/autocode/exception/GlobalExceptionHandler.java`
- `src/main/java/com/example/autocode/repository/BookRepository.java`
- `src/main/java/com/example/autocode/service/BookService.java`
- `src/main/resources/application.yml`
- `src/test/java/com/example/autocode/BookApiTest.java`

## API 面

- `GET /api/books` — `com.example.autocode.controller.BookController (@GetMapping)`
- `GET /api/books/{id}` — `com.example.autocode.controller.BookController (@GetMapping)`
- `POST /api/books` — `com.example.autocode.controller.BookController (@PostMapping)`
- `PATCH /api/books/{id}/stock` — `com.example.autocode.controller.BookController (@PatchMapping)`
- `GET /` — `com.example.autocode.controller.HealthController (@GetMapping)`
