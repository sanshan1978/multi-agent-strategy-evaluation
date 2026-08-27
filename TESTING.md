# 项目测试文档

本文档记录 `message_talk` 项目的测试目标、测试分层、常用验证命令和最近一次验证结果。项目当前主线是：

```text
Qwen Embedding -> RAG 知识增强 -> Agent 工具规划 -> LangGraph 执行 -> Trace 可观测 -> Evaluation 验证质量
```

测试的目的不是只证明代码能运行，而是证明 RAG、Agent Planner、工具调用、可观测 Trace、Evaluation 和真实 Qwen 模型接入都可以被重复验证。

## 1. 测试环境

当前推荐运行配置：

```text
LLM 模型：qwen3.7-plus
LLM Base URL：https://dashscope.aliyuncs.com/compatible-mode/v1
Embedding 模型：qwen3.7-text-embedding
Embedding Base URL：https://dashscope.aliyuncs.com/compatible-mode/v1
Embedding 维度：1024
Embedding 批次：8
VectorStore：Chroma HTTP
Chroma Endpoint：http://localhost:8001
Qwen 语义集合：tactical_knowledge_qwen_free
Strict Embedding：true
```

API Key 使用环境变量 `DASHSCOPE_API_KEY`。测试文档、命令输出和项目日志不应打印密钥内容。

## 2. 测试分层

### 2.1 配置与基础设施测试

对应文件：

- `tests/test_settings.py`
- `tests/test_storage.py`
- `tests/test_serializers.py`

覆盖内容：

- 默认模型配置：`qwen3.7-plus`
- Embedding runtime 配置：`qwen3.7-text-embedding`
- `DASHSCOPE_API_KEY` 到 embedding key 的 fallback
- SQLite 决策历史和 Evaluation 报告持久化
- API 响应序列化契约

### 2.2 FastAPI 接口测试

对应文件：

- `tests/test_api_fastapi.py`

覆盖内容：

- `GET /api/health`
- `GET /api/scenarios`
- `GET /api/tools`
- `POST /api/decide`
- `POST /api/decide/stream`
- `POST /api/evaluations/run`
- `POST /api/evaluations/planner/run`
- `POST /api/evaluations/rag/run`
- `GET /api/evaluations`
- `GET /api/evaluations/{report_id}`

重点验证接口参数校验、错误结构、SSE 流式输出、历史记录保存和评估报告保存。

### 2.3 Agent 决策引擎测试

对应文件：

- `tests/test_decision_engine.py`
- `tests/test_decision_graph.py`
- `tests/test_decision_auditor.py`

覆盖内容：

- 多智能体候选方案生成
- 动态权重计算
- LangGraph 节点顺序
- 条件节点跳过逻辑
- LLM 裁决成功、失败和 fallback
- 决策 Trace 节点完整性
- 决策审计状态

### 2.4 Planner 工具规划测试

对应文件：

- `tests/test_agent_planner.py`
- `tests/test_planner_evaluation.py`
- `planner_evaluation.py`
- `plan_execution_auditor.py`

覆盖内容：

- Agent 工具选择是否符合场景
- LLM Planner 输出计划的参数清洗
- 非法工具、重复工具和非法顺序修复
- planned tools 与 actual tool calls 一致性审计
- Planner Evaluation 指标：`tool_match_rate`、`average_repair_count`

### 2.5 RAG 检索与向量索引测试

对应文件：

- `tests/test_rag.py`
- `tests/test_rag_evaluation.py`
- `tests/test_embeddings.py`
- `tests/test_embedding_validation.py`
- `tests/test_vector_store.py`
- `tests/test_ingestion.py`
- `rag_evaluation.py`
- `embedding_validation.py`
- `scripts/build_rag_index.py`
- `scripts/validate_embedding_provider.py`

覆盖内容：

- Markdown Ingestion Pipeline
- 文件 hash 与 chunk 去重
- EmbeddingProvider 抽象
- 本地 `local-hashing` fallback 边界
- Qwen `qwen3.7-text-embedding` live provider 验证
- SQLite / Chroma Persistent / Chroma HTTP VectorStore
- Chroma heartbeat、Docker healthcheck 与 D 盘持久化
- BM25 + Dense Retrieval + RRF 融合
- RAG Evaluation 指标：`hit_at_k`、`MRR`、`nDCG`、`source_match_rate`

### 2.6 RAG Grounding 与证据归因测试

对应文件：

- `tests/test_grounding.py`
- `tests/test_evaluation.py`
- `grounding.py`

覆盖内容：

- RAG evidence 生成
- Agent proposal grounding
- Risk recommendation grounding
- Evaluation 对 grounding evidence 的强制检查

### 2.7 MCP 工具测试

对应文件：

- `tests/test_mcp_server.py`
- `tests/test_tools.py`
- `mcp_server.py`
- `tools/`

覆盖内容：

- Agent ToolRegistry 工具目录
- MCP Knowledge Hub 工具
- `query_knowledge_hub`
- `list_knowledge_collections`
- `get_retrieval_trace`
- 工具执行结果、fallback 和 metadata

## 3. 常用测试命令

基础代码质量验证：

