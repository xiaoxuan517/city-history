# 已完成清单归档

归档日期: 2026-04-24

本文件记录已经完成的执行清单，当前待办请看 [todo.md](todo.md)。

## P0 质量闭环

### 评测集

- [x] 新建评测数据目录，例如 `data/eval/`
- [x] 整理 30 到 50 个真实问题样本
- [x] 覆盖事实问答、步骤问答、拒答场景
- [x] 为每个问题补充期望答案或关键事实点
- [x] 为每个问题标注期望命中的文档来源

### 检索评测

- [x] 新建 `evaluation/evaluate_retrieval.py`
- [x] 实现单问题检索评测入口
- [x] 输出 top-k 命中情况
- [x] 统计命中率、召回率或简单 hit rate
- [x] 支持对比不同 `search_type`、`top_k`、`fetch_k`

### 回答评测

- [x] 新建 `evaluation/evaluate_answers.py`
- [x] 建立回答结果采样脚本
- [x] 对回答做人工评分或规则评分
- [x] 至少区分正确、部分正确、无法回答但合理、幻觉四类结果
- [x] 沉淀 bad case 样本（已导出到 `data/eval/bad_cases.jsonl`）

### 可观测

- [x] 给一次完整问答记录 query、retrieved chunks、answer、citations
- [x] 明确日志字段，便于后续回放问题
- [x] 预留 traces 接口位置，后续可接 LangSmith 或其他 tracing

## P1 工程边界

### 服务层

- [x] 新建 `app/services/rag_service.py`
- [x] 把检索与回答主流程收敛到 service 层
- [x] 让 CLI、Streamlit 调同一 service 入口
- [x] 避免 UI 层直接拼装业务流程
- [x] 增加 FastAPI API 层，让 Web / API 复用同一 service
- [x] 增加用户反馈闭环，将回答反馈记录为 JSONL 供后续评测回放
- [x] 增加基础运行指标监控，提供 `/api/metrics` 观察请求、错误、反馈和耗时

### Agent 与 Middleware

- [x] 明确 `create_agent.py` 只负责模型、工具、middleware 装配
- [x] 把当前 middleware 真正接入主链路
- [x] 梳理 prompt 与动态上下文注入策略
- [x] 明确哪些逻辑属于 tool，哪些逻辑属于 agent

### 配置与基础设施

- [x] 给 `Settings` 增加基础校验
- [x] 明确必填环境变量和默认值策略
- [x] 缓存 embeddings 实例
- [x] 缓存 vector store 实例
- [x] 统一入口文件，减少重复启动路径
- [x] 增加 SQLite 会话状态持久化，并支持通过配置切回内存 checkpointer

### 文档结构

- [x] 保持 `README` 简洁，只做导航和项目介绍
- [x] 现状、路线图、执行清单放在 `docs/`
- [x] 后续新增架构说明时单独放文档，不继续堆进 `README`

## P2 检索升级

### 召回质量

- [x] 引入 reranker
- [x] 增加 metadata 过滤能力
- [x] 评估是否需要 hybrid search
- [x] 对不同文档类型调整 chunk 策略
- [x] 做离线 hybrid search 原型
- [x] 用 RRF 融合 dense 与 lexical 候选
- [x] 对比 `similarity + reranker` 与 hybrid 原型的 retrieval eval 结果
- [x] 将 hybrid search 作为可选检索模式接入主链路

### 上下文质量

- [x] 抽离 formatter 模块
- [x] 增加上下文裁剪与去重策略
- [x] 控制传给模型的上下文长度
- [x] 优化 citation 输出结构

### 入库能力

- [x] 抽离 loaders 模块
- [x] 支持更多文档类型，例如 docx、html
- [x] 明确增量入库与重建索引策略
- [x] 为入库过程补充更细粒度日志
- [x] 增加按 source 删除已入库文档 chunks 的命令
