# 项目现状

## 阶段判断

项目已经从本地 RAG demo 收口为多租户企业知识库 RAG 后端。当前唯一产品主线是:

```text
/api/v1 + Runtime + Agent + PostgreSQL + pgvector + JWT + Redis/Celery
```

旧 `/api + Chroma + CLI + Streamlit` 链路已经删除。Runtime 已成为当前问答运行态主线，负责 chat run 生命周期、SSE StreamBridge、取消和运行态查询。Agent 已恢复到当前 `/api/v1 + Runtime + pgvector` 主线，`retrieve_context` tool 直接使用 PostgreSQL/pgvector，并带 `user_id + kb_id` 权限过滤。

## 已落地能力

- SQLAlchemy / Alembic / PostgreSQL / pgvector 数据层
- JWT 认证、知识库 CRUD、文档上传与状态追踪
- Celery 异步文档处理，同步处理入口兜底
- 文档解析、切片、embedding、pgvector 入库
- 按 `user_id + kb_id` 权限过滤的 pgvector 检索
- 多租户问答、结构化 references、聊天记录
- chat run 生命周期、取消、usage、热点缓存、限流、操作日志
- 外部 tracing 配置入口、本地 token cost 估算、trace id/url 预留字段、本地轻量 run timeline
- SSE `metadata / tool_call / tool_result / answer_delta / complete / end / error`
- pgvector retrieval / answer eval、baseline runner、embedding 维度诊断

## 当前核心模块

- `app/api/v1/`: 产品化 HTTP API
- `app/runtime/`: run 生命周期、SSE StreamBridge、取消、运行态查询
- `app/services/auth_service.py`: 注册、登录、当前用户
- `app/services/kb_service.py`: 知识库业务
- `app/services/document_service.py`: 上传、状态、解析处理
- `app/services/chat_service.py`: 问答、引用、聊天记录、run 生命周期
- `app/retrieval/pgvector_store.py`: pgvector 检索、hybrid、rerank 接入
- `app/retrieval/embeddings.py`: embedding provider
- `app/workers/tasks.py`: Celery 文档任务
- `evaluation/`: pgvector 评测和 baseline
- `frontend/`: React 控制台，调用 `/api/v1`

## 当前重点

下一步最值得投入的是质量基线，而不是继续堆大功能:

1. 在真实 PostgreSQL + pgvector 数据上跑 retrieval baseline。
2. 采样 pgvector answer run 并跑 answer eval。
3. 根据 bad cases 决定 hybrid / rerank 默认策略。
4. 补齐 run 查询、取消和更完整的前端多租户登录/知识库管理体验。
5. 之后再考虑组织、团队、RBAC、ACL。
