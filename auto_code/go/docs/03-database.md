# 数据存储设计（PostgreSQL）

> 持久化使用 PostgreSQL。默认连接：`postgresql://postgres:postgres@localhost:5435/ai_test`（可用环境变量 `DATABASE_URL` 覆盖）。启动时 `CREATE TABLE IF NOT EXISTS`。

## 表：books

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGSERIAL | 主键 | 图书 ID，自增 |
| title | TEXT | NOT NULL | 书名 |
| author | TEXT | NOT NULL DEFAULT '' | 作者 |
| stock | INT | NOT NULL DEFAULT 0，CHECK ≥ 0 | 库存绝对值 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 更新时间（UPDATE 时刷新） |

## API 映射（JSON Book）
- `id` / `title` / `author` / `stock`（当前接口不暴露 created_at / updated_at / price）。

## 更新语义
- PUT：按 id 覆盖 title、author、stock，刷新 `updated_at`。
- PATCH stock：只接受 `{ "stock": N }` 绝对值覆盖，不接受 `delta`。
