# 面向复杂对抗场景的多智能体策略评估系统

一个面向复杂对抗场景的多智能体策略评估与 LLM 增强裁决项目。系统先通过 Planner 规划工具调用，再让 5 个角色化策略 Agent 并行调用 Qwen 生成结构化候选方案，最后结合规则指标基线、动态权重、Reviewer 和审计输出排名；无模型或单 Agent 失败时可按模式回退到本地规则。

## 项目定位

项目围绕复杂场景下的 Agent 规划、执行、评估与可观测性，提供以下核心能力：

- 5 个角色化 LLM Strategy Agent 并行生成候选方案
- 单 Agent 结构化校验、错误隔离和规则 fallback
- 动态权重评分与排序
- Agent 互评影响置信度
- LLM JSON 裁决增强
- 决策 Trace 记录关键流程
- SQLite 历史决策记录
- 无 API Key 时自动降级到本地规则
- 前端可视化展示决策结果、Trace 时间线和历史记录
- SSE 流式展示决策进度
- RAG 知识库召回并注入 Agent 决策上下文
- RAG Grounding Evidence，将知识证据绑定到 Agent 方案与风险建议
- Agent Memory 相似历史案例召回、摘要写入策略与长期记忆
- Agent Tool Calling 工具注册、调用记录与风险分析
- 真实 MCP Server，对外暴露 Agent 工具与知识库查询/观测工具
- Agent Evaluation 默认场景集、指标统计与回归报告
- Agent Planner Evaluation 工具规划评估、非法计划修复与 Trace 可观测
- Agent / Planner / RAG Evaluation 历史报告持久化
- Planner 执行审计，对比 planned tools 与 actual tool calls
- 请求 ID 链路追踪与接口耗时响应头
- FastAPI 接口与 pytest 测试

## 技术栈

- Python
- FastAPI
- Pydantic
- SQLite
- LangChain OpenAI-compatible client
- Pydantic LLM Structured Output Validation
- ThreadPoolExecutor 并行 Agent 调度
- pytest
- HTML / CSS / JavaScript
- Docker / Docker Compose
- RAG / BM25 风格关键词检索
- RAG EmbeddingProvider / local-hashing fallback / OpenAI-compatible 预留
- OpenAI-compatible Embedding HTTP Client / Health Check
- Embedding Provider Validation / Semantic Guard / Dense Probe
- SQLite VectorStore / InMemory VectorStore / cosine similarity
- Chroma VectorStore / PersistentClient / HttpClient / Docker service
- Markdown Ingestion Pipeline / File Hash Dedup / Chunk Metadata
- RRF 多路候选融合
- Agent Memory / 长期记忆写入 / 历史案例相似度召回
- Agent Tool Calling / Tool Registry
- MCP Python SDK / FastMCP
- MCP Knowledge Hub Tools
- Retrieval Trace Observability
- RAG Grounding Evidence / Evidence Linking
- RAG Evaluation / hit@k / MRR / nDCG
- Agent Evaluation / Regression Report
- Agent Planner Evaluation / Plan Validation / Plan Repair
- Evaluation Report Persistence
- Plan Execution Audit / plan-vs-actual consistency
- 场景风险分析工具
- 请求链路追踪

## 目录结构

```text
.
├── agents.py              # 多个策略 Agent
├── agent_planner.py       # Agent 工具规划、计划校验和计划修复
├── api_fastapi.py         # 新版 FastAPI 服务入口
├── api_server.py          # 旧版 http.server 服务入口，保留兼容
├── decision_engine.py     # 决策编排、互评、评分和 LLM 增强
├── embedding_validation.py # Embedding Provider 验证与 dense probe
├── evaluation.py          # Agent Evaluation 场景集、指标检查和回归报告
├── grounding.py           # RAG 证据与 Agent 方案、风险建议的 grounding 关联
├── planner_evaluation.py  # Agent Planner Evaluation 工具计划评估报告
├── llm_coordinator.py     # LLM 调用与 JSON 解析
├── llm_strategy_agents.py # 5 个角色化 LLM Agent、结构化校验、并发与 fallback
├── main.py                # CLI 入口与预置场景
├── mcp_server.py          # 基于 FastMCP 的 MCP Server 工具入口
├── models.py              # 核心数据模型
├── schemas.py             # FastAPI/Pydantic 请求与响应模型
├── serializers.py         # API 响应序列化
├── standards.py           # 动态权重与评分标准
├── storage.py             # SQLite 历史记录存储
├── memory.py              # Agent Memory 历史案例召回
├── plan_execution_auditor.py # Planner 计划与实际工具调用一致性审计
├── trace.py               # 决策流程 Trace 事件模型
├── rag/                   # RAG 知识库与本地检索模块
├── tools/                 # Agent 工具注册与工具调用实现
├── frontend/              # 前端展示页面
└── tests/                 # pytest 测试
```

## 快速启动

安装依赖：

```bash
pip install -r requirements.txt
```

启动新版 FastAPI 服务：

```bash
uvicorn api_fastapi:app --reload --host 127.0.0.1 --port 8000
```

Windows 一键启动：

```powershell
.\scripts\start_server.ps1 -Reload
```

或：

```bat
scripts\start_server.bat
```

服务启动后可访问以下端点（请根据实际部署地址拼接）：

- 前端页面：`/`
- API 文档：`/docs`
- 健康检查：`/api/health`
- 历史记录：`/api/decisions`
- Agent Memory：`/api/memory`
- 评估报告历史：`/api/evaluations`

也可以继续使用旧版入口：

```bash
python api_server.py
```

命令行运行本地规则决策：

```bash
python main.py --llm-mode off --no-messages
```

运行默认 Agent Evaluation 评估集：

```bash
python evaluation.py
```

运行默认 Agent Planner Evaluation 评估集：

```bash
python planner_evaluation.py
```

运行默认 RAG Evaluation 评估集：

```bash
python rag_evaluation.py
```

构建或刷新 RAG 向量索引：

```bash
python scripts/build_rag_index.py
```

使用 Chroma 本地持久化向量库构建索引：

```bash
python scripts/build_rag_index.py --vector-store chroma --vector-db-path data/chroma_vectors
```

