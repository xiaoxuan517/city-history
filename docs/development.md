# 开发与运行约定

如果你是 AI 助手，不确定该读哪些文档时，先看 [ai-context.md](ai-context.md)。本文只负责运行、配置、API 使用和本地验证细节。

## Python 环境

本项目统一使用 `uv` 执行命令，不直接写死 `.venv\Scripts\python.exe`，也不建议直接使用系统 `python`。

推荐方式:

```powershell
uv run python -m evaluation.evaluate_pgvector_retrieval --user-id 1 --kb-id 1 --limit 2
```

原因:

- `uv` 会自动使用项目环境与锁文件
- 不需要手动关心 `.venv` 路径
- 能减少“系统 python 缺依赖”这类问题
- 当前仓库已经验证 `uv run` 可以直接执行评测命令

## 环境准备

首次拉起项目时，先同步依赖:

```powershell
uv sync
```

后续运行脚本时，统一使用:

```powershell
uv run python -m <module>
```

## 环境变量策略

- `OPENAI_API_KEY` 是必填项，即使接本地兼容服务也需要显式提供一个非空值。
- `OPENAI_BASE_URL` 是可选项；走官方 OpenAI 可留空，走兼容网关或本地模型服务时填写。
- `EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL` 可单独配置 embedding 服务；留空时分别回退到 `OPENAI_API_KEY`、`OPENAI_BASE_URL`。
- `CHAT_MODEL`、`EMBEDDING_MODEL`、`LOG_DIR`、`LOG_FILE_NAME` 都有默认值，但不允许为空字符串。
- `EMBEDDING_MODEL` 默认 `bge-m3`，`EMBEDDING_DIMENSION` 默认 `1024`，必须和当前 embedding 模型输出维度一致；例如 `text-embedding-3-small` 是 `1536`。
- `TOP_K`、`RETRIEVAL_FETCH_K`、`CHUNK_SIZE` 必须大于 `0`。
- `RETRIEVAL_MAX_CONTEXT_CHARS` 必须大于 `0`，用于限制传给模型的检索上下文字符数。
- `CHUNK_OVERLAP` 必须大于等于 `0`，且必须小于 `CHUNK_SIZE`。
- `RETRIEVAL_SEARCH_TYPE` 当前支持 `similarity`、`mmr` 和 `hybrid`。
- `RETRIEVAL_FETCH_K` 必须大于等于 `TOP_K`。
- `RERANKER_ENABLED` 是可选布尔开关，默认 `false`。
- `RERANKER_STRATEGY` 当前只支持 `embedding_lexical`。
- `LOG_LEVEL` 当前只支持 `CRITICAL`、`ERROR`、`WARNING`、`INFO`、`DEBUG`。
- `CHECKPOINTER_TYPE` 当前支持 `sqlite` 和 `memory`，默认 `sqlite`，用于保存多轮会话状态。
- `CHECKPOINTER_SQLITE_PATH` 默认 `./storage/checkpoints.sqlite3`，仅在 `CHECKPOINTER_TYPE=sqlite` 时使用。
- `FEEDBACK_LOG_PATH` 默认 `./storage/feedback.jsonl`，用于保存 Web/API 提交的回答反馈。
- `DATABASE_URL` 默认 `postgresql+psycopg://rag:rag@localhost:5432/rag`，用于多租户业务数据和后续 pgvector 检索。
- `REDIS_URL` 默认 `redis://localhost:6379/0`。
- `CELERY_BROKER_URL` 默认 `redis://localhost:6379/1`。
- `CELERY_RESULT_BACKEND` 默认 `redis://localhost:6379/2`。
- `JWT_SECRET_KEY` 默认值仅适合本地开发，生产环境必须替换。
- `ACCESS_TOKEN_EXPIRE_MINUTES` 默认 `60`。
- `UPLOAD_DIR` 默认 `./storage/uploads`，用于保存上传原始文件。
- `RATE_LIMIT_ENABLED` 默认 `true`，用于开启 `/api/v1` 接口限流。
- `RATE_LIMIT_REQUESTS` 默认 `60`，表示一个窗口内允许的请求数。
- `RATE_LIMIT_WINDOW_SECONDS` 默认 `60`，表示限流窗口秒数。
- `HOT_QUESTION_CACHE_ENABLED` 默认 `true`，用于缓存同一用户同一知识库的热点问题回答。
- `HOT_QUESTION_CACHE_TTL_SECONDS` 默认 `300`，表示热点问题缓存有效期秒数。
- `LANGSMITH_TRACING` 默认 `false`，开启后由 LangChain/LangSmith 记录 Agent trace。
- `LANGSMITH_API_KEY` 在 `LANGSMITH_TRACING=true` 时必填。
- `LANGSMITH_PROJECT` 默认 `langchain-rag`。
- `LANGSMITH_ENDPOINT` 可选，默认使用 LangSmith 官方地址。
- `TOKEN_INPUT_COST_PER_1K` 和 `TOKEN_OUTPUT_COST_PER_1K` 默认 `0`，用于本地按 usage 估算 token 成本。
- 入库当前支持 `.txt`、`.md`、`.pdf`、`.docx`、`.html`、`.htm`。

