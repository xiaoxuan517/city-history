# 方志云藏

方志云藏是面向中国古籍县志的汇聚、检索、下载与 RAG 问答知识库系统。项目将 AList 中的全国地方县志目录同步到数据库，提供县志文件检索、离线下载、本地文件管理，并支持把单本县志创建为独立知识库，进行基于来源片段的问答。

当前技术主线是 FastAPI + SQLAlchemy 2.0 + PostgreSQL + pgvector + Redis + Celery + React。后端通过 `/api/v1 + Runtime + Agent + pgvector` 管理知识库问答，Agent 使用 `retrieve_context` tool 检索当前知识库内容，并在 SQL 层保留用户与知识库范围过滤。

## 当前能力

- 县志目录同步：递归同步 AList 指定目录下的县志文件，落库后支持逻辑分页。
- 县志检索浏览：按文件名、完整路径、古地名、省市县关键词模糊检索。
- 文件下载管理：创建 AList 离线下载任务，保存到项目 `downloads/` 目录，并识别同名本地文件避免重复下载。
- 本地浏览器下载：已下载文件可直接从浏览器下载到用户本机。
- 单书知识库：每本县志可创建独立知识库，已存在同名知识库时直接打开。
- RAG 问答：文档解析、切片、embedding、pgvector 入库，问答时返回来源片段和检索 trace。
- 用户体系：注册、登录、JWT 鉴权，登录过期自动跳转登录页。
- 会话管理：聊天会话、消息、chat run、usage、操作日志、取消运行。
- 质量评测：pgvector retrieval / answer eval、baseline manifest、bad case 导出。


## 功能预览

![img.png](img.png)


![img_1.png](img_1.png)

## 快速开始

完整项目一键启动（PostgreSQL / Redis / FastAPI / Celery worker / React 前端静态资源）:

```powershell
docker compose up -d --build
```

打开: `http://127.0.0.1:8000`

如果容器内 API / worker 需要访问宿主机 Ollama 或兼容 OpenAI 服务，不要在 `.env` 中使用 `http://127.0.0.1:11434/v1`，应使用:

```env
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

本机进程开发:

```powershell
uv sync
docker compose up -d postgres redis
uv run alembic upgrade head
uv run python -m app.main web
```

API 默认地址: `http://127.0.0.1:8000`

## 必要环境变量

```env
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=
CHAT_MODEL=gpt-4.1-mini

EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSION=1024

DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5432/rag
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=change-me-in-production
UPLOAD_DIR=./storage/uploads

ALIST_BASE_URL=http://127.0.0.1:5244
ALIST_USERNAME=
ALIST_PASSWORD=
GAZETTEER_FILE_ROOT_PATH=/百度网盘/全国地方县志古籍收藏
```

`EMBEDDING_API_KEY` 和 `EMBEDDING_BASE_URL` 可单独配置；留空时分别回退到 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。

当前主线默认使用 `bge-m3`，embedding 表结构按 `vector(1024)` 设计。如果切换到其他 embedding 模型，必须同步修改:

```env
EMBEDDING_DIMENSION=1024
```

已经建过旧维度表时，本项目不保留旧 embedding 数据兼容；请重建数据库或清空并重建 `document_chunks` 后重新处理文档，避免混用不同维度的向量。

容器访问宿主机 Ollama 时使用:

```env
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

## 常用命令

```powershell
# 启动 FastAPI
uv run python -m app.main web

# 数据库迁移
uv run alembic upgrade head

# 单元测试
uv run python -m unittest discover -s tests

# 多租户 smoke
uv run python scripts/smoke_multitenant.py --skip-chat

# pgvector 配置诊断
uv run python -m evaluation.check_pgvector_embedding_config

# pgvector baseline
uv run python -m evaluation.run_pgvector_baseline --user-id 1 --kb-id 1 --retrieval-dataset data/eval/current_kb_retrieval.jsonl --retrieval-limit 10 --skip-answer
```

## 前端

```powershell
cd frontend
npm install
npm run build
```

FastAPI 会托管 `frontend/dist/`。本地开发:

```powershell
cd frontend
npm run dev
```

前端当前通过 `/api/v1` 调用后端，已支持首页、县志目录、知识库列表、文档向量化、RAG 问答、登录过期处理和本地下载。

## 项目结构

```text
app/
  api/          FastAPI app、/api/v1 路由、AList 文件接口、错误处理、限流
  config/       settings 与日志配置
  core/         JWT、密码、安全工具
  db/           SQLAlchemy session 与 ORM models
  memory/       LangGraph checkpointer
  mcp/          独立 MCP server 示例，不挂入 FastAPI 主进程
  retrieval/    parser、splitter、pgvector、hybrid、rerank、引用
  runtime/      chat run 生命周期、SSE StreamBridge、取消、运行态查询
  schemas/      Pydantic schemas
  services/     认证、AList、县志同步、知识库、文档、问答、缓存、日志
  workers/      Celery app 和文档任务
evaluation/     pgvector retrieval / answer eval 与 baseline
frontend/       React + Vite 前端
migrations/     Alembic migrations; 开发阶段以当前初始 schema 为准
scripts/        smoke 脚本
tests/          单元测试与 API 测试
docs/           架构、运行、规划、待办
```