使用 Docker Chroma 服务构建索引：

```powershell
docker compose up -d chroma
python scripts/build_rag_index.py --vector-store chroma --chroma-mode http --chroma-host localhost --chroma-port 8001 --no-chroma-ssl --strict
```

验证 Embedding Provider 是否可用于真实语义向量检索：

```bash
python scripts/validate_embedding_provider.py --embedding-provider openai-compatible --embedding-model qwen3.7-text-embedding --embedding-api-key your_embedding_api_key --embedding-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --embedding-dimensions 1024
```

本地 fallback 只用于开发连通性探针，必须显式允许：

```bash
python scripts/validate_embedding_provider.py --embedding-provider local-hashing --embedding-model local-hashing-v1 --embedding-dimensions 128 --allow-local-fallback
```

启动 MCP Server：

```bash
python mcp_server.py
```

MCP Streamable HTTP 端点：

```text
/mcp
```

实际访问地址由 MCP Server 的部署域名和端口决定。

当前 MCP 工具包括：

- `knowledge_retrieval`：面向战场场景的 RAG 知识召回工具，返回 Query Rewrite、融合和重排证据。
- `memory_recall`：从本地 SQLite Agent Memory 中召回相似历史案例。
- `risk_analysis`：基于场景与上游 RAG/Memory 上下文输出风险分析。
- `query_knowledge_hub`：直接查询本地 RAG 知识库，不要求传入完整战场场景。
- `list_knowledge_collections`：查看当前知识集合、向量索引和 ingestion 状态。
- `get_retrieval_trace`：针对一次 query 返回检索阶段、RRF 融合和 rerank 证据，便于调试召回质量。

当前 MCP Resource 包括：

- `agent-tools://catalog`：导出 Agent ToolRegistry 的工具目录。
- `knowledge-hub://collections`：导出当前 RAG 知识集合与索引状态。

## LLM 配置

复制 `.env.example` 中的变量到本地环境变量，或在终端中设置：

```bash
set MESSAGE_TALK_API_KEY=your_api_key_here
set MESSAGE_TALK_MODEL=qwen3.7-plus
set MESSAGE_TALK_DB_PATH=data/decision_records.db
```

当前推荐模型组合：LLM Planner、5 个 Strategy Agent 和 Reviewer 使用 `qwen3.7-plus`，RAG Dense Retrieval 使用 `qwen3.7-text-embedding`。`damo`/通义实验室属于模型来源说明，不作为 API 调用时的 `model` 字段。

`llm_mode` 支持：

- `off`：5 个 Strategy Agent、Planner 和 Reviewer 都使用本地规则，不产生模型调用
- `auto`：并行调用 5 个 Strategy Agent，单个 Agent 失败时只降级该角色；Planner 和 Reviewer 保持各自 fallback
- `on`：强制要求 5 个 Agent 全部生成成功，任一失败即返回明确错误

一次完整在线决策最多调用 Qwen 7 次：1 次 Planner、5 次并行 Strategy Agent、1 次 Reviewer。并发度通过 `MESSAGE_TALK_AGENT_MAX_WORKERS` 配置，默认值和上限均为 5。

## 测试

```bash
pytest -q
```

最近一次完整离线回归：`141 passed`。

完整测试分层、Qwen live 验证和部署前检查见 `TESTING.md`。

当前测试覆盖：

- 动态权重归一化
- 本地规则排序
- LLM 返回 JSON 容错解析
- FastAPI 健康检查
- 场景列表接口
- 决策接口成功返回
- 非法参数校验
- 决策 Trace 步骤与 API 返回结构
- SQLite 历史记录保存与查询

- Agent Tool Calling 工具注册、风险分析与 API 返回结构
- Agent Evaluation 场景集、指标检查、API 报告与失败用例解释
- Agent Planner Evaluation 工具选择评估、计划修复和 CLI JSON 报告
- Planner 执行审计、计划/实际工具调用一致性和 fallback 追踪
- RAG Grounding Evidence 与 Evaluation 报告持久化
## 历史记录

系统会在 `/api/decide` 成功完成后，将本次决策输入和输出保存到本地 SQLite 数据库。

默认数据库路径：

```text
data/decision_records.db
```

历史记录接口：

```text
GET /api/decisions
GET /api/decisions/{record_id}
GET /api/memory
GET /api/evaluations
GET /api/evaluations/{report_id}
```

前端页面底部提供：

- 决策 Trace 时间线
- 历史记录列表
- 点击历史记录回看完整决策结果

## 流式决策

除普通决策接口外，系统还提供流式决策接口：

```text
POST /api/decide/stream
```

该接口使用 `text/event-stream` 返回：

- `progress`：阶段进度事件
- `result`：最终决策结果
- `done`：流式输出结束
- `error`：流式执行过程中的错误

前端默认优先调用流式接口，并在 Trace 时间线中实时展示阶段进度。

## 请求链路追踪

FastAPI 服务会为每一次 HTTP 请求维护一个 `request_id`：

- 如果调用方传入 `X-Request-ID`，服务会沿用该值。
- 如果调用方未传入，服务会自动生成一个请求 ID。
- 响应头会返回 `X-Request-ID`，方便前端、调用方和后端日志对齐。
- 响应头会返回 `X-Response-Time-Ms`，用于观察接口耗时。
- 参数校验错误、历史记录不存在、LLM 配置错误等错误响应体中也会包含 `request_id`。

这个能力主要用于 Docker 部署、接口联调和线上排查：当某次请求失败时，可以用响应里的 `request_id` 到后端日志中快速定位对应链路。

## RAG 知识增强

项目新增轻量级 RAG 知识检索模块：

```text
rag/
├── documents/              # 本地 Markdown 知识库
├── retriever.py            # BM25 风格关键词检索器
└── __init__.py
```

决策流程会在 Agent 生成候选方案前执行知识召回：

```text
输入场景
  -> 构造场景查询
  -> 检索 TopK 知识片段
  -> 写入 Decision Trace
  -> 注入 Agent 方案的 knowledge_sources
  -> API 返回 knowledge_context
```

