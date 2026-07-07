# 架构说明

这份文档说明当前项目最重要的职责边界。AI 助手接手任务时先读 [ai-context.md](ai-context.md)，再按任务渐进读取相关文件。

## 主链路

当前唯一产品主链路:

```text
HTTP /api/v1
  -> app/api/v1/
  -> app/runtime/
  -> app/services/
  -> app/agent + app/tools/
  -> app/retrieval/
  -> app/db/models/
  -> PostgreSQL + pgvector
  -> Redis / Celery
```

旧 `/api + Chroma + CLI + Streamlit` 已删除。当前问答主线为 `/api/v1 + Runtime + Agent + pgvector`。

## 分层边界

- `app/api/`: FastAPI 应用装配、HTTP 协议、SSE 序列化、错误处理、限流。
- `app/api/v1/`: 产品化多租户接口。
- `app/runtime/`: chat run 生命周期、SSE StreamBridge、取消、运行态查询。runtime 不直接依赖 pgvector，不做检索业务，只编排运行状态和事件协议。
- `app/services/`: 业务编排，包含认证、知识库、文档、问答、缓存、日志。
- `app/agent/`: 当前问答 Agent 封装，只属于 `/api/v1 + Runtime + pgvector` 主链路。
- `app/tools/`: Agent tools。`retrieve_context` 必须从 runtime context 获取 `db_session / user_id / kb_id`，再调用 pgvector 检索。
- `app/retrieval/`: 文档加载、切分、embedding provider、pgvector 检索、hybrid、rerank、引用格式化。
- `app/db/`: SQLAlchemy Base、session、ORM models。
- `app/workers/`: Celery app 与异步文档处理任务。
- `evaluation/`: pgvector retrieval / answer eval、baseline 和 bad case 输出。
- `frontend/`: React 控制台，只通过 `/api/v1` 调用后端。

## 多租户原则

- 任何知识库、文档、chunk、聊天会话、消息查询都必须绑定当前用户。
- pgvector 检索必须在 SQL 条件中包含 `user_id + kb_id`。
- 不允许先全局召回再在 Python 层过滤权限。
- references 必须来自实际召回 chunks，并随 assistant message 保存。

## 问答路径

```text
POST /api/v1/kbs/{kb_id}/chat
  -> ChatService.ask()
  -> RagService.stream()
  -> Agent
  -> retrieve_context tool
  -> pgvector retrieve(user_id, kb_id)
  -> model answer with tool context
  -> save chat_messages + chat_runs
  -> return answer / references / session_id / run_id / usage
```

SSE 路径:

```text
POST /api/v1/kbs/{kb_id}/chat/stream
  -> RuntimeService
  -> RunManager
  -> ChatService.prepare_run()
  -> ChatService.run_prepared_stream()
  -> RagService.stream()
  -> Agent
  -> retrieve_context tool
  -> pgvector retrieve(user_id, kb_id)
  -> StreamBridge emits metadata / tool_call / tool_result / answer_delta / complete / end / error
```

API 层只负责鉴权、依赖注入和 SSE 序列化。

## 文档处理路径

```text
upload
  -> documents.status = pending
  -> Celery documents.process
  -> parse
  -> split
  -> embed
  -> document_chunks.embedding(pgvector)
  -> documents.status = completed / failed
```

同步处理接口复用同一套 service 逻辑，用于本地调试和 worker 失败后的兜底。

## 当前文件映射

- `app/main.py`: 统一启动入口，目前保留 `web`。
- `app/api/main.py`: FastAPI app、路由装配、React dist 托管。
- `app/api/v1/system.py`: `/api/v1/health`、`/api/v1/config`、`/api/v1/metrics`。
- `app/api/v1/auth.py`: 注册、登录、当前用户。
- `app/api/v1/knowledge_bases.py`: 知识库 CRUD。
- `app/api/v1/documents.py`: 上传、列表、详情、删除、处理。
- `app/api/v1/chat.py`: 同步问答、SSE、聊天记录。
- `app/runtime/manager.py`: in-process run 注册、查询和取消状态。
- `app/runtime/service.py`: RuntimeService，连接 API、ChatService 和 StreamBridge。
- `app/runtime/stream.py`: StreamBridge，统一 SSE 事件输出。
- `app/runtime/schemas.py`: runtime 事件和状态数据结构。
- `app/services/chat_service.py`: 问答主编排。
- `app/services/rag_service.py`: Agent 流式事件适配、引用去重、usage 聚合。
- `app/services/chat_client.py`: LangChain Agent client。
- `app/tools/retrieve_context.py`: Agent 检索工具，连接 runtime context 与 pgvector。
- `app/services/document_service.py`: 文档处理主编排。
- `app/retrieval/pgvector_store.py`: pgvector 检索、hybrid、rerank。
- `app/retrieval/embeddings.py`: embedding 初始化。
- `app/retrieval/loaders.py`: 文档加载。
- `app/retrieval/splitter.py`: 文本切分。
- `migrations/`: Alembic migration。

## 当前结论

后续新增能力应保持:

- 新业务流程进 `app/services/`。
- 新检索能力进 `app/retrieval/`。
- 新 HTTP 能力进 `app/api/v1/`。
- 数据变更同步 model、migration、schema、测试和文档。