```powershell
python -m py_compile workflow/__init__.py workflow/decision_graph.py agent_planner.py agents.py api_server.py api_fastapi.py decision_auditor.py decision_engine.py evaluation.py grounding.py planner_evaluation.py plan_execution_auditor.py rag_evaluation.py embedding_validation.py llm_coordinator.py logging_config.py main.py mcp_server.py memory.py models.py schemas.py serializers.py settings.py standards.py storage.py trace.py rag/__init__.py rag/embeddings.py rag/ingestion.py rag/vector_store.py rag/retriever.py tools/base.py tools/registry.py tools/knowledge_tool.py tools/memory_tool.py tools/risk_tool.py scripts/build_rag_index.py scripts/validate_embedding_provider.py
python -m pytest -q
node --check frontend/app.js
```

三类 Evaluation：

```powershell
python evaluation.py
python planner_evaluation.py
python rag_evaluation.py
```

Embedding Provider 验证：

```powershell
python scripts/validate_embedding_provider.py
```

Qwen 语义索引构建：

```powershell
python scripts/build_rag_index.py --strict
```

Chroma 服务验证：

```powershell
docker compose up -d chroma
docker compose ps
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod http://localhost:8001/api/v2/heartbeat
python scripts/build_rag_index.py --strict
```

LLM 集成验证可以使用 `DecisionEngine(llm_mode="on", llm_model="qwen3.7-plus")` 对预置场景运行一次，检查 `decision_mode` 是否为 `llm+rules(qwen3.7-plus)`，并确认 `llm_error=null`。

## 4. 最近一次验证结果

最近一次完整验证结果：

```text
Python py_compile：通过
node --check frontend/app.js：通过
python -m pytest -q -p no:cacheprovider：141 passed
pip check：No broken requirements found
pytest 环境隔离：自动使用 local-hashing、临时 SQLite 和测试 collection，不受用户级 Qwen/Chroma 配置影响
Agent Evaluation：3/3 passed，pass_rate=1.0，average_score=100.0
Planner Evaluation：3/3 passed，tool_match_rate=1.0，average_repair_count=0.0
知识库契约：12 个 Markdown 文件、60 个知识单元、标题唯一且 Metadata 完整
纯 BM25 全量基线：26/30 passed，hit_at_k=0.8667，MRR=0.8611，nDCG=0.8629
纯 BM25 语义改写基线：4/7 passed，hit_at_k=0.5714，MRR=0.4762，nDCG=0.5
Qwen Embedding live：ok=true，model=qwen3.7-text-embedding，dimensions=1024
Qwen Chroma HTTP 首次扩容：document_count=60，upserted=60，deleted=7
Chroma 幂等重建：upserted=0，skipped=60，deleted=0
Chroma Docker：chromadb/chroma:1.5.9，localhost:8001，health=healthy
FastAPI Docker：/api/health 返回 ok=true，容器 health=healthy
Chroma 数据持久化：D:\BaiduNetdiskDownload\message_talk_chroma_data
Qwen Chroma RAG Evaluation：30/30 passed，hit_at_k=1.0，MRR=0.9611，nDCG=0.9684，source_match_rate=1.0
RAG Quality Gate：passed=true，average_rerank_improvement=0.0333
Qwen LLM 集成：decision_mode=llm+rules(qwen3.7-plus)，planner_source=llm-planner，llm_error=null
```

这说明当前真实 Qwen 主线已经跑通：

```text
qwen3.7-plus LLM Planner/裁决
-> qwen3.7-text-embedding 语义向量
-> Chroma HTTP VectorStore
-> Hybrid RAG 检索
-> LangGraph/Trace
-> Evaluation 验证
```

## 5. 部署前检查清单

部署或演示前建议按顺序执行：

1. 确认 `DASHSCOPE_API_KEY` 已配置，且不在日志或文档中明文出现。
2. 确认 `MESSAGE_TALK_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`。
3. 确认 `MESSAGE_TALK_MODEL=qwen3.7-plus`。
4. 确认 `MESSAGE_TALK_EMBEDDING_MODEL=qwen3.7-text-embedding`。
5. 确认 `MESSAGE_TALK_EMBEDDING_DIMENSIONS=1024`。
6. 确认 `MESSAGE_TALK_EMBEDDING_BATCH_SIZE=8`。
7. 确认 `MESSAGE_TALK_VECTOR_STORE=chroma`。
8. 确认 `MESSAGE_TALK_CHROMA_HOST=localhost`、`MESSAGE_TALK_CHROMA_PORT=8001`。
9. 执行 `docker compose up -d chroma`，确认服务状态为 `healthy`。
10. 执行 `python scripts/validate_embedding_provider.py`。
11. 执行 `python scripts/build_rag_index.py --strict`。
12. 执行 `python -m pytest -q`。
13. 执行 `python evaluation.py`、`python planner_evaluation.py`、`python rag_evaluation.py`。

## 6. 面试解释口径

可以这样介绍测试体系：

```text
这个项目不是只做了 RAG 和 Agent 功能堆叠，我还补了质量验证链路。
基础层用 pytest 覆盖配置、存储、API、序列化和工具调用。
Agent 层用 Evaluation 验证不同场景下的工具选择、Trace 节点、风险等级和最终分数。
Planner 层单独做了工具计划评估、非法计划修复和 planned-vs-actual 审计。
RAG 层用 hit@k、MRR、nDCG 和 source_match_rate 验证召回质量。
模型接入层做了 Qwen Embedding live validation 和 strict mode，避免系统悄悄降级到本地 fallback。
```

重点突出：

```text
RAG 知识增强 -> Agent 工具规划 -> LangGraph 执行 -> Trace 可观测 -> Evaluation 验证质量
```
