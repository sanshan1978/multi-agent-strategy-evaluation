# RAG 知识库扩容设计

## 一、项目现状

当前 RAG 知识库只有 1 个 Markdown 源文件、7 个二级标题知识单元和
5 条检索评测用例。现有规模足以证明文档摄取、Embedding、Chroma
存储、混合检索、重排序、Trace 和 Evaluation 已经连通，但不足以验证
主题相似、查询改写和复合约束下的检索质量。

## 二、本轮目标

在不引入真实敏感资料的前提下，为项目构建一套规模适中、可以长期维护的
虚构对抗仿真知识库。

扩容后的语料应具备一定的主题多样性和语义重叠，用于检验 Hybrid Search
和 Rerank 的真实效果，同时控制 Qwen Embedding 调用量与本地维护成本。

## 三、实施范围

- 在 `rag/documents` 下维护 12 个 Markdown 源文件。
- 总计生成 60～70 个二级标题知识单元。
- 默认 RAG 评测集扩展到 30 条用例。
- 所有内容均为虚构仿真语料，重点描述系统评估、安全约束、多智能体协作和
  决策行为。
- 保留现有 Markdown 摄取格式和 Chroma 技术方案。
- 新增知识库契约测试和评测集契约测试。
- 重建现有 `tactical_knowledge_qwen_free` Chroma Collection。
- 将最终改动和实测数据记录到 `OPTIMIZATION_LOG.md`。

## 四、知识库结构

知识库按照职责拆分为以下 12 个文件：

1. `terrain_and_scenarios.md`：地形与场景
2. `intelligence_and_reconnaissance.md`：情报与侦察
3. `communication_and_command.md`：通信与指挥
4. `resources_and_logistics.md`：资源与补给
5. `multi_agent_coordination.md`：多智能体协作
6. `risk_and_safety_constraints.md`：风险与安全约束
7. `deception_and_anomaly_response.md`：欺骗识别与异常处置
8. `strategy_evaluation_metrics.md`：策略评估指标
9. `decision_workflow_and_termination.md`：决策流程与终止条件
10. `degradation_and_recovery.md`：降级与恢复
11. `tool_calling_governance.md`：工具调用治理
12. `compound_scenario_cases.md`：复合场景案例

每个文件包含：

- 一个一级标题，表示文档名称；
- 一组文件级标签；
- 5～6 个二级标题知识单元；
- 每个知识单元使用唯一的英文标题和中文正文。

每个知识单元的长度应尽量控制在一个 Chunk 内，使评测目标稳定且结果便于
解释。原有 `tactical_knowledge.md` 中的内容会重新分配到对应主题文件，
随后删除旧文件，避免内容重复和源文件统计失真。

## 五、语料编写规则

- 只描述虚构仿真系统行为，不提供真实作战操作资料。
- 每个知识单元说明适用条件、建议的系统行为、安全限制和可观测评估证据。
- 相近主题可以共享部分关键词，以形成具有区分难度的检索环境。
- 每个知识单元必须包含能够与相似内容区分开的特征词。
- 标签统一使用稳定的英文蛇形命名，兼容现有 Metadata 解析器。
- 二级标题必须全局唯一，因为当前评测系统通过标题判断预期结果。

## 六、评测集设计

30 条默认评测用例分为五类：

- 8 条直接主题检索；
- 7 条中文自然语言改写；
- 6 条多条件复合查询；
- 5 条相似主题区分查询；
- 4 条跨文档关联查询。

每条评测用例包含：

- 唯一的 `case_id`；
- 自然语言查询；
- 一个或多个预期标题；
- 预期源文件名；
- `top_k=3`。

跨文档查询必须配置至少两个预期标题及对应源文件，并在 Top3 内同时命中，
用于验证检索器能够组合不同知识来源，而不是只返回单个相关片段。

## 七、评测验收指标

扩容后要求达到：

- `Hit@3 >= 0.90`
- `MRR >= 0.75`
- `NDCG@3 >= 0.80`
- Source Match Rate `>= 0.90`
- 每条结果都具有 Retrieval Trace、Fusion Evidence 和 Rerank Evidence
- 评测 CLI 未达到任一门槛时返回非零退出码
- 语义改写题的纯 BM25 基线 Hit@3 不高于 0.70

这里不要求所有指标必须达到 `1.0`。如果扩大语料后仍然轻易获得完全满分，
通常意味着查询直接复用了原文关键词，评测难度不足。

## 八、自动化测试

### 8.1 知识库契约测试

测试真实的 `rag/documents` 目录并验证：

- Markdown 文件数严格为 12；
- 摄取后 Chunk 数处于 60～70；
- 没有摄取失败的文件；
- 二级标题全局唯一；
- 12 个规定的主题文件全部存在；
- 每个 Chunk 都具有 Source、Document Title、Tags、Section Title 和
  Collection Metadata。

### 8.2 评测集契约测试

验证：

- 默认评测用例严格为 30 条；
- 所有 `case_id` 唯一；
- 每个预期标题真实存在于知识库；
- 每个预期源文件真实存在；
- 五种评测类别均具有对应的稳定 ID 前缀。

现有单元测试继续使用确定性的 Local Hashing Embedding，保证测试不依赖
网络和 API 额度。最终真实评测使用 Qwen
`qwen3.7-text-embedding` 与 Chroma HTTP 服务。

## 九、完整数据流程

1. `MarkdownIngestionPipeline` 递归读取 12 个 Markdown 文件。
2. 每个二级标题被转换成带 Metadata 的 `DocumentChunk`。
3. Qwen Embedding 生成 1024 维稠密向量。
4. `ChromaVectorStore` 写入新增或变更的 Chunk，并删除失效数据。
5. `KnowledgeRetriever` 使用 RRF 融合稀疏检索与稠密检索结果。
6. Rerank 对候选结果进行重新排序并记录排序证据。
7. `RAGEvaluator` 使用 30 条标准用例计算检索质量。

## 十、异常处理

- 无法读取或解析的文档以单文件失败的方式记录到摄取历史。
- 文件数或知识单元数偏离规定范围时，知识库契约测试失败。
- 预期标题或源文件不存在时，评测集契约测试失败。
- Qwen 健康检查或 Embedding 请求失败时，严格模式立即终止索引构建。
- Chroma 原有数据继续保存在 D 盘；重建过程使用幂等 Upsert 和失效数据
  删除机制，不直接删除持久化目录。

## 十一、本轮不做的内容

- 不导入真实军事手册或敏感作战数据。
- 不开发文档上传前端。
- 不增加 PDF、Word 或网页摄取。
- 不更换向量数据库或 Embedding 模型。
- 不把知识库扩大到 70 个 Chunk 以上。
- 不修改 Agent、LangGraph、MCP 或 Trace 的现有行为。

## 十二、完成标准

只有同时满足以下条件，本轮扩容才算完成：

1. 知识库契约测试和评测集契约测试全部通过。
2. 项目完整自动化测试全部通过。
3. 重建索引后，Chroma 中包含 60～70 条当前文档数据。
4. 30 条真实评测达到全部目标指标。
5. Retrieval Evidence 能确认实际使用了 Chroma HTTP 和 Qwen Embedding。
6. `OPTIMIZATION_LOG.md` 和测试文档记录实际测量结果，而不是规划值。
