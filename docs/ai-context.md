# AI 助手上下文入口

这份文档给代码助手使用。目标是用最少上下文理解项目，不要一开始读取所有文档。

## 先读这几份

每次接手任务时，优先按顺序读取:

1. [../AGENTS.md](../AGENTS.md): 仓库工作规则、代码落点和提交前检查。
2. [architecture.md](architecture.md): 当前分层、边界和关键文件映射。
3. [target-architecture.md](target-architecture.md): 主架构决策和已删除旧链路说明。
4. [todo.md](todo.md): 当前待办、已完成批次和近期方向。

只有任务需要时，再按下面路由继续读取。

## 当前主线

唯一产品主线:

```text
/api/v1 + Runtime + Agent + PostgreSQL + pgvector + JWT + Redis/Celery
```

旧 `/api + Chroma + CLI + Streamlit` 已删除。当前问答运行时路径是 `/api/v1/chat -> app/runtime -> app/services/chat_service.py -> app/services/rag_service.py -> app/agent -> app/tools/retrieve_context.py -> app/retrieval/pgvector_store.py`。

注意: `app/agent/` 和 `app/tools/` 已恢复为当前主线的一部分，但 tool 必须走 pgvector 和多租户过滤；不要恢复旧 Chroma vectorstore。

## 按任务渐进读取

### 运行、配置、Docker、迁移

读取:

- [development.md](development.md)
- [.env.example](../.env.example)
- [docker-compose.yml](../docker-compose.yml)
- `migrations/versions/`

常用命令:

```powershell
uv sync
docker compose up -d postgres redis
uv run alembic upgrade head
uv run python -m app.main web
```

### 多租户 API、认证、权限隔离

读取:

- [multitenant-rag.md](multitenant-rag.md)
- `app/api/v1/`
- `app/services/auth_service.py`
- `app/services/kb_service.py`
- `app/services/document_service.py`
- `app/services/chat_service.py`
- `app/db/models/`

关键原则:

- 所有知识库、文档、chunk、聊天会话都必须按当前用户过滤。
- 向量检索权限过滤必须进入 SQL 条件，不能先全局召回再应用层过滤。

### 文档上传、异步处理、pgvector

读取:

- [ingestion.md](ingestion.md)
- `app/api/v1/documents.py`
- `app/services/document_service.py`
- `app/workers/tasks.py`
- `app/retrieval/parser.py`
- `app/retrieval/splitter.py`
- `app/retrieval/pgvector_store.py`

路径:

```text
upload -> documents(pending) -> Celery task -> parse -> split -> embedding -> document_chunks -> completed/failed
```

### 问答、引用、聊天记录、SSE、缓存

读取:

- [development.md](development.md) 的多租户问答 API 章节
- [../RAG_RUNTIME_SPEC.md](../RAG_RUNTIME_SPEC.md): 只有改运行态、取消、后台 run、SSE 桥时需要读取。
- `app/api/v1/chat.py`
- `app/runtime/`
- `app/services/chat_service.py`
- `app/services/rag_service.py`
- `app/services/chat_client.py`
- `app/services/hot_question_cache.py`
- `app/retrieval/pgvector_store.py`
- `app/db/models/chat.py`

当前行为:

- 同步接口返回 `answer / references / session_id / run_id / usage`。
- SSE 返回 `tool_call`、`tool_result`、`answer_delta`、`complete`、`error`。
- assistant 消息保存结构化 `references`。
- 热点问题缓存按 `user_id + kb_id + question + top_k + 模型配置` 隔离。

### MCP Tool 示例、外部 Agent 集成

读取:

- [development.md](development.md) 的 MCP Server 示例章节
- `app/mcp/server.py`
- `app/retrieval/pgvector_store.py`
- `app/db/models/chat.py`
- `app/db/models/document.py`

当前 MCP server 是独立进程，不挂到 FastAPI 主进程。工具必须显式接收 `user_id` / `kb_id` 或 `user_id` / `run_id`，并复用当前 pgvector 检索和 SQL 租户过滤，不允许绕回旧 Chroma。

### 检索质量、评测、rerank、hybrid

读取:

- [hybrid-search-evaluation.md](hybrid-search-evaluation.md)
- [evaluation.md](evaluation.md)
- `evaluation/`
- `app/retrieval/pgvector_store.py`
- `app/retrieval/reranker.py`
- `evaluation/evaluate_pgvector_retrieval.py`
- `evaluation/run_pgvector_baseline.py`

验证建议:

```powershell
uv run python -m evaluation.check_pgvector_embedding_config
uv run python -m evaluation.evaluate_pgvector_retrieval --user-id 1 --kb-id 1 --limit 10
uv run python -m evaluation.run_pgvector_baseline --user-id 1 --kb-id 1 --retrieval-dataset data/eval/current_kb_retrieval.jsonl --answer-dataset data/eval/current_kb_answer.jsonl --retrieval-limit 10 --skip-answer
```

### 前端、React、静态托管

读取:

- `frontend/`
- `app/api/main.py`
- [development.md](development.md) 的 React 前端章节

当前关系:

- 前端调用 `/api/v1`。
- 前端已内置登录、知识库选择、文档上传和聊天，不再需要手动配置 `VITE_API_TOKEN` / `VITE_KB_ID`。
- `frontend/dist/` 存在时由 FastAPI 托管。

## 代码结构速览

```text
app/
  api/          FastAPI app、/api/v1、错误处理、限流
  config/       settings 与日志配置
  core/         安全/JWT/密码工具
  db/           SQLAlchemy Base、session、ORM models
  memory/       LangGraph checkpointer
  mcp/          独立 MCP server 示例，复用当前 pgvector 与 chat run 数据
  retrieval/    加载、切分、pgvector、hybrid、rerank、引用
  runtime/      chat run 生命周期、SSE StreamBridge、取消、运行态查询
  schemas/      Pydantic schemas
  services/     认证、知识库、文档、问答、缓存、日志
  workers/      Celery app 和文档任务
evaluation/     pgvector retrieval / answer eval 与 baseline
frontend/       React + Vite 前端
migrations/     Alembic migrations; 开发阶段压成当前初始 schema，不维护旧库兼容迁移
scripts/        smoke 脚本
tests/          单元测试与 API 测试
docs/           架构、运行、规划、待办
```

## 修改落点规则

- 新业务流程优先放 `app/services/`。
- 新检索能力优先放 `app/retrieval/`。
- 新 HTTP 接口优先放 `app/api/v1/`。
- 新数据库结构同步 ORM model、Alembic migration 和模型测试。
- 新配置同步 `app/config/settings.py`、`.env.example`、`docker-compose.yml` 和 [development.md](development.md)。
- 新文档同步 README 文档导航，必要时同步本文件。

## 推荐最小检查

- API/service: `uv run python -m unittest discover -s tests`
- 前端: `cd frontend && npm run build`
- 数据库/migration: `uv run alembic upgrade head`
- Docker/Compose: `docker compose config`
- 多租户 smoke: `uv run python scripts/smoke_multitenant.py --skip-chat`
- 检索/回答质量: 运行相关 `evaluation.*pgvector*` 命令