当前 RAG 第一版使用本地 Markdown 文档和 BM25 风格关键词检索，不依赖外部向量库。后续可以继续升级为 Embedding 向量检索、Hybrid Search 和 Rerank。

第二十七轮优化后，RAG 检索流程增加 Query Rewrite 和 Rerank：
- `KnowledgeRetriever.rewrite_scene_query()` 会根据场景地形、平民密度、时效压力、情报质量、补给和敌我压力生成查询扩展词。
- `retrieve_for_scene_with_trace()` 会先扩大 BM25 候选召回，再根据场景信号对候选知识片段进行 rerank。
- `KnowledgeRetrievalTool` 会在工具 metadata 中返回 `query_rewrite`、`candidates_considered` 和 `rerank_evidence`。
- `retrieve_knowledge` Trace 会记录检索扩展词、候选数量和重排证据，便于解释 RAG 为什么召回这些知识片段。

这一轮让 RAG 从“直接关键词检索”升级为“查询重写 -> 候选召回 -> 场景相关性重排 -> 证据追踪”的检索流水线。

第三十一轮优化后，RAG 检索链路参考 Modular RAG MCP Server 的 Query Pipeline 思路进一步模块化：
- `retrieve_for_scene_with_trace()` 会记录 `query_processing`、`sparse_retrieval`、`scene_signal_retrieval`、`fusion`、`rerank` 五个阶段。
- 候选召回拆成 `bm25` 与 `scene_signal` 两条本地可解释路线，当前不伪装成真实向量检索，后续可把 `scene_signal` 替换为 Embedding Dense Retriever。
- `fusion` 阶段使用 RRF（Reciprocal Rank Fusion）融合多路候选排名，避免直接混用不同路线的原始分数。
- `KnowledgeRetrievalTool` 会在 metadata 中返回 `fusion_evidence` 与 `retrieval_trace`，面试时可以解释“召回了什么、怎么融合、为什么重排”。

第三十二轮优化后，RAG 增加 Embedding 与 VectorStore 可插拔骨架：
- `rag/embeddings.py` 定义 `EmbeddingProvider` 抽象，默认提供 `local-hashing` 本地确定性 embedding fallback，并预留 `openai-compatible` provider。
- `rag/vector_store.py` 定义 `InMemoryVectorStore`，用于把知识片段写入本地内存向量索引并执行余弦相似度检索。
- `retrieve_for_scene_with_trace()` 新增 `dense_retrieval` 阶段，当前默认路线为 `embedding_dense` + `local-hashing`，用于本地开发和测试；配置真实 embedding 模型后可升级为语义 Dense Retrieval。
- RRF 融合路线升级为 `bm25`、`embedding_dense`、`scene_signal` 三路候选融合。
- `.env.example` 新增 `MESSAGE_TALK_EMBEDDING_PROVIDER`、`MESSAGE_TALK_EMBEDDING_MODEL`、`MESSAGE_TALK_VECTOR_STORE`、`MESSAGE_TALK_RAG_DENSE_ENABLED` 等配置项。

需要注意：默认 `local-hashing` 是本地确定性向量 fallback，不等同于真实语义 embedding 模型。简历中只有在配置并跑通真实 embedding provider 后，才建议写“Dense Embedding 向量检索”。

第三十三轮优化后，`openai-compatible` embedding provider 进入生产化接入：
- 不再依赖简单封装，而是直接调用 OpenAI-compatible `/embeddings` HTTP 接口。
- Provider 支持 `timeout`、`batch_size`、`max_retries`、指数退避、响应数量校验和向量维度校验。
- `EmbeddingProvider.health_check()` 可用于检查 provider 是否可用，并返回 provider、model、dimensions、latency 和错误信息。
- `dense_retrieval` Trace 会返回 provider、model、dimensions、是否语义 embedding、batch_size、max_retries 和 vector_store，方便排查是否真的走了语义向量路线。
- 生产部署建议设置 `MESSAGE_TALK_EMBEDDING_PROVIDER=openai-compatible`、真实 embedding model、真实 API Key，并将 `MESSAGE_TALK_RAG_STRICT_EMBEDDING=true`，避免 embedding 初始化失败后静默降级。

真实 OpenAI-compatible embedding 配置示例：

```bash
set MESSAGE_TALK_EMBEDDING_PROVIDER=openai-compatible
set MESSAGE_TALK_EMBEDDING_MODEL=qwen3.7-text-embedding
set MESSAGE_TALK_EMBEDDING_API_KEY=your_embedding_api_key
set MESSAGE_TALK_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
set MESSAGE_TALK_EMBEDDING_DIMENSIONS=1024
set MESSAGE_TALK_EMBEDDING_TIMEOUT=30
set MESSAGE_TALK_EMBEDDING_BATCH_SIZE=8
set MESSAGE_TALK_EMBEDDING_MAX_RETRIES=2
set MESSAGE_TALK_RAG_STRICT_EMBEDDING=true
```

如果本机已经配置 `DASHSCOPE_API_KEY`，且没有单独设置 `MESSAGE_TALK_EMBEDDING_API_KEY`，项目会自动复用 `DASHSCOPE_API_KEY` 作为 embedding key。`qwen3.7-text-embedding` 在当前 DashScope OpenAI-compatible 接口下已通过 live 验证，返回向量维度为 `1024`。

第三十八轮优化后，项目新增 Embedding Provider 验证入口：
- `embedding_validation.py` 会先执行 `health_check()`，再用固定样本文本调用 `embed()`，检查向量数量、非空向量、维度一致性和 provider 语义标记。
- 验证流程内置 dense probe：把 3 条小型知识片段写入 `InMemoryVectorStore`，用查询向量执行 cosine similarity 检索，并检查预期知识片段是否排在 Top1。
- `scripts/validate_embedding_provider.py` 提供命令行验证入口，支持覆盖 provider、model、API Key、base URL、dimensions、timeout、batch size 和 retry 配置。
- 默认要求 `provider.is_semantic=True`，因此 `local-hashing` 会被判定为不满足真实语义检索要求；只有加 `--allow-local-fallback` 时才允许作为本地开发探针通过。
- 推荐上线前流程：先配置真实 OpenAI-compatible embedding 环境变量，再运行 `validate_embedding_provider.py`，验证通过后执行 `build_rag_index.py` 刷新索引，最后运行 `rag_evaluation.py` 观察检索质量。

