# RAG Runtime 适配规格

## 1. 结论

原始 runtime 设计方向是合理的: 它把 `API -> Run -> Agent -> Stream -> Persistence` 拆开，避免 API handler 直接管理 Agent 生命周期。

但如果直接照搬 DeerFlow 风格的通用 runtime，会对当前项目过重。我们现在不是要做通用 Agent 平台，而是要把现有多租户企业知识库 RAG 做稳:

```text
/api/v1/chat
  -> ChatService
  -> RagService / AgentChatClient
  -> app/agent
  -> retrieve_context tool
  -> pgvector retrieval(user_id, kb_id)
```

因此本项目应该采用 **轻量 Runtime 层**:

- 保留 Run 生命周期、SSE 事件桥、取消能力、并发策略。
- 复用现有 `chat_sessions`、`chat_messages`、`chat_runs` 表。
- 复用现有 Agent、tool、pgvector 检索。
- 不引入独立 sqlite store、rollback、subgraph runtime、通用 marketplace。

一句话:

> Runtime 是现有 Agent 问答链路的服务化执行壳，不是新的 RAG 实现，也不是新的 Agent 平台。

## 2. 当前系统已有能力

已经具备:

- FastAPI `/api/v1`
- JWT 多用户登录
- 知识库、文档、聊天记录表
- `chat_sessions`
- `chat_messages`
- `chat_runs`
- Agent + `retrieve_context` tool
- pgvector 检索，按 `user_id + kb_id` 过滤
- SSE 输出 `tool_call / tool_result / answer_delta / complete / error`
- 前端可展示 Agent 工具调用和检索片段

所以 runtime 不应该重做这些东西。

## 3. 当前缺口

现在真正缺的是运行态控制:

1. API handler 已开始通过 RuntimeService 启动 run，不再直接 for-loop Agent stream。
2. `chat_runs.id` 已作为 run_id，RunManager 管理当前进程内运行中任务。
3. MemoryStreamBridge 已解耦 Agent producer 和 SSE consumer。
4. 后端已有取消接口，前端已接入当前 run 取消按钮。
5. 暂不支持断线后重新 join 某次 run。
6. 同一会话并发请求第一版采用 interrupt 策略。

剩余重点是 run 查询展示和更完整的测试覆盖。

## 4. 边界

Runtime 负责:

- 创建 run
- 管理 run 状态
- 管理同一 `session_id/thread_id` 的并发策略
- 启动后台 Agent 任务
- 把 Agent 事件写入 StreamBridge
- 给 API 层提供 SSE consumer
- 处理取消、异常、清理

Runtime 不负责:

- 用户鉴权
- 知识库权限判断
- 文档解析
- embedding
- pgvector 查询细节
- prompt 内容
- tool 内部逻辑
- 答案质量评测

RAG 检索继续放在:

```text
app/tools/retrieve_context.py
app/retrieval/pgvector_store.py
```

## 5. 适配后的目录结构

推荐新增:

```text
app/runtime/
  __init__.py
  schemas.py
  manager.py
  stream.py
  service.py
  serialization.py
```

不要新建顶层 `runtime/`，保持项目分层一致。

## 6. 核心模型

### RuntimeRun

Runtime 内存态对象，不替代数据库 `chat_runs`。

```python
@dataclass
class RuntimeRun:
    run_id: int
    session_id: int
    user_id: int
    kb_id: int
    status: RuntimeRunStatus
    task: asyncio.Task | None = None
    abort_event: asyncio.Event = field(default_factory=asyncio.Event)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error: str | None = None
```

`run_id` 直接使用数据库 `chat_runs.id`，避免再引入一套 UUID 与映射关系。

### RuntimeRunStatus

第一阶段只需要:

```python
class RuntimeRunStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
```

数据库里已有 `ChatRunStatus`，runtime 状态名应与它保持一致。

### DisconnectMode

第一阶段支持:

```python
class DisconnectMode(StrEnum):
    cancel = "cancel"
    continue_ = "continue"
```

默认建议:

- 普通聊天 SSE: `cancel`
- 后台长任务: 未来再用 `continue`

## 7. RunManager

