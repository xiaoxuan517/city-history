# 目标架构与收口计划

核心结论: 项目没有致命总体设计缺陷，真正的架构风险是两条 RAG 链路长期并存。现在该风险已经通过删除旧链路收口，产品主线唯一化为 `/api/v1 + Runtime + Agent + pgvector`。

## 当前主线

```text
/api/v1/*
  -> app/api/v1/
  -> app/runtime/
  -> app/services/
  -> app/agent + app/tools/retrieve_context.py
  -> app/retrieval/
  -> SQLAlchemy models
  -> PostgreSQL + pgvector
  -> Redis / Celery / operation logs / rate limit / cache
```

新增能力默认进入:

- HTTP: `app/api/v1/`
- 运行态、SSE、取消: `app/runtime/`
- 业务编排: `app/services/`
- 检索能力: `app/retrieval/`
- 数据结构: `app/db/models/` + Alembic migration
- 后台任务: `app/workers/`

## 已删除的旧链路

以下旧路径不再存在:

- 旧 `/api/chat`、`/api/chat/stream`、`/api/threads`、`/api/feedback`
- Chroma vectorstore 与本地 ingest CLI
- Agent / Tool 问答链路
- CLI 聊天入口
- Streamlit 演示入口
- 旧 Chroma/Agent evaluation 脚本

系统接口已迁移到:

- `GET /api/v1/health`
- `GET /api/v1/config`
- `GET /api/v1/metrics`

问答接口是:

- `POST /api/v1/kbs/{kb_id}/chat`
- `POST /api/v1/kbs/{kb_id}/chat/stream`

## 参考 DeerFlow 的取舍

适合借鉴:

- run / session 生命周期
- SSE 事件围绕 run 聚合
- 渐进上下文和文档导航
- 分层边界清晰，避免工具、业务状态、协议层混在一起

暂不引入:

- subagent 编排
- sandbox 文件系统
- skill marketplace
- 通用 Agent 平台式复杂 memory

## 成功标准

- 新功能只面向 `/api/v1` 产品主链路。
- Runtime 只负责 run 生命周期、取消和事件协议，不直接依赖 pgvector 或承载检索业务。
- Agent / Tool 只能作为当前产品主链路的一部分存在，不能恢复旧 Chroma 或旧 `/api`。
- 检索必须在 SQL 层保留 `user_id + kb_id` 权限过滤。
- 问答输出始终保存聊天记录并返回 references。
- usage、cache、operation log、SSE 都围绕 chat run 聚合。
- AI 助手通过 [ai-context.md](ai-context.md) 渐进读取，不需要一次性加载所有文档。

## 下一步

当前架构收口已完成。后续优先级:

1. 真实数据 pgvector retrieval baseline。
2. pgvector answer sampling + answer eval。
3. bad case 回流，决定 hybrid / rerank 默认策略。
4. 前端补齐新会话、历史会话列表、消息加载和 usage 展示。