## 常用评测命令

### 数据库服务

仅启动 PostgreSQL + Redis 依赖:

```powershell
docker compose up -d postgres redis
uv run alembic upgrade head
```

当前 Alembic migration 环境已经接入 SQLAlchemy metadata。新增或修改 ORM 模型后，使用:

```powershell
uv run alembic revision --autogenerate -m "message"
```

### Celery Worker

本地开发时，启动 Redis 后，可以启动文档处理 worker:

```powershell
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

上传文档成功后，API 会尝试投递 `documents.process` 任务。若 Redis / broker 暂不可用，上传记录仍会保留为 `pending`，可以稍后通过同步处理入口重试。

### API smoke tests

```powershell
uv run python -m unittest tests.test_api
```

### 完整项目一键启动

一条命令启动 PostgreSQL、Redis、FastAPI、Celery worker，并在 FastAPI 中托管 React 构建产物:

```powershell
docker compose up -d --build
```

打开:

```text
http://127.0.0.1:8000
```

`api` 服务启动时会自动执行 `alembic upgrade head`，然后监听 `http://127.0.0.1:8000`。Docker 镜像构建时会先执行 `frontend` 的 `npm ci` 和 `npm run build`，再把 `frontend/dist` 复制进后端镜像。

如果容器内 API / worker 需要访问宿主机上的 Ollama 或兼容 OpenAI 服务，不要在 `.env` 里使用 `http://127.0.0.1:11434/v1`，应改为:

```env
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

### 多租户端到端 Smoke

方式一：一键启动完整项目:

```powershell
docker compose up -d --build
uv run python scripts/smoke_multitenant.py
```

方式二：本机进程调试。先启动依赖并创建当前开发 schema:

```powershell
docker compose up -d postgres redis
uv run alembic upgrade head
```

再分别启动 API 和 Celery worker:

```powershell
uv run python -m app.main web
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

执行端到端 smoke:

```powershell
uv run python scripts/smoke_multitenant.py
```

当前主线默认按本地或兼容服务的 `bge-m3` embedding 设计，请确保 `.env` 或当前 shell 中设置:

```env
EMBEDDING_DIMENSION=1024
```

Docker Compose 的 `api` / `worker` 服务会读取 `.env` 中的模型配置，并自动把数据库和 Redis 地址改为容器内部服务名。

修改 embedding 维度后，需要重新执行:

```powershell
uv run alembic upgrade head
```

如果数据库中已经存在旧维度的 pgvector 列，开发环境不做历史兼容迁移；直接清理本地 `postgres_data` volume 或重建数据库，然后重新执行 `uv run alembic upgrade head`。

运行 baseline 前可以先检查 pgvector 维度配置:

```powershell
uv run python -m evaluation.check_pgvector_embedding_config
uv run python -m evaluation.check_pgvector_embedding_config --probe-model
```

不带 `--probe-model` 时只检查配置和数据库列维度；带 `--probe-model` 会真实调用 embedding 模型，适合确认兼容 OpenAI 服务实际返回的向量维度。数据库不可达时会快速返回 `database_error`，先确认 Docker/PostgreSQL 已启动。

该脚本会依次执行:

1. 健康检查
2. 用户注册 / 登录
3. 创建知识库
4. 上传 txt 文档
5. 等待异步处理完成
6. 如果异步处理未完成，默认调用同步处理接口兜底
7. 调用问答接口并检查 references
8. 查询聊天会话和消息记录

如果当前环境没有可用模型配置，可先跳过问答调用，只验证认证、知识库、上传和处理链路:

```powershell
uv run python scripts/smoke_multitenant.py --skip-chat
```

本地模型首次推理较慢时，可以调大请求超时:

```powershell
uv run python scripts/smoke_multitenant.py --request-timeout 240
```

### 检索评测

