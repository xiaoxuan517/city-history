# 多租户企业知识库 RAG 规划

本文记录项目从单用户本地 RAG 演进为多租户企业知识库 RAG 系统的目标、架构边界、数据模型、API 设计和分批实施计划。

## 目标定位

目标系统不是简单聊天 demo，而是一个具备多租户权限隔离、文档异步处理、向量检索、引用追踪和聊天记录保存能力的企业知识库 RAG 后端。

核心特点:

1. 多用户注册、登录和 JWT 鉴权
2. 每个用户拥有自己的知识库
3. 文档上传后可异步解析
4. 文档切片并写入向量库
5. 问答时只检索当前用户有权限的文档
6. 回答必须返回结构化引用来源
7. 保存聊天会话和聊天消息
8. 支持文档处理状态追踪

## 技术栈

第一阶段采用简单但够用的后端技术栈:

- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- pgvector
- Redis
- Celery
- Pydantic v2
- JWT
- Docker Compose
- Pytest

向量库第一阶段直接使用 PostgreSQL + pgvector，避免同时维护独立向量库和业务数据库。

## 架构分层

建议按下面的边界演进:

```text
app/
  api/
    v1/
      auth.py
      knowledge_bases.py
      documents.py
      chat.py
  core/
    security.py
    exceptions.py
  db/
    base.py
    session.py
    models/
  schemas/
  services/
    auth_service.py
    kb_service.py
    document_service.py
    ingestion_service.py
    chat_service.py
  retrieval/
    splitter.py
    embeddings.py
    pgvector_store.py
    retriever.py
  workers/
    celery_app.py
    tasks.py
```

职责边界:

- `api/` 只处理 HTTP、鉴权依赖、参数校验和响应序列化。
- `services/` 负责编排业务流程和权限判断。
- `db/` 负责 SQLAlchemy 模型、session 和 migration metadata。
- `retrieval/` 负责切片、embedding、向量检索和引用构造。
- `workers/` 负责文档解析、切片、向量化等异步任务。

## 核心数据模型

第一阶段核心表:

- `users`
- `knowledge_bases`
- `documents`
- `document_chunks`
- `chat_sessions`
- `chat_messages`

### users

```text
id
username
email
password_hash
created_at
updated_at
```

### knowledge_bases

```text
id
user_id
name
description
created_at
updated_at
```

第一阶段先做个人知识库，所有知识库归属于单个用户。组织、团队、ACL 后续再扩展。

### documents

```text
id
kb_id
user_id
filename
content_type
file_path
status
error_message
created_at
updated_at
```

文档状态:

```text
pending
processing
completed
failed
```

### document_chunks

```text
id
document_id
kb_id
user_id
chunk_index
content
embedding
metadata
created_at
updated_at
```

`embedding` 使用 pgvector 类型。`user_id`、`kb_id`、`document_id` 必须保留在 chunk 表中，方便检索时做租户和知识库权限过滤。

### chat_sessions

```text
id
user_id
kb_id
title
created_at
updated_at
```

### chat_messages

```text
id
session_id
role
content
references
created_at
updated_at
```

`references` 使用 JSON 保存结构化引用:

```json
[
  {
    "document_id": 1,
    "filename": "产品手册.pdf",
    "chunk_id": 12,
    "chunk_index": 3,
    "content": "引用片段..."
  }
]
```

## API 设计

### 认证

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

### 知识库

```text
POST   /api/v1/kbs
GET    /api/v1/kbs
GET    /api/v1/kbs/{kb_id}
PUT    /api/v1/kbs/{kb_id}
DELETE /api/v1/kbs/{kb_id}
```

### 文档

```text
POST   /api/v1/kbs/{kb_id}/documents
GET    /api/v1/kbs/{kb_id}/documents
GET    /api/v1/documents/{document_id}
DELETE /api/v1/documents/{document_id}
```

### 问答

```text
POST /api/v1/kbs/{kb_id}/chat
GET  /api/v1/chat-sessions
GET  /api/v1/chat-sessions/{session_id}/messages
```

问答请求:

```json
{
  "question": "这个系统怎么计费？",
  "session_id": 1
}
```

问答响应:

```json
{
  "answer": "系统根据调用次数和存储容量计费……",
  "references": [
    {
      "document_id": 1,
      "filename": "产品说明.pdf",
      "chunk_id": 12,
      "chunk_index": 3,
      "content": "计费规则包括调用次数、存储容量……"
    }
  ],
  "session_id": 1
}
```

## 权限原则

多租户 RAG 的第一原则是检索不能越权。

所有知识库、文档、chunk、聊天会话查询都必须约束当前用户:

```text
user_id = current_user.id
```

向量检索也必须在 SQL 层过滤:

```sql
WHERE user_id = :current_user_id
AND kb_id = :kb_id
ORDER BY embedding <=> :query_embedding
LIMIT :top_k
```

不要先全局向量召回再在应用层过滤，否则存在跨租户泄露风险。

## 分阶段计划

### 第一阶段: 必须做

- 用户注册 / 登录
- JWT 鉴权
- 知识库 CRUD
- 文档上传
- 文档解析
- 文本切分
- Embedding 入库
- 问答接口
- 引用来源返回
- 聊天记录保存

### 第二阶段: 增强后端感

- Celery 异步处理文档
- 文档处理状态: `pending / processing / completed / failed`
- Redis 缓存热点问题
- 接口限流
- 统一异常处理
- 操作日志
- Pytest 测试
- Docker Compose 一键启动

### 第三阶段: 面试加分

- 混合检索: 关键词 + 向量
- 重排序 rerank
- 上下文压缩
- 召回率评估
- 更细粒度权限过滤
- 流式回答 SSE
- Token 用量统计

## 当前实施批次

### Batch 1: 数据库与工程地基

- 引入 SQLAlchemy / Alembic / PostgreSQL / pgvector / Redis / Celery 依赖
- 增加数据库配置
- 增加 SQLAlchemy Base、session provider 和核心模型
- 增加 Docker Compose 的 PostgreSQL + Redis
- 增加模型层测试

### Batch 2: 用户认证

- 密码哈希
- 用户注册
- 用户登录
- JWT access token
- `get_current_user` 鉴权依赖
- `/api/v1/auth/me`

### Batch 3: 知识库 CRUD

- 知识库创建、列表、详情、更新、删除
- 所有接口限制当前用户权限
- 知识库 service 和 schema

### Batch 4: 文档上传与状态

- 上传文件保存到 `UPLOAD_DIR`
- 创建 document 记录
- 文档状态流转
- 同步解析入口，后续切到 Celery

### Batch 5: pgvector 入库与检索

- 文档切片
- Embedding 写入 `document_chunks`
- 基于 `user_id + kb_id` 的 pgvector 检索
- 返回结构化引用

### Batch 6: 多租户问答和聊天记录

- 问答接口
- session 创建和复用
- 保存 user / assistant 消息
- assistant 消息保存 references JSON

## 关键风险

- 权限过滤不能只做应用层过滤，必须进入 SQL 查询条件。
- 文档异步任务要幂等，重试不能重复写入 chunks。
- 引用来源应由后端根据检索结果结构化返回，不能完全依赖模型自由生成。
- 第一阶段不要过早做组织、多角色 ACL、复杂 memory 或多向量库。