使用当前免费 Qwen embedding 模型构建独立 SQLite 语义索引：

```bash
python scripts/build_rag_index.py --embedding-provider openai-compatible --embedding-model qwen3.7-text-embedding --embedding-api-key your_embedding_api_key --embedding-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --embedding-dimensions 1024 --vector-store sqlite --vector-db-path data/rag_qwen_vectors.db --collection tactical_knowledge_qwen_free --strict
```

运行服务时切到这份语义索引：

```bash
set MESSAGE_TALK_EMBEDDING_PROVIDER=openai-compatible
set MESSAGE_TALK_EMBEDDING_MODEL=qwen3.7-text-embedding
set MESSAGE_TALK_EMBEDDING_DIMENSIONS=1024
set MESSAGE_TALK_VECTOR_STORE=sqlite
set MESSAGE_TALK_VECTOR_DB_PATH=data/rag_qwen_vectors.db
set MESSAGE_TALK_VECTOR_COLLECTION=tactical_knowledge_qwen_free
set MESSAGE_TALK_RAG_STRICT_EMBEDDING=true
```

第三十四轮优化后，RAG 向量索引从启动时临时内存索引升级为 SQLite 持久化 VectorStore：
- `rag/vector_store.py` 新增 `SQLiteVectorStore`，默认数据库路径为 `data/rag_vectors.db`。
- 向量表按 `collection` 隔离，记录文档 ID、source、title、content、content hash、embedding provider、embedding model、dimensions、vector 和更新时间。
- `upsert_documents()` 支持幂等写入：内容、provider、model、dimensions 未变化时跳过重新 embedding；知识库删除文档后会删除 stale vector。
- `scripts/build_rag_index.py` 提供显式索引构建命令，并输出 JSON 格式的文档数量、embedding provider、health、upsert/skip/delete 统计和 vector store 状态。
- Docker 默认使用 `/app/data/rag_vectors.db`，并通过 `./data:/app/data` 挂载持久化。

SQLite 持久化向量库配置示例：

```bash
set MESSAGE_TALK_VECTOR_STORE=sqlite
set MESSAGE_TALK_VECTOR_DB_PATH=data/rag_vectors.db
set MESSAGE_TALK_VECTOR_COLLECTION=tactical_knowledge
```

第三十九轮优化后，RAG VectorStore 增加 Chroma 后端：
- `rag/vector_store.py` 新增 `ChromaVectorStore`，使用 Chroma `PersistentClient` 将 collection 持久化到本地目录。
- Chroma 后端复用项目已有 `EmbeddingProvider`，写入的是 `embed_texts()` 生成的向量，不依赖 Chroma 默认 embedding function，便于统一切换 `local-hashing` 或真实 OpenAI-compatible embedding。
- upsert 时会记录 source、title、content_hash、metadata_json、embedding provider、embedding model 和 dimensions，用于幂等跳过未变更文档。
- search 时通过 Chroma 的 metadata `where` 条件限制 provider/model/dimensions，避免不同 embedding 模型生成的向量混在一起参与召回。
- 支持 `replace_collection=True` 删除 stale document，知识库删除或 chunk 变化后不会继续召回旧向量。
- `KnowledgeRetriever.default()` 和 `scripts/build_rag_index.py` 均支持 `MESSAGE_TALK_VECTOR_STORE=chroma` 或 `--vector-store chroma`。

Chroma 本地持久化配置示例：

```bash
set MESSAGE_TALK_VECTOR_STORE=chroma
set MESSAGE_TALK_VECTOR_DB_PATH=data/chroma_vectors
set MESSAGE_TALK_VECTOR_COLLECTION=tactical_knowledge
```

当前推荐的 Chroma HTTP 服务配置：

```powershell
$env:MESSAGE_TALK_VECTOR_STORE = "chroma"
$env:MESSAGE_TALK_VECTOR_COLLECTION = "tactical_knowledge_qwen_free"
$env:MESSAGE_TALK_CHROMA_MODE = "http"
$env:MESSAGE_TALK_CHROMA_HOST = "localhost"
$env:MESSAGE_TALK_CHROMA_PORT = "8001"
$env:MESSAGE_TALK_CHROMA_SSL = "false"
```

Chroma Server 使用 `chromadb/chroma:1.5.9`。主机连接地址由 `MESSAGE_TALK_CHROMA_HOST` 和 `MESSAGE_TALK_CHROMA_PORT` 配置；Compose 内的 FastAPI 服务通过 `chroma:8000` 连接。持久化目录由 `docker-compose.yml` 的 volume 配置决定，容器重建后 collection 和向量仍然保留。`ChromaVectorStore` 会在初始化时执行 heartbeat，并在 Trace 中记录 `chroma_mode`、endpoint、collection、embedding provider 和 model。

第三十五轮优化后，RAG 增加轻量 Ingestion Pipeline：
- `rag/ingestion.py` 新增 `MarkdownIngestionPipeline`，将知识库摄取拆成 Markdown Loader、section splitter、chunk splitter、metadata extraction 和 history write。
- 每个 Markdown 文件会计算 SHA256 file hash，并写入 `rag_ingestion_history` 表，默认路径为 `data/rag_ingestion.db`。
- 每个 chunk 会记录 document title、section title、source path、file hash、tags、chunk index、chunk size 和 collection。
- `KnowledgeRetriever.from_directory()` 统一走 Ingestion Pipeline，再转换为 `KnowledgeDocument`，避免 Retriever、索引脚本各写一套 Markdown 解析逻辑。
- `scripts/build_rag_index.py` 输出中新增 `ingestion` 报告，包括 files_total、files_processed、files_unchanged、files_failed 和 chunks_total。
- `dense_retrieval` Trace 会透出 ingestion 报告，便于排查当前 RAG 检索基于哪批知识 chunk。

Ingestion 配置示例：