```powershell
uv run python -m evaluation.evaluate_pgvector_retrieval --user-id 1 --kb-id 1 --search-type similarity hybrid --reranker off on --limit 10 --bad-cases-out data/eval/pgvector_bad_cases.jsonl --manifest-output storage/exports/pgvector_retrieval_eval_manifest.json
uv run python -m evaluation.run_pgvector_baseline --user-id 1 --kb-id 1 --retrieval-limit 10 --answer-limit 5
uv run python -m evaluation.run_pgvector_baseline --user-id 1 --kb-id 1 --retrieval-limit 10 --skip-answer
```

`evaluate_pgvector_retrieval` 使用相同 retrieval eval 样本评测 `/api/v1` 主链路的 PostgreSQL + pgvector 检索。它必须显式传入 `--user-id` 和 `--kb-id`，结果会同时检查 source / keyword 命中和返回 chunk metadata 中的租户范围是否匹配当前用户与知识库。`--search-type similarity hybrid` 可以对比纯向量召回与 pgvector dense + lexical RRF 融合召回，`--reranker off on` 可以对比 embedding + lexical rerank 效果。

`run_pgvector_baseline` 会串行运行 pgvector retrieval eval、pgvector answer sampling 和 answer eval，并把 baseline manifest、bad cases 和 answer runs 放到 `storage/exports/pgvector_baselines/{run_id}/`。实际执行完成后，`baseline_manifest.json` 会回填 retrieval manifest 数量、answer run 数量和 bad case 数量。

如果 baseline 中途失败，`baseline_manifest.json` 会标记 `status=failed` 并记录失败命令。常见原因是 `EMBEDDING_DIMENSION` 与实际 embedding 模型输出维度不一致，或缺少模型 API Key。

维度不一致时会看到 `Embedding dimension mismatch: EMBEDDING_DIMENSION=..., actual=...`。处理方式是让 `.env` 中的 `EMBEDDING_DIMENSION` 与当前 embedding 模型输出一致，并重建数据库与已有 embeddings；不要混用不同维度的 embedding 数据。本项目开发阶段不维护旧 `vector(1536)` 迁移，旧库可以直接重建后重新上传/处理文档。

## 日志边界

运行日志统一由 `app.config.logging_setup.setup_logging()` 配置，FastAPI lifespan 会在进程启动时初始化。Agent、tool、retrieval、worker 代码只使用 `logging.getLogger(__name__)` 获取 logger，不单独配置 handler。

`operation_logs` 是数据库业务审计表，用于记录注册、登录、知识库、文档、问答等用户操作；它不是运行日志系统，也不替代文件日志。

如果只想先验证 retrieval baseline 路径，可临时在 PowerShell 中设置:

```powershell
$env:EMBEDDING_DIMENSION='1024'
uv run python -m evaluation.check_pgvector_embedding_config
uv run python -m evaluation.run_pgvector_baseline --user-id 2 --kb-id 2 --retrieval-dataset data/eval/current_kb_retrieval.jsonl --retrieval-limit 1 --skip-answer
```

注意: smoke 文档和正式评测集语义不匹配时，retrieval pass rate 为 0 是预期现象，不能据此判断 hybrid / rerank 策略优劣。为当前知识库准备专用样本时，参考 [evaluation.md](evaluation.md)。

### 采样回答

```powershell
uv run python -m evaluation.generate_pgvector_answers --user-id 1 --kb-id 1 --limit 5
```

### 回答评测

```powershell
uv run python -m evaluation.evaluate_answers --limit 5
uv run python -m evaluation.evaluate_answers --show-passes
uv run python -m evaluation.evaluate_answers --bad-cases-out data/eval/bad_cases.jsonl
```

### 抓取单次 Trace

```powershell
当前 `/api/v1/chat/stream` 会输出 Agent tool trace。排查问答时先看 SSE 中的 `tool_call` / `tool_result`，再结合 pgvector baseline 和 chat run 记录。
```

## 统一入口

常用启动方式现在统一走 `app.main web`:

```powershell
uv run python -m app.main web
```

如果需要自定义 FastAPI Web 地址或端口:

```powershell
uv run python -m app.main web --host 0.0.0.0 --port 8000
uv run python -m app.main web --reload
```

## React 前端

前端位于 `frontend/`，使用 React + Vite + TypeScript。开发时先启动 FastAPI:

```powershell
uv run python -m app.main web
```

另开终端启动 Vite:

```powershell
cd frontend
npm install
npm run dev
```

Vite 默认地址为 `http://127.0.0.1:5173`，前端通过 `/api/v1` 调用 FastAPI。

生产构建:

```powershell
cd frontend
npm run build
```

