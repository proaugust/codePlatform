# 数据库

采用 H2 内存库，JPA 自动建表（`ddl-auto: update`）。

## 表：book

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK, AUTO_INCREMENT | 主键 |
| title | VARCHAR(255) | NOT NULL | 书名 |
| author | VARCHAR(255) | NOT NULL | 作者 |
| isbn | VARCHAR(32) | UNIQUE, NOT NULL | ISBN |
| stock | INT | NOT NULL, DEFAULT 0, CHECK >= 0 | 库存 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

## 关系
- 单表，无外键关联。

## 说明
- 删除为物理删除，直接 `DELETE FROM book WHERE id = ?`。
- `isbn` 唯一约束用于防止重复录入。
- 字段类型与现有 `Book` 实体保持一致，删除接口不新增表结构。
