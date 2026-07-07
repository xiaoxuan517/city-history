# 项目路线图

相关文档:

- AI 助手上下文入口: [ai-context.md](ai-context.md)
- 目标架构与收口计划: [target-architecture.md](target-architecture.md)
- 项目现状: [project-status.md](project-status.md)
- 架构说明: [architecture.md](architecture.md)
- 多租户企业知识库 RAG 规划: [multitenant-rag.md](multitenant-rag.md)
- 入库策略: [ingestion.md](ingestion.md)
- Hybrid Search 需求评估: [hybrid-search-evaluation.md](hybrid-search-evaluation.md)
- 执行清单: [todo.md](todo.md)
- 已完成清单归档: [todo-done.md](todo-done.md)

## 长期目标

长期目标不是做一个“能回答问题”的 demo，而是演进为一个多租户企业知识库 RAG 系统。

新的产品化目标详见 [multitenant-rag.md](multitenant-rag.md)。当前第一、第二阶段主体能力和架构收口主任务已经落地: `/api/v1 + Runtime + Agent + pgvector` 是唯一产品主线，旧 Chroma/CLI/Streamlit 链路已经删除，chat run 生命周期、Runtime SSE、取消、pgvector retrieval / answer eval、hybrid、rerank 和上下文压缩已经具备。详细计划见 [target-architecture.md](target-architecture.md)。

### 目标一: 可验证的 RAG 系统

需要满足:

- 检索优化可以量化评估
- 回答质量可以独立评估
- bad case 可以被追踪和回流
- 引用与拒答策略可以被验证

为了达到这一点，需要逐步补齐:

- 评测集
- retrieval eval
- answer eval
- tracing 与可观测能力

### 目标二: 可扩展的工程底座

需要满足:

- CLI、Web、未来 API 共用同一业务编排层
- retrieval、tool、agent、memory 边界清晰
- 模型、向量库、重排器可以逐步替换
- 配置、日志、运行入口更规范

### 目标三: 面向企业知识库的产品雏形

结合当前知识库内容和后端能力，更适合演进成下面这些方向:

- 多用户企业知识库
- 产品说明书问答
- 售后支持问答
- 故障排查助手
- FAQ 与知识运营后台

长期看，系统应具备这些特征:

- 回答基于事实
- 引用来源清晰
- 无法回答时稳定拒答
- 支持持续导入和维护知识库

## 架构演进方向

建议逐步演进到下面这类结构，但不要求一次性全部实现:

```text
app/
  retrieval/
    loaders.py
    splitter.py
    embeddings.py
    pgvector_store.py
    reranker.py
    formatter.py
    citations.py
  memory/
    checkpointer.py
  services/
    chat_service.py
    document_service.py
  runtime/
    manager.py
    service.py
    stream.py
  api/
    v1/
evaluation/
    dataset.py
    evaluate_pgvector_retrieval.py
    generate_pgvector_answers.py
    evaluate_answers.py
```

架构原则:

- `retrieval/` 只负责加载、切分、召回、重排、格式化
- `services/` 负责业务编排
- `evaluation/` 负责质量验证

## 短期计划

### P0: 架构收口

已基本完成。

计划内容:

- [x] 明确 `/api/v1 + Runtime + pgvector` 是产品主链路
- [x] 抽统一 retrieval interface / DTO
- [x] 删除旧 Chroma 链路，并将 Agent 迁移到 pgvector tool 主线
- [x] 增加 chat run 生命周期
- [x] 将 `/api/v1` SSE 升级为 runtime 管理的 token 级 streaming

预期结果:

- 新功能默认进入产品主线
- 检索、引用、流式、usage 和日志不再两套实现
- 后续做权限、评测、hybrid、rerank 时有稳定接口

### P1: 补齐前端最小产品闭环

计划内容:

- [ ] 登录 / 注册 / 当前用户
- [ ] 知识库列表、创建、编辑、删除和选择
- [ ] 文档上传、状态追踪、手动处理和删除
- [ ] 基于当前知识库聊天，展示引用和历史会话
- [ ] 移除对 `VITE_API_TOKEN` 和 `VITE_KB_ID` 的手动依赖

实现约束:

- 组件按业务场景拆分，不做通用后台框架。
- 可以用 `@tanstack/react-query`、`react-hook-form`、`zod` 这类成熟依赖减少手写状态和表单代码。
- 暂不引入复杂全局状态库、大型组件库或多页路由。

### P2: 建立 pgvector 多租户质量闭环

计划内容:

- [x] 建立 pgvector retrieval eval
- [x] 区分 retrieval eval 与 answer eval
- [x] 增加权限隔离评测样本
- [x] 沉淀 bad case、references 和检索参数
- [ ] 在真实 PostgreSQL 数据上跑出 baseline manifest

预期结果:

- 知道新产品主链路哪些问题答得好
- 知道哪些问题召回不准
- 后续引入 reranker 或 hybrid search 时有客观依据

### P3: 升级检索能力

计划内容:

- [x] 加入 reranker
- [ ] 支持 `/api/v1` 查询级 metadata 过滤
- [x] 优化上下文压缩
- [ ] 增强 citation 与 artifact 输出

预期结果:

- 召回质量更高
- 上下文更干净
- 回答更稳定，引用更可信

## 中期计划

当前多租户产品化后端能力已经基本具备，下一阶段重点是前端最小产品闭环、产品化运维能力和真实数据质量基线。

建议方向:

- 数据库地基: SQLAlchemy / Alembic / PostgreSQL / pgvector
- 用户认证: 注册、登录、JWT、当前用户依赖
- 知识库 CRUD: 所有数据按当前用户隔离
- 文档管理: 上传、状态追踪、解析、切片、向量化
- 问答: 基于 `user_id + kb_id` 的权限过滤检索、引用返回、聊天记录保存
- 异步处理: Celery + Redis 处理文档任务

## 当前不建议优先做的事

以下事情短期内不建议排在前面:

- 一次性把理想目录全部实现
- 同时支持过多向量库
- 过早接入复杂 memory 体系
- 一口气增加很多 tool
- 在没有评测前反复调 prompt

这些不是不做，而是不应该排在质量闭环之前。

## 里程碑建议

### 里程碑 1: 最小可评估

完成标准:

- 有基础评测集
- 能跑 retrieval eval
- 能跑 answer eval
- 至少有一组 bad case 样本

### 里程碑 2: 最小可维护

完成标准:

- 有 service 层编排
- 有更清晰的模块边界
- 会话状态不再只依赖内存
- 配置和日志更规范

### 里程碑 3: 最小可产品化

完成标准:

- 有 API
- 有知识库维护能力
- 有稳定的引用展示和拒答策略
- 有基础运营与质量反馈闭环

## 总结

推进顺序建议保持为:

1. 先做质量闭环
2. 再做工程边界
3. 再升级检索能力
4. 最后进入产品化建设

这个顺序最稳，也最符合当前项目阶段。