构建产物位于 `frontend/dist/`。当该目录存在时，FastAPI Web 入口会优先托管 React 构建产物。

## GitHub Pages 预览

仓库内置 `.github/workflows/frontend-pages.yml`，推送到 `master` 或 `main` 后会构建 `frontend/` 并发布到 GitHub Pages。

Pages 只适合预览 React 静态界面。完整 RAG 问答需要 FastAPI 后端运行在可访问的服务上。如果已经部署了后端，可在 GitHub 仓库变量中设置:

```text
VITE_API_BASE_URL=https://your-api.example.com
```

本地开发不需要设置该变量，Vite 会继续代理 `/api` 到 `http://127.0.0.1:8000`。
聊天界面还需要设置 `VITE_API_TOKEN` 和 `VITE_KB_ID`，分别对应登录后的 access token 和当前知识库 ID。

## 多租户认证 API

新的产品化接口从 `/api/v1` 开始。认证接口:

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

注册请求:

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "password-123"
}
```

登录请求:

```json
{
  "username_or_email": "alice",
  "password": "password-123"
}
```

登录响应会返回 `access_token`。后续 `/api/v1` 业务接口通过 Bearer Token 鉴权:

```text
Authorization: Bearer <access_token>
```

## 多租户知识库 API

知识库接口:

```text
POST   /api/v1/kbs
GET    /api/v1/kbs
GET    /api/v1/kbs/{kb_id}
PUT    /api/v1/kbs/{kb_id}
DELETE /api/v1/kbs/{kb_id}
```

所有接口都依赖当前登录用户，只能访问当前用户自己的知识库。

创建请求:

```json
{
  "name": "产品知识库",
  "description": "产品说明、售后和故障排查资料"
}
```

## 多租户文档 API

文档接口:

```text
POST   /api/v1/kbs/{kb_id}/documents
GET    /api/v1/kbs/{kb_id}/documents
GET    /api/v1/documents/{document_id}
DELETE /api/v1/documents/{document_id}
POST   /api/v1/documents/{document_id}/process
```

上传接口使用 `multipart/form-data`，字段名为 `file`。上传成功后保存原始文件、创建 `documents` 记录，初始状态为 `pending`，并尝试投递 Celery 异步处理任务。

同步处理入口会加载原始文件并更新状态:

```text
pending -> processing -> completed
pending -> processing -> failed
```

当前同步处理会完成解析、切片、embedding 和 pgvector 入库。处理成功后状态变为 `completed`，失败时变为 `failed` 并写入 `error_message`。

Celery 任务复用同一套同步处理逻辑，因此失败状态和幂等策略与同步入口一致。每次处理会先删除该 document 已有 chunks，再重新写入新 chunks，避免任务重试造成重复入库。

pgvector 检索模块会在 SQL 层按 `user_id + kb_id` 过滤:

```text
document_chunks.user_id = current_user.id
document_chunks.kb_id = requested_kb_id
```

检索结果会转换为结构化 references，供后续问答接口保存到 `chat_messages.references`。

## 多租户问答 API

问答和聊天记录接口:

```text
POST /api/v1/kbs/{kb_id}/chat
POST /api/v1/kbs/{kb_id}/chat/stream
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

`session_id` 可选。不传时创建新会话，传入时只允许复用当前用户自己的会话，且会话必须属于当前 `kb_id`。

问答流程:

1. 校验当前用户有权访问知识库。
2. 保存用户问题到 `chat_messages`。
3. 使用 pgvector 在 `user_id + kb_id` 范围内检索 chunks。
4. 按 `RETRIEVAL_MAX_CONTEXT_CHARS` 压缩发送给模型的上下文。
5. 调用模型生成回答。
6. 保存助手回答和结构化 references。
7. 返回 `answer / references / session_id / run_id`。

上下文压缩只影响模型 prompt 中的资料长度，不会截断响应里保存和返回的 `references[*].content`。

同步问答响应会额外返回 `usage`，尽量包含 `input_tokens`、`output_tokens`、`total_tokens` 和 `cached`。不同模型网关可能不返回 token usage，此时本接口会返回 0 值占位并继续完成回答。

流式问答接口返回 `text/event-stream`，事件包括:

- `answer_delta`: 增量回答片段，字段为 `content` 和当前累计 `answer`
- `complete`: 完整回答、references、session_id、run_id、cache_hit 和 usage
- `error`: 流式问答失败信息，失败时对应 `chat_runs.status = failed`

每次问答都会创建一条 `chat_runs` 记录。operation log 的 `chat.ask` / `chat.stream` 以 `chat_run` 作为 resource，并在 details 中保留 `session_id`、`kb_id`、引用数量、缓存命中和 usage。