```bash
set MESSAGE_TALK_INGESTION_HISTORY_DB_PATH=data/rag_ingestion.db
set MESSAGE_TALK_RAG_CHUNK_SIZE=900
set MESSAGE_TALK_RAG_CHUNK_OVERLAP=120
```

第三十六轮优化后，RAG 检索能力进一步通过 MCP Knowledge Hub 工具暴露：
- `KnowledgeRetriever.retrieve_query_with_trace()` 支持直接 query 检索，不再只能依赖 `BattlefieldScene` 构造查询。
- direct query 会复用同一套 `sparse_retrieval -> dense_retrieval -> fusion -> rerank` 流水线，输出 `fusion_evidence`、`rerank_evidence` 和 `retrieval_trace`。
- 场景检索仍保留 `scene_signal_retrieval` 与 `scene_signal_boost`；普通 query 则使用 `query_score_boost`，避免把战场场景信号硬套到普通知识库查询里。
- MCP Server 新增 `query_knowledge_hub`、`list_knowledge_collections`、`get_retrieval_trace`，让外部 Agent 客户端能独立查询知识库、查看 collection 状态和调试检索链路。

第四十二轮优化后，RAG 证据进一步升级为 Grounding Evidence：
- 新增 `GroundingBuilder`，将 `knowledge_context` 中的知识片段转换为带 `evidence_id` 的结构化证据。
- `proposal_grounding` 会记录每个 Agent 方案引用了哪些 RAG 证据，避免只返回“参考过知识库”这种模糊信息。
- `risk_grounding` 会把风险分析建议与 RAG evidence 绑定，说明风险建议依据了哪些知识片段。
- LangGraph 新增 `build_grounding_evidence` 业务节点，位于 `generate_proposals` 之后、`run_dialogue` 之前。
- API 响应新增 `grounding_evidence`，历史决策记录也会保存这份证据绑定报告。
- Agent Evaluation 对需要 RAG 的场景新增 grounding 检查，确保 RAG 证据不仅被召回，也被真正链接到决策输出。

这一轮让项目从“RAG 召回可解释”进一步升级为“决策输出可溯源到 RAG 证据”，更符合 AI 应用里 grounded answer / evidence attribution 的工程要求。

## Agent Memory 长期记忆

项目将 SQLite 历史决策记录进一步升级为 Agent 可使用的长期记忆：

```text
决策完成
  -> 保存完整历史记录 decision_records
  -> 根据写入策略生成 agent_memory_entries
  -> 记录 summary / lessons / tags / importance_score

下一次相似场景
  -> 优先从 agent_memory_entries 召回摘要记忆
  -> 按地形、天气、敌我强度、补给、情报、紧急度、平民密度计算相似度
  -> 召回 TopK 相似长期记忆
  -> 写入 Decision Trace
  -> 注入 Agent 方案的 memory_sources
  -> API 返回 memory_context
```

第三十轮优化后，Memory 新增写入策略与摘要记忆：
- `DecisionMemory.write_decision()` 会在决策保存后生成结构化记忆条目。
- 写入策略会综合最终分数、风险分数、审查发现数量、工具调用数量和 Trace 完整性计算 `importance_score`。
- 每条长期记忆包含 `summary`、`lessons`、`tags`、`risk_level`、`importance_score` 和关联的历史记录 ID。
- `DecisionMemory.recall()` 会优先从 `agent_memory_entries` 召回摘要记忆；如果没有摘要记忆，则回退到旧的完整历史记录召回。
- 新增 `GET /api/memory`，用于查看当前长期记忆条目。

`memory_context` 会返回历史记录 ID、长期记忆 ID、历史场景名、历史最优 Agent、历史最优策略、相似度、匹配特征、摘要、经验要点、标签和重要性分数。这样 Memory 不只是“查历史记录”，而是能沉淀可复用的经验。

## Agent Tool Calling 工具调用

项目新增轻量级 Agent 工具调用层，把 RAG、Memory 和风险分析统一包装为可注册、可追踪的工具：

```text
DecisionEngine
  -> RuleBasedToolPlanner
  -> tool_plan
  -> ToolRegistry
  -> knowledge_retrieval / memory_recall / risk_analysis
  -> ToolResult
  -> Decision Trace / API Response / Frontend Tool Calls
```

当前工具包括：
- `knowledge_retrieval`：调用本地 RAG 检索，返回场景相关知识片段。
- `memory_recall`：调用 Agent Memory，返回相似历史决策案例。
- `risk_analysis`：根据敌我强度、平民密度、情报质量、补给、时效和地形生成风险等级、风险因子和建议。

每次工具调用都会返回 `tool_name`、`status`、`output`、`metadata` 和 `duration_ms`。这些数据会写入 `tool_calls` 字段，并在前端 “Tool Calls” 面板中展示。这样项目不只是“后端函数调用”，而是具备 Agent 工具编排、执行轨迹和可观察性的基础结构。

第十七轮优化后，工具调用前会先生成 `tool_plan`：
- `RuleBasedToolPlanner` 根据场景时效压力、平民密度、情报质量、敌我强度和地形生成工具计划。
- `tool_plan.steps` 记录工具执行顺序、调用目的、参数和是否必需。
- `Decision Trace` 新增 `plan_tools` 阶段，SSE 流式输出会先展示规划，再展示工具执行。
- 前端 “Tool Calls” 面板上半部分展示计划，下半部分展示实际工具调用结果。

第十八轮优化后，决策流程先抽象为轻量状态图编排层：
- `workflow/decision_graph.py` 定义 `DecisionGraphState`、`DecisionGraphNode` 和 `DecisionGraphRunner`。
- `DecisionEngine` 不再在 `run_stream()` 中直接串联所有阶段，而是通过图节点逐步更新统一 State。
- API 响应新增 `workflow_nodes`，记录本次实际执行过的图节点路径。
- 当前节点路径为：`plan_tools -> retrieve_knowledge -> recall_memory -> analyze_risk -> audit_tool_plan_execution -> generate_proposals -> build_grounding_evidence -> run_dialogue -> build_weights -> llm_review -> score_proposals -> audit_decision -> finalize_decision`。
- 后续如果接入真正的 LangGraph，可以把这些节点平滑迁移为 LangGraph StateGraph 节点。