`RunManager` 只管理当前进程内的运行中任务。

最小接口:

```python
class RunManager:
    async def register(record: RuntimeRun) -> None: ...
    async def create_or_interrupt(record: RuntimeRun) -> RuntimeRun: ...
    def get(run_id: int) -> RuntimeRun | None: ...
    def active_for_session(session_id: int) -> RuntimeRun | None: ...
    async def set_status(run_id: int, status: RuntimeRunStatus, error: str | None = None) -> None: ...
    async def cancel(run_id: int) -> bool: ...
    async def cleanup(run_id: int, delay: float = 300) -> None: ...
```

并发策略第一版只做:

- `interrupt`: 同一 `session_id` 有运行中 run 时，取消旧 run，然后启动新 run。

暂不做:

- `reject`
- `rollback`
- 多 worker 分布式锁

原因: 当前系统还在单进程本地开发阶段，优先让用户体验正确。

## 8. StreamBridge

StreamBridge 用来解耦:

```text
Agent worker -> publish events -> API SSE consumer
```

第一版只实现内存版:

```python
class MemoryStreamBridge:
    async def publish(run_id: int, event: str, data: Any) -> None: ...
    async def publish_end(run_id: int) -> None: ...
    async def subscribe(run_id: int) -> AsyncIterator[StreamEvent]: ...
    async def cleanup(run_id: int, delay: float = 300) -> None: ...
```

事件名继续复用当前前端已经支持的名字:

- `tool_call`
- `tool_result`
- `answer_delta`
- `complete`
- `error`
- `heartbeat`
- `end`

不要改成 LangGraph 原生 `values/messages/updates` 直接暴露给前端。底层协议可以变，前端事件协议要稳定。

## 9. RuntimeService

新增 `app/runtime/service.py`，作为 API 与 ChatService/Agent 的连接层。

建议接口:

```python
class RuntimeService:
    async def start_chat_run(
        self,
        *,
        db: Session,
        user_id: int,
        kb_id: int,
        question: str,
        session_id: int | None,
        disconnect_mode: DisconnectMode = DisconnectMode.cancel,
    ) -> RuntimeRun:
        ...

    async def stream_run(self, run_id: int) -> AsyncIterator[StreamEvent]:
        ...

    async def cancel_run(self, run_id: int, *, user_id: int) -> bool:
        ...
```

`start_chat_run()` 内部可以复用现有 `ChatService` 的会话创建、消息保存、`chat_runs` 创建逻辑，也可以把这些逻辑进一步拆成私有方法。

不要让 RuntimeService 直接写 retrieval SQL。

## 10. API 适配

现有接口保留:

```http
POST /api/v1/kbs/{kb_id}/chat/stream
```

内部改为:

```text
validate request
  -> RuntimeService.start_chat_run(...)
  -> return StreamingResponse(RuntimeService.stream_run(run_id))
```

新增取消接口:

```http
POST /api/v1/chat-runs/{run_id}/cancel
```

可选新增查询接口:

```http
GET /api/v1/chat-runs/{run_id}
```

暂不新增 DeerFlow 风格的:

```http
POST /threads/{thread_id}/runs
POST /threads/{thread_id}/runs/stream
GET  /threads/{thread_id}/runs/{run_id}/join
```

原因: 当前产品 API 已经围绕 `kb_id`、`chat_session` 和多租户权限建模，强行换成 threads API 会增加迁移成本。

## 11. 后台执行流程

第一版 worker 流程:

```text
1. ChatService 创建/确认 chat_session
2. 保存 user message
3. 创建 chat_run(status=running)
4. RuntimeManager 注册 RuntimeRun
5. 后台 task 调 RagService.stream(...)
6. 每个 Agent 事件 publish 到 StreamBridge
7. tool_result 中的 citations/references 累积到内存
8. complete 时保存 assistant message
9. 更新 chat_run(answer, references, usage, completed)
10. publish complete/end
11. cleanup runtime 内存状态
```

失败:

```text
1. chat_run.status = failed
2. chat_run.error_message = str(exc)
3. publish error
4. publish end
```

取消:

```text
1. abort_event.set()
2. task.cancel()
3. chat_run.status = cancelled
4. publish error 或 cancelled
5. publish end
```

## 12. 序列化

需要新增 `app/runtime/serialization.py`，但只做当前事件需要的稳定输出。

第一版支持:

- dataclass
- Pydantic model
- Enum
- datetime
- LangChain message 的基础字段

不要把所有 LangGraph 内部状态暴露给前端。

稳定前端事件 payload:

```json
{
  "event": "tool_result",
  "data": {
    "tool_name": "retrieve_context",
    "status_line": "retrieve_context 已返回结果",
    "content": "...",
    "citations": []
  }
}
```

## 13. Persistence 策略

第一阶段不新增 sqlite/store provider。

已有 PostgreSQL 表就是持久化来源:

- `chat_sessions`: thread/session 容器
- `chat_messages`: user/assistant 消息
- `chat_runs`: 每次 run 的生命周期、usage、references、error
- `operation_logs`: 业务审计

Agent checkpointer 当前可以继续使用已有 `app/memory/checkpointer.py`。

后续如果要跨进程恢复 Agent 内部状态，再考虑 PostgreSQL checkpointer。

## 14. 与当前 Agent 的关系

当前 Agent 继续放在:

```text
app/agent/
app/tools/
app/services/rag_service.py
app/services/chat_client.py
```

Runtime 不直接 import `retrieve_context`，只调用 `RagService` 或 `AgentChatClient`。

RAG 上下文继续通过 runtime context 传入:

- `thread_id`
- `user_id`
- `kb_id`
- `db_session`
- `retrieval_profile`

tool 内部必须继续做:

```text
document_chunks.user_id = current_user.id
document_chunks.kb_id = requested_kb_id
```

## 15. 第一阶段实现顺序

按这个顺序做，别一口气做全:

1. [x] 新建 `app/runtime/schemas.py`
2. [x] 新建 `app/runtime/stream.py`，实现 `MemoryStreamBridge`
3. [x] 新建 `app/runtime/manager.py`，实现单进程 `RunManager`
4. [x] 新建 `app/runtime/service.py`
5. [x] 改造 `/api/v1/kbs/{kb_id}/chat/stream` 使用 RuntimeService
6. [x] 新增 `POST /api/v1/chat-runs/{run_id}/cancel`
7. [x] 给 `chat_runs` 查询接口补最小 schema
8. [x] 更新前端: 发送中显示 run_id，必要时显示取消按钮

## 16. 暂缓事项

这些设计先不要做:

- rollback
- reconnect replay
- sqlite store
- 独立 thread API
- subgraph streaming
- 多 agent marketplace
- 分布式 runtime
- Redis stream bridge
- LangGraph 内部 values/updates 全量透传

等当前单进程 runtime 稳定、评测闭环跑起来，再决定是否升级。

## 17. 验收标准

第一阶段完成后，应满足:

1. API handler 不再直接 for-loop Agent stream。
2. 每次提问都有 `chat_runs.id` 作为 run_id。
3. 前端 SSE 事件名保持兼容。
4. 同一会话重复发送时旧 run 会被取消或中断。
5. 取消接口能停止正在生成的回答。
6. 失败时 `chat_runs.status=failed` 且 SSE 返回 `error`。
7. Runtime 代码不 import pgvector store。
8. `retrieve_context` 仍是唯一知识库检索 tool。
9. 文档、聊天记录、引用来源仍落在现有 PostgreSQL 表。

## 18. 架构判断

这份 runtime 规格可以嵌入当前系统，但必须简化。

合理保留:

- RunManager
- StreamBridge
- 后台 task
- cancel
- 稳定事件序列化

必须改掉:

- 顶层 `runtime/` 目录，改成 `app/runtime/`
- 独立 thread API，改成复用 `chat_sessions`
- 独立 run id，改成复用 `chat_runs.id`
- sqlite/store provider，暂缓
- rollback/reconnect/subgraph，暂缓
- runtime 直接了解 RAG 参数，改为透传 context/profile

最终目标不是“实现 DeerFlow”，而是吸收它的运行态设计，把当前 RAG 系统变得更稳、更可取消、更可观测。