## 可观测与 Timeline

本项目不自研完整 Agent trace 平台。深度 trace、tool 调用树、LLM 输入输出、延迟和线上调试可以交给 LangSmith / Langfuse 这类外部平台；本地只保留产品运行态和演示所需字段:

- `chat_runs.usage`
- `chat_runs.token_cost`
- `chat_runs.prompt_version_id`
- `chat_runs.trace_id`
- `chat_runs.trace_url`
- `chat_run_events`
- operation logs

`chat_run_events` 是轻量本地 timeline，只记录 `tool_call`、`tool_result`、`complete`、`error` 这类关键事件及结构化 payload，便于前端回看一次 run 的执行过程。它不是 OpenTelemetry span 树，也不替代 LangSmith / Langfuse。

如果你要接外部平台，再开启 LangSmith:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=langchain-rag
```

如果需要本地成本估算，设置:

```env
TOKEN_INPUT_COST_PER_1K=0.001
TOKEN_OUTPUT_COST_PER_1K=0.002
```

`token_cost` 基于模型返回的 `usage.input_tokens` 和 `usage.output_tokens` 计算。不同兼容模型网关可能不返回 usage，此时成本为 0。

查询本地 run timeline:

```text
GET /api/v1/chat-runs/{run_id}/events
```

## Prompt 版本

`prompt_versions` 保存可追踪的系统 prompt 版本。当前内置 `default_rag_assistant / v1`，每个 `chat_runs` 会记录 `prompt_version_id`，方便后续把回答质量、bad cases 和 prompt 变更关联起来。

Prompt 版本接口:

```text
GET  /api/v1/prompts
POST /api/v1/prompts
POST /api/v1/prompts/{prompt_version_id}/activate
POST /api/v1/prompts/{prompt_version_id}/rollback
```

创建请求:

```json
{
  "name": "default_rag_assistant",
  "version": "v2",
  "description": "Stricter citation style",
  "system_prompt": "..."
}
```

`activate` 和 `rollback` 都会把指定 prompt version 设为当前 active 版本，区别是 operation log 的 action 分别记录为 `prompt.activate` 和 `prompt.rollback`，便于审计。

当前问答会在创建 `chat_runs` 时绑定 active prompt version，并把该版本的 `system_prompt` 传入 Agent。Agent 客户端会按 system prompt 文本缓存运行实例；切换 active prompt 后，新一轮 chat run 使用新 prompt，历史 run 仍保留原 `prompt_version_id`。

## MCP Server 示例

项目提供一个独立 MCP server 示例，不挂到 FastAPI 主进程:

```powershell
uv run python -m app.mcp.server
```

当前工具:

- `kb_search`: 按 `user_id + kb_id` 调用 pgvector 检索。
- `document_lookup`: 查询当前用户当前知识库内的文档元数据。
- `get_chat_run`: 查询当前用户自己的 chat run、usage、token cost 和 trace 字段。

这些工具都显式要求 `user_id` / `kb_id` 或 `user_id` / `run_id`，并在 SQL 层保留租户过滤。它们用于演示外部 Agent/MCP client 如何复用本项目能力，不替代 `/api/v1` 产品接口。

## 用户反馈

旧 `/api/feedback` 已删除。后续如果需要产品化反馈，应新增 `/api/v1` 反馈接口，并绑定 `user_id / kb_id / session_id / run_id`。

## 运行指标

FastAPI 提供基础进程内指标:

```powershell
curl http://127.0.0.1:8000/api/v1/metrics
```

当前包含:

- `chat_requests_total`
- `chat_stream_requests_total`
- `chat_errors_total`
- `feedback_total`
- `feedback_up_total`
- `feedback_down_total`
- `average_chat_elapsed_ms`
- `last_chat_elapsed_ms`
- `uptime_seconds`

这些指标随进程重启清零，适合本地调试和轻量部署观测。需要长期趋势或告警时，再接入 Prometheus / OpenTelemetry 等外部系统。

## 注意事项

- 旧本地 Chroma 评测入口已删除，检索质量验证使用 `evaluate_pgvector_retrieval`。
- `generate_pgvector_answers` 会真实调用模型，需要 `.env` 中的模型配置和 API Key 可用。
- `evaluate_answers` 默认会把未通过样本导出到 `data/eval/bad_cases.jsonl`，便于后续回看 bad case。
- 如果命令报依赖缺失，先执行 `uv sync`，再重试 `uv run ...`。