第十九轮优化后，工具调用具备可靠性策略：
- `ToolRegistry.run_with_policy()` 支持工具异常捕获、重试和 fallback 输出。
- `ToolExecutionPolicy` 可配置最大重试次数和慢调用阈值。
- API 响应新增 `tool_metrics`，统计工具总数、失败数、fallback 次数、慢调用次数和总耗时。
- `DecisionEngine` 在 RAG、Memory、Risk 工具失败时会使用默认输出继续完成决策，避免单个工具失败导致整体流程中断。
- 前端 “Tool Calls” 面板会展示工具执行可靠性指标。

第二十轮优化后，工具具备 Tool Schema 工具目录能力：
- `ToolSpec` 描述工具名、工具说明、输入 schema、输出 schema 和标签。
- `KnowledgeRetrievalTool`、`MemoryRecallTool`、`RiskAnalysisTool` 都实现 `describe()`。
- `ToolRegistry.specs()` 可以导出当前注册工具目录。
- 新增 `GET /api/tools`，用于查看当前 Agent 可用工具及其 schema。
- 这为真实 MCP Server、外部 API 工具、权限控制和自动工具选择打基础。

第二十一轮优化后，Agent 工具编排具备条件分支能力：
- `RuleBasedToolPlanner` 会根据情报质量、平民密度、时效压力、地形、敌我强度和补给水平选择工具。
- `tool_plan.steps` 只记录本轮真正需要执行的工具。
- `tool_plan.skipped_steps` 记录被跳过的工具、跳过原因和触发条件。
- `DecisionGraph` 的工具节点支持 `status=skipped` 的 Trace 事件，用于解释为什么没有调用某个工具。
- 高压城市场景仍会执行 RAG、Memory、Risk；低压平原场景会跳过 RAG 和 Memory，仅保留必要的风险分析。

这使项目从“固定调用所有工具”升级为“基于工具 schema 发现工具，再通过条件节点选择工具”，更接近真实 Agent Workflow。

第二十二轮优化后，条件分支进一步升级为图级路由与工具选择评分：
- `ToolPlanStep` 和 `SkippedToolStep` 新增 `need_score` 与 `threshold`，用于解释工具为什么被调用或跳过。
- `RuleBasedToolPlanner` 不再只做布尔判断，而是分别计算 RAG、Memory、Risk 的工具需求分。
- `DecisionGraphNode` 支持 `condition` 与 `on_skip`，工具节点的执行/跳过由图 Runner 决定。
- `DecisionGraphRunner` 在条件不满足时触发 skip hook，仍保留节点路径与 Trace 解释。
- `retrieve_knowledge`、`recall_memory`、`analyze_risk` 三个工具节点已经迁移到图级条件路由。

这一轮让项目更接近真实 LangGraph 的思想：节点是否执行由图状态和条件边控制，工具是否调用由评分后的工具计划决定。

第二十三轮优化后，工具规划支持 LLM Planner 与本地规则兜底：
- `llm_coordinator.py` 新增工具规划专用 Prompt，模型会基于场景、`/api/tools` 工具目录和本地评分参考生成工具调用计划。
- `ToolPlan` 新增 `planner_source`、`planner_model` 和 `planner_error`，用于解释工具计划来自 LLM 还是本地规则。
- `DecisionEngine` 在 `llm_mode=auto/on` 时优先尝试 LLM Planner；当无 API Key、模型调用失败或模型输出非法时，自动回退到本地评分 Planner。
- LLM 输出会经过本地校验：未知工具会被忽略，`top_k` 会被限制在 1-6，`risk_analysis` 不接受额外参数。
- `plan_tools` Trace 会记录规划来源、模型名和 fallback 错误原因。

这让项目形成了更完整的 Agent 工具规划闭环：`ToolSpec -> LLM Planner -> Plan 校验 -> Conditional Graph -> Tool Execution -> Trace`。

第二十四轮优化后，工具链支持依赖 DAG 与上下文感知风险分析：
- `risk_analysis` 不再只读取原始场景参数，还可以接收 `knowledge_context` 和 `memory_context`。
- `DecisionEngine` 会把 `knowledge_retrieval` 和 `memory_recall` 的输出注入到 `risk_analysis`，形成 `RAG / Memory -> Risk Analysis` 的工具依赖链。
- `risk_context` 新增 `context_evidence`，记录使用了哪些知识片段、历史案例、上下文信号和风险修正分。
- `analyze_risk` Trace 新增 `depends_on`、`knowledge_context_count`、`memory_context_count`，用于解释风险分析依赖了哪些上游工具。
- `RiskAnalysisTool.describe()` 的 Tool Schema 也声明了可选的 `knowledge_context` 和 `memory_context` 入参。

这一轮让工具调用从“并列执行”升级为“上游工具结果影响下游工具判断”，更接近真实 Agent DAG 工作流。

第二十五轮优化后，决策流程新增 Reflection / Critic 审查节点：
- 新增 `decision_auditor.py`，提供 `RuleBasedDecisionAuditor`。
- 状态图在 `score_proposals` 之后、`finalize_decision` 之前新增 `audit_decision` 节点。
- 审查器会检查最终推荐方案是否存在高风险低控制、平民安全缺口、情报匹配不足、上下文风险放大、置信度偏低等问题。
- API 响应新增 `decision_audit`，返回 `overall_status`、`findings`、`evidence_summary` 等结构化审查结果。
- `Decision Trace` 新增 `audit_decision` 事件，记录审查状态和发现数量。

这一轮让项目从“算出最优方案”升级为“对最优方案进行二次审查”，更贴近 Self-Reflection / Critic Agent 的工作流。

第二十六轮优化后，工作流编排接入真实 LangGraph：
- `requirements.txt` 新增 `langgraph` 依赖。
- `workflow/decision_graph.py` 的 `DecisionGraphRunner` 改为基于 `langgraph.graph.StateGraph` 编译和执行。
- 每个业务节点会映射为 LangGraph router/run/skip 节点，条件工具节点通过 `add_conditional_edges` 路由到执行分支或跳过分支。
- 原有 `DecisionGraphState`、`DecisionGraphNode` 和 `DecisionEngine` 调用方式保持兼容，避免大面积重写业务逻辑。
- API 返回的 `workflow_nodes` 和 `Decision Trace` 仍然记录业务节点路径，不暴露内部 router 节点。

