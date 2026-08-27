# RAG 知识库扩容实施计划

> **执行要求：** 使用 `executing-plans` 或 `subagent-driven-development`
> 按任务逐项实施；所有功能修改遵循测试先行。

**目标：** 将现有 1 个文件、7 个知识单元、5 条评测用例扩展为 12 个主题文件、
60～70 个知识单元和 30 条评测用例，并通过 Chroma HTTP 与 Qwen Embedding
完成真实检索评测。

**架构：** 沿用现有 Markdown 二级标题语义分块、Qwen Embedding、Chroma
HTTP、Hybrid Search、RRF 和 Rerank。新增知识库契约测试锁定语料规模及
Metadata 完整性，扩展现有 `RAGEvaluationCase` 基准验证检索质量。

**技术栈：** Python、pytest、Markdown、Qwen
`qwen3.7-text-embedding`、ChromaDB 1.5.9、BM25、Dense Retrieval、RRF、
Rerank。

## 全局约束

- 只使用虚构仿真语料，不引入真实敏感作战资料。
- `rag/documents` 严格包含 12 个 Markdown 文件。
- 摄取后知识单元总数为 60～70。
- 默认评测用例严格为 30 条。
- 不修改 Agent、LangGraph、MCP 和 Trace 的行为。
- 本轮所有说明文档使用中文。

---

### 任务一：建立知识库契约测试

**文件：**
- 新建：`tests/test_knowledge_corpus.py`

**产出：**
- `test_knowledge_corpus_has_expected_files_and_chunk_count`
- `test_knowledge_corpus_has_unique_titles_and_complete_metadata`

- [x] 编写测试，要求 12 个指定文件和 60～70 个 Chunk。
- [x] 运行测试并确认因当前只有 1 个文件、7 个 Chunk 而失败。
- [x] 保留失败证据，进入语料扩充。

### 任务二：扩充主题知识库

**文件：**
- 删除：`rag/documents/tactical_knowledge.md`
- 新建：`rag/documents/terrain_and_scenarios.md`
- 新建：`rag/documents/intelligence_and_reconnaissance.md`
- 新建：`rag/documents/communication_and_command.md`
- 新建：`rag/documents/resources_and_logistics.md`
- 新建：`rag/documents/multi_agent_coordination.md`
- 新建：`rag/documents/risk_and_safety_constraints.md`
- 新建：`rag/documents/deception_and_anomaly_response.md`
- 新建：`rag/documents/strategy_evaluation_metrics.md`
- 新建：`rag/documents/decision_workflow_and_termination.md`
- 新建：`rag/documents/degradation_and_recovery.md`
- 新建：`rag/documents/tool_calling_governance.md`
- 新建：`rag/documents/compound_scenario_cases.md`

**产出：**
- 12 个主题文件。
- 每个文件 5 个全局唯一的二级标题，共 60 个语义 Chunk。
- 每个知识单元包含适用条件、系统行为、约束与评估证据。

- [x] 使用 `apply_patch` 删除旧文件并新建 12 个主题文件。
- [x] 运行知识库契约测试，确认文件数、Chunk 数和 Metadata 全部通过。
- [x] 运行现有摄取测试，确认增量摄取行为没有回归。

### 任务三：建立并扩展评测集契约

**文件：**
- 修改：`tests/test_rag_evaluation.py`
- 修改：`rag_evaluation.py`

**产出：**
- 30 条默认评测用例。
- 五类稳定前缀：`direct_`、`paraphrase_`、`compound_`、
  `discrimination_`、`cross_`。

- [x] 先修改测试，要求 30 条用例、唯一 ID、预期标题和源文件均真实存在。
- [x] 运行测试并确认因当前只有 5 条旧用例而失败。
- [x] 将 `build_default_rag_evaluation_cases` 扩展为 30 条。
- [x] 运行评测单元测试并确认通过。

### 任务四：回归测试与真实索引

**文件：**
- 可能修改：`rag_evaluation.py` 中不稳定或错误的评测查询。

**产出：**
- 完整 pytest 通过。
- Chroma Collection 中保留 60 条当前向量，旧 7 条被清理。
- 真实评测达到 `Hit@3 >= 0.90`、`MRR >= 0.75`、
  `NDCG@3 >= 0.80`、Source Match Rate `>= 0.90`。

- [x] 运行完整 pytest。
- [x] 启动 Chroma 服务并检查健康状态。
- [x] 使用 Qwen Embedding 重建索引。
- [x] 再次构建索引验证幂等性。
- [x] 运行 30 条真实 RAG Evaluation。
- [x] 仅通过调整查询表达或语料区分度修复低质量案例，不降低验收阈值。

### 任务五：记录实际结果

**文件：**
- 修改：`OPTIMIZATION_LOG.md`
- 修改：`TESTING.md`
- 修改：`README.md`

**产出：**
- 中文记录本轮文件、数据规模、技术、测试结果和真实检索指标。

- [x] 写入实际文件数、Chunk 数和向量条数。
- [x] 写入完整测试结果和真实评测指标。
- [x] 更新 README 的知识库规模说明。
- [x] 执行最终测试、编译检查、Docker 状态检查和敏感信息扫描。
