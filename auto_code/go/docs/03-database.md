# 数据库（内存存储模型）

本项目沿用内存存储，无外部数据库。以下为逻辑数据模型与约束，Repository 层据此实现。

## 表：books（内存 map）

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | int64 | 主键，唯一，> 0，后端自增生成 | 图书 ID |
| title | string | 非空，去除首尾空格后长度 > 0 | 书名 |
| author | string | 可为空字符串 | 作者 |
| stock | int | >= 0 | 库存数量 |

## 关系
- 单表，无外键关联。

## 存储实现约定
- 使用 `map[int64]*model.Book` 存储，`sync.RWMutex` 保护并发读写。
- 自增 id 由 Repository 内部计数器维护，新增时生成。
- 更新操作按 id 查找，存在则覆盖 title、author、stock，返回更新后副本；不存在返回 `ErrNotFound`。
- 进程重启后数据清空（内存存储的已知限制）。