这一轮把之前的自定义状态图执行器替换为真实 LangGraph StateGraph，项目可以更专业地表述为：使用 LangGraph 编排 Agent 工作流。

第二十八轮优化后，项目新增真实 MCP Server：
- `requirements.txt` 新增 `mcp[cli]>=1.28,<2`，使用官方 MCP Python SDK v1 稳定线。
- 新增 `mcp_server.py`，通过 `FastMCP` 将现有 `ToolRegistry` 暴露为 MCP 工具入口。
- MCP tools 包括：
  - `knowledge_retrieval`：对当前场景执行 RAG Query Rewrite、候选召回和 Rerank。
  - `memory_recall`：从本地 SQLite Agent Memory 召回相似历史案例。
  - `risk_analysis`：执行风险分析，并可接收上游 RAG/Memory 上下文。
- MCP resource `agent-tools://catalog` 会返回当前工具目录，便于 MCP 客户端发现工具说明和 schema。
- `call_agent_tool()` 统一负责场景入参校验、`top_k` 限制、上下文反序列化和 `ToolResult` 序列化，避免 MCP 入口和 FastAPI 入口各写一套业务逻辑。

这一轮后，项目可以更专业地表述为：FastAPI 面向普通 Web/API 调用，MCP Server 面向 LLM Agent 客户端调用；两者复用同一套 RAG、Memory、Risk 工具实现。

第三十六轮优化后，MCP Server 从“只暴露 Agent 执行工具”扩展为“Agent 工具 + 知识库工具”：
- 新增 `query_knowledge_hub`，允许 MCP 客户端直接输入自然语言 query 查询 RAG 知识库。
- 新增 `list_knowledge_collections`，返回 collection 名称、文档数量、embedding provider、vector store stats、vector index upsert 统计和 ingestion 报告。
- 新增 `get_retrieval_trace`，只返回 Query Rewrite、候选融合、重排证据和阶段耗时，不返回完整知识片段正文，适合调试检索质量。
- 新增 MCP resource `knowledge-hub://collections`，让 MCP 客户端可以像读取资源一样查看知识库状态。
- 这些工具复用 `KnowledgeRetrievalTool` 背后的同一个 `KnowledgeRetriever`，避免 MCP Server 内部初始化多套索引。

第四十轮优化后，工具规划新增 Plan Validation 与 Plan Repair 闭环：
- `PlanValidator` 会在工具计划进入 LangGraph 执行前统一校验 `AgentToolPlan`，防止 LLM Planner 输出未知工具、重复工具、非法参数或不符合依赖顺序的计划。
- 计划修复包括删除未注册工具、删除重复工具、清洗 `top_k` 参数、补回本地 fallback planner 判定为必需的工具，并按 `knowledge_retrieval -> memory_recall -> risk_analysis` 的依赖顺序重新编号。
- `DecisionEngine._plan_tools()` 会先生成 rule-based fallback plan，再接收 LLM Planner 原始计划，最后用 `PlanValidator` 产出可执行计划；后续图节点只消费修复后的 plan。
- `tool_plan` API 字段新增 `validation_status`、`validation_issues` 和 `repair_actions`，`plan_tools` Trace metadata 新增 `plan_validation`，用于解释计划为什么被修复。
- 新增 `planner_evaluation.py`，专门评估 Planner 在不同场景下的工具选择是否符合预期、修复次数是否在阈值内、修复后执行顺序是否满足工具依赖。

这一轮让项目从“能调用 LLM 生成工具计划”升级为“LLM 计划可评估、可修复、可追踪”，更接近生产 Agent 系统里常见的 planner guardrail。

第四十一轮优化后，工具规划新增执行后审计闭环：
- 新增 `PlanExecutionAuditor`，在工具节点执行完成后对比 `planned_tools` 与 `actual_tools`。
- 审计报告会统计 `missing_tools`、`unexpected_tools`、`failed_tools`、`fallback_tools` 和 `sequence_match`。
- LangGraph 新增 `audit_tool_plan_execution` 业务节点，位置在工具执行完成后、Agent 生成方案前。
- API 响应新增 `plan_execution_audit`，Trace metadata 同步记录 `plan_execution_audit`。
- 当计划与实际调用完全一致且工具无失败时，状态为 `passed`；当工具失败或 fallback 但计划顺序仍一致时，状态为 `attention_required`；当实际执行偏离计划时，状态为 `drift_detected`。

这一轮让 Planner 从“执行前修复”继续升级为“执行前修复 + 执行后审计”。面试时可以讲成：`LLM Planner -> PlanValidator -> LangGraph Tool Execution -> PlanExecutionAuditor -> Trace`。

## Agent Evaluation 评估

第二十九轮优化后，项目新增 Agent Evaluation 评估层，用于衡量当前 Agent 工作流是否稳定：

```text
evaluation.py
  -> build_default_evaluation_cases()
  -> AgentEvaluator
  -> DecisionEngine(llm_mode=off)
  -> EvaluationSummary
```

默认评估集包含 3 类场景：
- `urban_high_pressure`：高时效、低情报、平民密集城市场景，要求执行 RAG、Memory、Risk，并检查 RAG Query Rewrite 与 Rerank 证据。
- `mountain_enemy_pressure`：山地敌压场景，要求执行 Memory 和 Risk，验证条件工具选择是否符合预期。
- `plain_low_context_need`：低上下文需求平原场景，要求跳过 RAG 和 Memory，只保留 Risk，验证工具不会被无效调用。

评估指标包括：
- 工具调用计划是否符合预期。
- Trace 是否包含完整决策节点。
- LangGraph 工作流是否正常走到 `finalize_decision`。
- 工具调用是否无失败和 fallback。
- 风险等级是否落在允许范围内。
- 最终方案分数是否超过最低阈值。
- Decision Audit 状态是否可接受。
- 对需要 RAG 的场景，额外检查 `query_rewrite`、必要扩展词和 `rerank_evidence`。

