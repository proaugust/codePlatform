# 数据存储设计（内存存储）

> 本项目沿用内存存储，无关系型数据库。以下为逻辑数据模型，字段与 Go 结构体及 JSON 对应。

## 实体：Book

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | int64 | 主键，唯一，>0，后端自增生成 | 图书 ID |
| title | string | 非空，去空格后长度>0 | 书名 |
| author | string | 可为空字符串 | 作者 |
| stock | int | >=0 | 库存 |
| createdAt | string(RFC3339) | 创建时写入 | 创建时间 |
| updatedAt | string(RFC3339) | 每次更新刷新 | 更新时间 |

## 存储结构
- `map[int64]*Book` 加 `sync.RWMutex` 保护并发读写。
- 自增 id 计数器 `nextID int64`，新增时 `nextID++`。

## 关系
单实体，无外键关联。

## 更新语义
- 按 id 查找，不存在返回 `NOT_FOUND`。
- 覆盖 title、author、stock，刷新 updatedAt，保留 id 与 createdAt。
