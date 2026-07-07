# 执行清单

本文件只保留仍需推进的事项。已完成批次不在这里堆叠，历史见 [todo-done.md](todo-done.md) 和 git 提交记录。

## 当前阶段判断

后端主线已经收口为:

```text
/api/v1 + Runtime + Agent + PostgreSQL + pgvector + JWT + Redis/Celery
```

旧 `/api + Chroma + CLI + Streamlit` 已删除。Runtime 是当前问答运行态主线，负责 chat run 生命周期、SSE StreamBridge、取消和运行态查询。Agent 已恢复为当前主线的一部分，`retrieve_context` tool 直接调用 PostgreSQL/pgvector，并在 SQL 层保留 `user_id + kb_id` 权限过滤。当前最短板是质量评测还没有绑定真实知识库数据集，以及前端还没有会话历史加载。

## 当前优先级

1. 准备与当前知识库一致的 eval dataset，并跑 pgvector retrieval / answer baseline。
2. 根据 bad cases 决定 hybrid / rerank 默认策略。
3. 补齐前端聊天体验: 新会话、历史会话列表、消息加载、usage 展示。
4. 补齐 Agentic RAG 工程增强: Prompt 版本管理、MCP Server 示例、LangSmith trace 链接回填。
5. 再考虑更复杂的权限模型、运维面板和质量运营。

## 前端实现原则

- 组件按业务场景拆分，避免做成通用后台框架。
- 可以引入成熟依赖减少手写复杂度，但不要为了“看起来专业”堆设计系统。
- 优先使用浏览器原生能力、React state 和少量稳定工具库。
- API 调用集中在 `frontend/src/api.ts`，类型集中在 `frontend/src/types.ts`。
- 页面状态保持简单: token、当前用户、知识库列表、当前知识库、文档列表、聊天会话。
- 暂不做复杂路由、RBAC、组织空间、全局状态库和表格引擎。

可考虑的成熟依赖:

- `@tanstack/react-query`: 管理 API 请求、缓存、刷新和 loading/error 状态。
- `react-hook-form`: 登录、注册、知识库表单。
- `zod`: 前端表单校验和 API payload 校验。


## Batch F1: 前端 API Client 和会话状态

- [x] 增加 `/api/v1/auth/register`、`/api/v1/auth/login`、`/api/v1/auth/me` 前端 API 方法
- [x] 增加 `/api/v1/kbs` 创建、列表前端 API 方法
- [x] 增加知识库编辑、删除前端 API 方法
- [x] 增加文档上传、列表、删除、手动处理 API 方法
- [x] 增加文档详情前端 API 方法
- [x] 增加聊天 SSE API 方法
- [x] 统一 Bearer token 注入和基础错误处理
- [x] 将 token 保存到 `localStorage`
- [x] 移除对 `VITE_API_TOKEN` 和 `VITE_KB_ID` 的运行时依赖

建议组件/文件:

```text
frontend/src/api.ts
frontend/src/types.ts
frontend/src/hooks/useAuth.ts
frontend/src/hooks/useKbs.ts
frontend/src/hooks/useDocuments.ts
frontend/src/hooks/useChat.ts
```

## Batch F2: 登录 / 注册

- [x] 增加登录表单
- [x] 增加注册表单
- [x] 登录成功后保存 token 并加载当前用户
- [x] 未登录时只展示认证界面
- [x] 增加退出登录
- [x] 显示接口错误和 loading 状态

建议组件:

```text
frontend/src/components/AuthPanel.tsx
frontend/src/components/LoginForm.tsx
frontend/src/components/RegisterForm.tsx
```

## Batch F3: 知识库工作台

- [x] 展示当前用户知识库列表
- [x] 创建默认知识库
- [x] 创建自定义知识库
- [x] 编辑知识库名称和描述
- [x] 删除知识库前二次确认
- [x] 选择当前知识库后加载文档和聊天区域
- [x] 空知识库状态给出创建入口

建议组件:

```text
frontend/src/components/KbSidebar.tsx
frontend/src/components/KbFormDialog.tsx
frontend/src/components/EmptyState.tsx
```

## Batch F4: 文档上传和状态追踪

- [x] 支持选择文件上传到当前知识库
- [x] 展示文档列表: 文件名、content type、状态、错误信息、更新时间
- [x] 支持 pending / processing / completed / failed 状态样式
- [x] 支持手动触发处理 `/api/v1/documents/{document_id}/process`
- [x] 支持删除文档
- [x] 上传或处理后自动刷新文档列表

建议组件:

```text
frontend/src/components/DocumentPanel.tsx
frontend/src/components/DocumentUpload.tsx
frontend/src/components/DocumentList.tsx
frontend/src/components/StatusBadge.tsx
```

## Batch F5: 聊天体验收口

- [x] 聊天使用当前选中知识库，不再手动填 `kb_id`
- [x] 新会话、历史会话列表、消息加载
- [x] SSE 展示 `answer_delta / complete / error`
- [x] SSE 展示 Agent `tool_call / tool_result`
- [x] 引用来源展示 filename/source、chunk_index、content 预览
- [x] 发送中、错误、空 references 的状态处理
- [x] 保留 usage 展示，但不阻塞主要聊天体验
- [x] 增加只检索不问 AI 的 preview/debug 接口，用于直接查看 pgvector 命中的 chunks
- [x] 前端接入 chat run 取消按钮

建议组件:

```text
frontend/src/components/ChatPanel.tsx
frontend/src/components/SessionList.tsx
frontend/src/components/MessageBubble.tsx
frontend/src/components/ReferenceList.tsx
```

## Batch Q1: 真实数据质量基线

- [x] 增加 baseline runner 自定义 retrieval / answer dataset 参数
- [x] 增加质量评测闭环文档和 dataset 格式说明
- [ ] 准备一组与当前知识库一致的 eval dataset
- [ ] 运行 pgvector retrieval baseline
- [ ] 运行 pgvector answer sampling
- [ ] 运行 answer eval
- [ ] 保存 baseline manifest、answer runs 和 bad cases
- [ ] 根据结果决定 `RETRIEVAL_SEARCH_TYPE`、`RERANKER_ENABLED` 默认值

## Batch O1: 可观测与运行成本

- [x] 接入外部 tracing 环境变量，不自研完整 trace 后台
- [x] `chat_runs` 预留 `trace_id / trace_url`
- [x] 保存本地 `token_cost` 估算字段
- [ ] 外部平台 trace_url 自动回填（可选）
- [x] 前端 run 详情展示 usage / token_cost / trace_url

## Batch A1: Agentic RAG 加分项

- [x] Prompt 版本管理地基: prompt_versions 表、默认版本、run 记录 prompt_version_id
- [x] Prompt 版本管理 API: 创建、启用、列表、回滚
- [x] MCP Server 示例: 暴露 kb_search / document_lookup / get_chat_run
- [x] Runtime 使用 active prompt version 装配 Agent 系统提示词
- [x] Agent 执行事件持久化: chat_run_events 轻量 timeline

建议命令:

```powershell
uv run python -m evaluation.check_pgvector_embedding_config
uv run python -m evaluation.run_pgvector_baseline --user-id 1 --kb-id 1 --retrieval-dataset data/eval/current_kb_retrieval.jsonl --answer-dataset data/eval/current_kb_answer.jsonl --retrieval-limit 10 --answer-limit 5
```

## 暂不做

- 组织 / 团队 / RBAC / ACL
- 多向量库适配
- 复杂长期 memory
- 通用 Agent / subagent / tool marketplace
- 大型后台管理框架
- 在没有 baseline 前反复调 prompt