运行方式：

```bash
python evaluation.py
```

API 方式：

```text
POST /api/evaluations/run
POST /api/evaluations/planner/run
POST /api/evaluations/rag/run
GET /api/evaluations
GET /api/evaluations/{report_id}
```

评估接口会把报告保存到 SQLite 的 `evaluation_reports` 表，不写入 `/api/decisions` 决策历史表。当前 Agent 默认评估结果为 `3/3 passed`，平均分 `100.0`。

第四十三轮优化后，Evaluation 报告支持历史持久化：
- `POST /api/evaluations/run` 运行 Agent Evaluation，并保存 `report_type=agent` 的报告。
- `POST /api/evaluations/planner/run` 运行 Planner Evaluation，并保存 `report_type=planner` 的报告。
- `POST /api/evaluations/rag/run` 运行 RAG Evaluation，并保存 `report_type=rag` 的报告。
- `GET /api/evaluations` 返回评估报告摘要，支持按 `report_type` 过滤。
- `GET /api/evaluations/{report_id}` 返回完整评估报告 JSON。

这让 Evaluation 从“命令行跑一次”升级为“可回溯的质量报告历史”，更适合持续回归验证和项目演示。

## Agent Planner Evaluation 评估

第四十轮优化后，项目新增独立的 Agent Planner Evaluation，用于评估“工具规划”本身是否稳定：

```text
planner_evaluation.py
  -> build_default_planner_evaluation_cases()
  -> PlannerEvaluator
  -> RuleBasedToolPlanner / custom planner
  -> PlanValidator
  -> PlannerEvaluationSummary
```

默认评估集包含 3 类场景：
- `urban_high_context_need`：城市高压、低情报、平民密集场景，预期执行 RAG、Memory、Risk 三个工具。
- `mountain_memory_risk_need`：山地敌压场景，预期执行 Memory 和 Risk。
- `plain_low_context_need`：低上下文需求平原场景，预期只执行 Risk。

评估指标包括：
- 原始 Planner 选择的工具是否符合预期。
- 修复后的计划是否可执行。
- 修复次数是否超过用例阈值。
- 修复后的 sequence 是否连续。
- 已执行工具和 skipped tools 是否覆盖全部 available tools。
- 工具顺序是否满足 `knowledge_retrieval -> memory_recall -> risk_analysis` 的依赖约束。

运行方式：

```bash
python planner_evaluation.py
```

也可以只运行单个 Planner 评估用例：

```bash
python planner_evaluation.py --case-id urban_high_context_need
```

Planner Evaluation 只评估工具计划本身；Agent Evaluation 评估完整决策工作流；RAG Evaluation 评估知识库检索质量。三者边界分开后，项目更容易定位问题：是 Planner 选错工具、RAG 召回质量不稳，还是完整 Agent 决策链路出现回归。

## RAG Evaluation 评估

第三十七轮优化后，项目新增独立的 RAG 检索质量评估层，用于衡量知识库召回是否稳定：

```text
rag_evaluation.py
  -> build_default_rag_evaluation_cases()
  -> RAGEvaluator
  -> KnowledgeRetriever.retrieve_query_with_trace()
  -> RAGEvaluationSummary
```

默认评估集包含 30 条查询，分为 5 类：
- 8 条 `direct_`：直接主题检索。
- 7 条 `paraphrase_`：中文自然语言改写。
- 6 条 `compound_`：多条件复合查询。
- 5 条 `discrimination_`：相似主题区分查询。
- 4 条 `cross_`：跨文档关联查询。

评估指标包括：
- `hit_at_k`：TopK 是否命中预期知识片段。
- `mean_reciprocal_rank`：预期片段排名越靠前分数越高。
- `mean_ndcg`：衡量排序质量。
- `source_match_rate`：命中片段是否来自预期知识源。
- `average_rerank_improvement`：最终 rerank 相比 RRF 融合排名是否有提升。

运行方式：

```bash
python rag_evaluation.py
```

也可以只运行单个评估用例：

```bash
python rag_evaluation.py --case-id direct_urban_safety_zone
```

RAG Evaluation 只评估检索链路，不运行完整多智能体决策流程；Agent Evaluation 则评估工具规划、LangGraph 工作流、风险分析和最终决策质量。

当前知识库由 12 个主题 Markdown 文件组成，共 60 个标题感知语义 Chunk。
真实 Qwen + Chroma HTTP 评测结果为：30/30 通过、Hit@3=1.0、
MRR=0.9611、nDCG@3=0.9684、Source Match Rate=1.0。
作为对照，纯 BM25 在全部 30 条用例中通过 26 条，在 7 条语义改写题中只通过
4 条；真实语义向量路线通过全部质量门，并得到 `Rerank Improvement=0.0333`。

## Docker 部署

构建镜像：

```bash
docker build -t message-talk .
```

运行容器：

```bash
docker run --rm -p 8000:8000 -v "%cd%/data:/app/data" message-talk
```

使用 Docker Compose：

```bash
docker compose up -d chroma
docker compose up --build message-talk
```

服务端点与数据目录：

```text
FastAPI: /
FastAPI health: /api/health
Chroma heartbeat: /api/v2/heartbeat
Chroma data: 由 docker-compose.yml 的 volume 配置决定
```

检查服务状态时，请先设置实际部署地址：

```powershell
$apiBaseUrl = $env:MESSAGE_TALK_API_BASE_URL
$chromaBaseUrl = $env:MESSAGE_TALK_CHROMA_BASE_URL
docker compose ps
Invoke-RestMethod "$apiBaseUrl/api/health"
Invoke-RestMethod "$chromaBaseUrl/api/v2/heartbeat"
```

## 后续优化路线

1. 扩大 RAG Evaluation 数据集：增加中文自然语言查询、噪声文档、跨文件检索和 TopK 敏感性测试。
2. 深化 Memory：记忆质量评估、去重压缩、过期策略和召回排序优化。
3. 深化 Planner：在已有 plan-vs-actual audit 基础上，继续补充 planner self-reflection 和失败样例库。
4. 扩展 Agent Evaluation：更多对抗场景、失败样例库、评估报告对比分析和 CI 回归。
