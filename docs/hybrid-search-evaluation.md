# Hybrid Search 需求评估

本评估用于判断当前阶段是否需要引入 hybrid search，并记录离线原型与主链路可选接入后的结果。

## 评估方法

使用当前最佳 dense baseline:

```powershell
uv run python -m evaluation.evaluate_pgvector_retrieval --user-id 1 --kb-id 1 --search-type similarity --top-k 3 --fetch-k 8 --reranker on
```

再运行词面补救诊断:

```powershell
uv run python -m evaluation.evaluate_hybrid_need --show-failures
```

`evaluate_hybrid_need` 会先跑现有 dense retrieval，再对 dense 失败样本做全库 chunk 的词面匹配诊断。词面匹配使用评测样本中的 `expected_keywords` 和 query term，因此它是“是否值得做 hybrid”的诊断工具，不是线上 hybrid search 实现。

## 当前结果

数据集:

- retrieval eval 总样本: 34
- 计分样本: 29
- 拒答场景跳过: 5

Dense baseline:

- `similarity + reranker=on`
- passed: 25 / 29
- pass_rate: 86.21%
- dense_failed: 4

词面补救诊断:

- lexical_rescued_dense_failures: 4 / 4
- lexical_rescue_rate: 100.00%
- recommendation: `evaluate_hybrid_search`

离线 hybrid 原型:

```powershell
uv run python -m evaluation.evaluate_hybrid_search --show-changes
```

- baseline_passed: 25 / 29
- baseline_pass_rate: 86.21%
- hybrid_passed: 29 / 29
- hybrid_pass_rate: 100.00%
- improved: 4
- regressed: 0

主链路可选 `hybrid` 检索:

```powershell
uv run python -m evaluation.evaluate_pgvector_retrieval --user-id 1 --kb-id 1 --search-type hybrid --top-k 3 --fetch-k 8 --reranker off on
```

- `hybrid + reranker=off`: passed 29 / 29，pass_rate 100.00%
- `hybrid + reranker=on`: passed 29 / 29，pass_rate 100.00%

说明: 当前 `hybrid` 已作为最终融合排序接入 retrieval 层，默认 `RETRIEVAL_SEARCH_TYPE` 不变。即使 `RERANKER_ENABLED=on`，`hybrid` 也不会再套当前 reranker，避免 reranker 覆盖 lexical 召回收益。

可被词面补救的 dense 失败样本:

- `faq_015_mop_watermark`: 水痕/水渍场景，词面命中 `出水量 / 拖布 / 低速拖地`
- `faq_026_battery_drop`: 续航衰减场景，词面命中 `及时回充 / 满充满放 / 更换电池`
- `faq_031_water_tank_leak`: 水箱漏水场景，词面命中 `水箱盖 / 出水管 / 更换`
- `faq_068_wood_floor`: 木地板拖地场景，词面命中 `调小出水量 / 干拖模式 / 拖布拧干`

## 结论

当前建议把 `hybrid` 作为可选检索模式保留，并继续用 evaluation 观察后续数据集上的稳定性。

原因:

- 剩余 dense 失败样本不是完全无资料，而是相关 chunk 可通过词面信号找到。
- 失败集中在明确实体或操作词上，例如 `水箱盖`、`出水管`、`干拖模式`、`更换电池`。
- 现有 reranker 已把 pass rate 提到 86.21%，继续只调 dense 参数收益有限。

后续如果扩充评测集，应继续对比:

- `similarity + reranker=on`
- `hybrid`
- `hybrid + metadata_filter`
