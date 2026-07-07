# 架构评审（2026-04-09）

> 评审范围：`app/` 主链路、`evaluation/` 质量闭环、配置与运行入口。

## 总体结论

项目已经具备 **可运行的最小 RAG 闭环**，分层方向正确：`UI -> services -> agent/tools -> retrieval`。

但从“可演示”到“可长期维护/可产品化”仍有几处关键缺口：

1. 运行期状态与持久化能力不足（仅内存 checkpoint）。
2. 领域模型与事件协议定义偏松，跨层 `dict` 透传较多。
3. 检索与评测虽具雏形，但缺少统一实验记录与回归门禁。
4. 部分入口和依赖关系仍有“脚手架遗留”痕迹。

## 做得好的地方（应保留）

- 分层边界在文档和实现里基本一致，避免 UI 直接操作检索与 Agent 细节。
- `services/rag_service.py` 提供同步 + 流式统一输出，对 CLI/Streamlit 复用友好。
- retrieval 模块有“召回 + 格式化 + citation 提取”拆分，便于后续插入 reranker。
- 已有 `evaluation/` 目录和 retrieval/answer 两类评测脚本，具备建立质量闭环的基础。

## 架构缺陷与改进建议

### 1) 会话状态不可持久化（高优先级）

现状：Agent 使用 `InMemorySaver`，会话只在进程生命周期内可用。

风险：
- 服务重启后线程上下文丢失。
- 无法横向扩展（多进程/多实例）。
- 评测/回放难复现线上行为。

建议：
- 抽象 `CheckpointerProvider`，把 `InMemorySaver` 变为 dev 默认实现。
- 增加 `sqlite` 或 `postgres` 持久化实现，并由配置切换。

进展：
- 已新增 `app/memory/checkpointer.py`，通过 `CHECKPOINTER_TYPE=sqlite|memory` 统一创建 checkpointer。
- 默认使用 SQLite 持久化到 `CHECKPOINTER_SQLITE_PATH`，服务重启后可按同一 `thread_id` 恢复 LangGraph 会话状态。

### 2) 事件协议缺少强类型约束（高优先级）

现状：`chat_client -> rag_service -> UI` 之间大量使用 `dict[str, Any]`。

风险：
- 字段名漂移导致静默错误（例如 `usage/tool_calls/citations`）。
- 新前端接入需要重复猜测事件 schema。

建议：
- 建立统一事件模型（如 `Pydantic` discriminated union），明确 `tool_call/tool_result/answer/complete/error`。
- 在 service 层完成“协议适配”，UI 仅读取稳定字段。

进展：
- 已新增 `app/services/rag_types.py`，将 service 对外的 `RagResponse` / `RagStreamEvent` 从实现文件中抽出。
- FastAPI SSE 已集中通过 API schema 序列化，并补充了不调用模型的 stream smoke test。

### 3) 检索配置与运行策略耦合在全局 settings（中优先级）

现状：tool 和 retriever 强依赖全局 `settings`。

风险：
- 单进程内难做多租户或 A/B 实验。
- 评测脚本和线上参数不易一致回放。

建议：
- 引入 `RetrievalProfile`（top_k/search_type/fetch_k/max_chars）。
- `rag_service.ask/stream` 支持传入 profile，默认再回落到 settings。

进展：
- 已新增 `app/retrieval/profile.py`，retriever、retrieve_context tool 与 retrieval eval 已开始使用统一 profile。
- FastAPI `ChatRequest` 已支持可选 `retrieval_profile`，并通过 LangChain `ToolRuntime` 传递到 `retrieve_context`。
- retrieval eval 支持通过 `--manifest-output` 输出 run manifest，记录模型、profile、metadata filter 与 summary。

### 4) 依赖方向可进一步收紧（中优先级）

现状：目前 `services` 直接理解底层 stream 事件细节并做拼装。

风险：
- 当 agent/SDK 协议变更时，service 逻辑易大面积受影响。

建议：
- 在 `chat_client` 层增加“LangGraph 事件 -> 领域事件”适配器。
- `rag_service` 只做编排与聚合，不感知底层供应商字段。

### 5) 评测体系缺少“门禁化”与实验追踪（中优先级）

现状：有评测脚本，但缺少统一 run id、参数、结果归档与阈值门禁。

风险：
- 优化后难证明是“进步”还是“漂移”。
- PR 很难基于数据做 go/no-go。

建议：
- 固化 `eval run manifest`（模型、检索参数、数据集版本、时间戳）。
- 在 CI 增加最小评测门禁（例如 retrieval pass_rate 不低于基线 -x%）。

### 6) 工程入口存在重复和可读性噪音（低优先级）

现状：根目录和 `app/` 都有 streamlit 入口；`app/streamlit_app.py` 内含 `sys.path` 注入。

风险：
- 新同学难理解“官方入口”是哪一个。
- 打包/部署时路径魔法容易出隐式问题。

建议：
- 统一 `python -m app.main streamlit` 为唯一推荐入口。
- 清理 `sys.path` 注入，改为标准包运行方式。

## 推荐演进顺序（90 天）

### Phase 1（第 1-3 周）
- 统一事件 schema。
- 持久化 checkpointer（先 sqlite）。
- 补充 error 事件与失败可观测字段。

### Phase 2（第 4-7 周）
- 引入 RetrievalProfile 与实验参数传递。
- 补齐 eval manifest 与结果归档。
- 设定基础门禁阈值。

### Phase 3（第 8-12 周）
- 插入 reranker/hybrid 检索实验。
- 增加 API 层并复用 service。
- 逐步替换开发态逻辑（如路径注入、临时脚手架）。

## 可量化目标（建议）

- 稳定性：服务重启后线程可恢复（持久化通过）。
- 可维护性：事件字段变更在类型检查阶段即可暴露。
- 质量：retrieval 与 answer eval 有可追溯基线并可回归对比。
- 交付效率：每次优化可用统一实验记录复盘。
