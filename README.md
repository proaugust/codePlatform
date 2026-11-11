# Code Platform

**Python FastAPI 项目**：前端只调本仓库 Py Agent 接口；由 Agent 分析需求并生成 **Java / Go 工程产物**到 `auto_code/`。

```
React/Vue → /api/agent/* → Python Agent → auto_code/java | auto_code/go
```

| 前端 | 端口 | 调 Py | 产物 target |
|------|------|-------|-------------|
| React | 5174 | `/agent/*` | `java` → `auto_code/java` |
| Vue | 5173 | `/agent/*` | `go` → `auto_code/go` |

## 环境

```bash
uv sync
copy .env.example .env
# 填写 LLM_API_KEY（DeepSeek）
```

## 启动后端（F5 或 bat）

```bash
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
# 或 run.bat ；Cursor F5：FastAPI: backend
```

文档：http://127.0.0.1:8001/docs

### Agent 接口（前端只调这些）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/agent/analyze` | body: `{ "spec", "target": "java\|go" }` → 5+1 前半：RepoIntel→Requirements→Planner，写 docs + IR |
| GET | `/agent/{target}/docs` | 读取已生成文档 |
| GET | `/agent/{target}/run` | 编排状态 / plan 摘要 |
| POST | `/agent/plan/confirm` | body: `{ "target" }` → 批准 change_plan（`AUTO_APPROVE_PLAN=true` 时可跳过） |
| POST | `/agent/generate` | body: `{ "target", "use_docs": true }` → Coder⇄Validator→Review |
| GET | `/agent/{target}/status` | 产物目录状态 |

内部 Agent：Orchestrator + Requirements / RepoIntel / Planner / Coder / Validator。IR 落在 `auto_code/{target}/docs/ir/`。

## 需求四件套（写在 `auto_code/{target}/docs/`）

- `01-requirements.md` 总需求  
- `02-architecture.md` 架构  
- `03-database.md` 数据库表  
- `04-api.md` 接口  

## 前端

```bash
frontend-react\run_react.bat   # Java 产物
frontend-vue\run_vue.bat       # Go 产物
```

Vite 把 `/api` 代理到 Py `:8001`（去掉 `/api` 前缀）。

## 目录

```
backend/             Python FastAPI + Agent
frontend-react/      调 Agent，target=java
frontend-vue/        调 Agent，target=go
auto_code/java/      生成的 Spring Boot（产物）
auto_code/go/        生成的 Go 后端（产物）
```
