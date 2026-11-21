# 数据存储设计（进程内内存）

无外部数据库，采用内存数据结构模拟表。

## 表：books

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | int64 | 主键，自增，唯一 | 图书 ID |
| title | string | 非空 | 书名 |
| author | string | 非空 | 作者 |
| isbn | string | 非空，唯一 | ISBN |
| stock | int | >= 0 | 库存 |
| created_at | time.Time | 非空 | 创建时间 |
| updated_at | time.Time | 非空 | 更新时间 |

## 存储结构
- `map[int64]*Book`：主键索引。
- `map[string]int64`：ISBN 唯一索引（isbn -> id）。
- `nextID int64`：自增计数器，初始 1。
- 并发控制：`sync.RWMutex`，写操作加写锁，读操作加读锁。

## 关系
单表，无外键关系。

## 索引
- 主键索引：id。
- 唯一索引：isbn。
- 关键字查询为内存遍历过滤（title/author/isbn 包含匹配，忽略大小写）。
