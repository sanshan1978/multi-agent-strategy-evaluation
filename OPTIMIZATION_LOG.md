# 项目技术优化记录

本文档用于记录 `message_talk` 项目的每次技术优化内容，方便后续复盘、写简历、准备面试和继续迭代。

项目目标保持不变：**战场对抗多智能体决策展示系统**。以下优化均以不改变原有业务场景、Agent 策略和评分规则为前提。

## 2026-07-12 第一轮：新增 FastAPI 后端入口

### 改动内容

- 新增 `api_fastapi.py`，为项目增加 FastAPI 服务入口。
- 保留原有 `api_server.py`，旧版 `http.server` 入口仍可继续使用。
- 新增 `schemas.py`，使用 Pydantic 定义请求体、响应体和健康检查模型。
- FastAPI 新增接口：
  - `GET /api/health`
  - `GET /api/scenarios`
  - `POST /api/decide`
- 新增静态资源托管能力，访问 `/` 可打开原有前端页面。
- 新增 `/docs` 自动接口文档。

### 使用技术

- FastAPI
- Pydantic
- StaticFiles
- FileResponse
- OpenAPI 自动文档

### 优化价值

- 将原有 Python 决策引擎包装成标准 Web API。
- 接口具备自动文档和参数校验能力。
- 为后续日志、异常处理、测试、部署打下基础。

## 2026-07-12 第二轮：补充测试体系

### 改动内容

- 新增 `tests/conftest.py`，保证 pytest 能稳定导入项目根目录模块。
- 新增 `tests/test_decision_engine.py`，覆盖核心决策逻辑。
- 新增 `tests/test_api_fastapi.py`，覆盖 FastAPI 接口。
- 测试内容包括：
  - 动态权重归一化
  - 本地规则模式排序
  - LLM JSON 容错解析
  - 健康检查接口
  - 场景列表接口
  - 决策接口
  - 非法参数校验

### 使用技术

- pytest
- FastAPI TestClient
- 回归测试

### 优化价值

- 项目从“能运行”提升到“可验证”。
- 后续继续优化时，可以用测试保护原有行为不被破坏。

## 2026-07-12 第三轮：补充工程化文件

### 改动内容

- 新增 `.gitignore`，忽略虚拟环境、缓存、IDE 配置和日志文件。
- 新增 `.env.example`，给出模型 API Key、Base URL、模型名称、超时时间配置示例。
- 更新 `requirements.txt`，补充 FastAPI、Uvicorn、Pydantic、pytest、httpx 等依赖。
- 新增 `README.md`，说明项目定位、技术栈、目录结构、启动方式、LLM 配置和测试方式。

### 使用技术/工程实践

- 环境变量模板
- Git 忽略规则
- README 项目文档
- Python 依赖声明

### 优化价值

- 项目更容易被别人启动、测试和理解。
- 更适合放入简历、作品集或 GitHub 仓库展示。

## 2026-07-12 第四轮：抽离序列化逻辑

### 改动内容

- 新增 `serializers.py`。
- 将 `scene_to_dict`、`proposal_to_dict`、`scored_to_dict`、`message_to_dict`、`result_to_dict` 从 `api_server.py` 抽离出来。
- 修改 `api_fastapi.py` 和 `api_server.py`，让新旧两个 API 入口共用同一套序列化逻辑。
- 新增 `tests/test_serializers.py`，保护前端依赖的 JSON 字段结构。

### 使用技术/工程实践

- 模块解耦
- 单一职责原则
- API 数据契约测试

### 优化价值

- API 层只负责请求响应，序列化模块只负责对象转 JSON。
- 避免新版 FastAPI 入口反向依赖旧版 `http.server` 文件。
- 降低重复代码，方便后续维护。

## 2026-07-13 第五轮：FastAPI 接口文档中文化

### 改动内容

- 修改 `api_fastapi.py`，补充中文 API 标题、系统描述和接口分组。
- 为接口增加中文 `summary` 和 `description`。
- 修改 `schemas.py`，为 Pydantic 字段增加中文 `description`。
- `/docs` 中可查看中文接口说明、请求字段说明和响应字段说明。

### 使用技术

- FastAPI `title`
- FastAPI `description`
- FastAPI `openapi_tags`
- 路由级 `summary`
- 路由级 `description`
- Pydantic `Field(description=...)`

### 优化价值

- 接口文档更适合中文项目展示。
- 面试或演示时可以直接打开 `/docs` 说明接口功能。

## 2026-07-13 第六轮：配置、日志与错误结构优化

### 改动内容

- 新增 `settings.py`，集中管理服务名、版本号、模型 API Key、Base URL、模型名称、超时时间和日志级别。
- 调整 `llm_coordinator.py`，将原本分散的环境变量读取逻辑迁移到 `settings.py`。
- 新增 `logging_config.py`，统一项目日志格式和日志级别。
- 调整 `api_fastapi.py`，接入接口请求日志、决策完成日志和运行错误日志。
- 调整 `llm_coordinator.py`，接入 LLM 启用、缺少密钥、调用失败、非 JSON 返回等日志。
- 调整 `api_fastapi.py`，新增 FastAPI 异常处理器，统一 HTTP 错误和参数校验错误的 JSON 返回格式。
- 调整 `schemas.py`，为错误响应增加可选 `details` 字段。
- 新增 `tests/test_settings.py`，覆盖默认配置读取和模型覆盖逻辑。
- 扩展 `tests/test_api_fastapi.py`，覆盖健康检查版本返回、参数校验错误结构和强制 LLM 模式缺少密钥时的错误结构。

### 使用技术

- Python `dataclass`
- 环境变量配置管理
- Python `logging`
- FastAPI exception handler
- FastAPI `RequestValidationError`
- pytest

### 优化价值

- 配置读取更集中，后续换模型、改超时时间、改日志级别更方便。
- 接口错误返回结构更稳定，前端和测试都更容易处理。
- 日志能帮助排查请求、决策、LLM 降级和模型调用失败问题。

## 2026-07-13 第七轮：决策 Trace 记录优化

### 改动内容

- 将项目定位统一为“面向复杂对抗场景的多智能体策略评估系统”。
- 新增 `trace.py`，定义 `TraceEvent`，用于记录决策流程中的关键步骤。
- 调整 `decision_engine.py`，在不改变 Agent 策略和评分规则的前提下，为 `DecisionEngine.run()` 增加流程追踪记录。
- 当前 Trace 记录步骤包括：
  - `start`：开始执行多智能体策略评估。
  - `generate_proposals`：多个策略智能体生成候选方案。
  - `run_dialogue`：执行智能体互评。
  - `build_weights`：根据场景参数生成动态评价权重。
  - `llm_review`：记录 LLM 裁决、跳过或失败回退状态。
  - `score_proposals`：完成候选方案综合评分与排序。
  - `finalize_decision`：输出最终推荐方案。
- 调整 `serializers.py`，新增 `trace_to_dict()`，并在决策结果 JSON 中返回 `trace` 字段。
- 调整 `schemas.py`，新增 `TraceEventSchema`，并将 `trace` 纳入 `DecisionResponse`。
- 调整 `api_fastapi.py`，将接口文档标题和描述更新为复杂对抗场景定位。
- 调整 `README.md`，更新项目定位、目录结构、测试覆盖和后续优化路线。
- 扩展测试：
  - `tests/test_decision_engine.py` 覆盖 Trace 步骤顺序和最终推荐元数据。
  - `tests/test_serializers.py` 覆盖 Trace JSON 字段结构。
  - `tests/test_api_fastapi.py` 覆盖 API 返回中的 Trace 字段。

### 使用技术

- Python `dataclass`
- 决策链路 Trace
- 结构化 metadata
- API 响应扩展
- Pydantic 响应模型
- pytest 回归测试

### 优化价值

- 决策过程从“只返回结果”变成“结果 + 可解释过程”。
- 方便调试 Agent 提案、互评、权重、LLM 裁决和最终排序。
- 更适合在实习面试中讲成 Agent 工作流和可解释 AI 应用。
- 为后续前端 Trace 时间线、SSE 流式输出、历史决策回放打基础。

## 2026-07-13 第八轮：决策引擎流程模块化

### 改动内容

- 调整 `decision_engine.py`，将原本集中在 `DecisionEngine.run()` 中的主流程拆分为多个阶段函数。
- 新增内部数据结构 `LLMReviewDecision`，用于承载 LLM 裁决阶段的加分、决策模式、推荐智能体、推荐理由和错误信息。
- 新增或整理以下阶段方法：
  - `_start_trace()`：初始化决策 Trace。
  - `_generate_proposals()`：调用多个策略智能体生成候选方案。
  - `_run_dialogue_stage()`：执行智能体互评并记录 Trace。
  - `_build_weights_stage()`：计算动态评价权重并记录优先指标。
  - `_review_with_llm()`：处理 LLM 裁决、跳过、失败回退和强制模式报错。
  - `_score_and_rank()`：计算方案综合得分并排序。
  - `_finalize_trace()`：记录最终推荐方案。
- 保持原有 Agent 策略、动态权重计算、互评逻辑、评分公式和 API 返回字段不变。
- 扩展 `tests/test_decision_engine.py`，验证模块化后的工作流仍保持最终结果契约。

### 使用技术/工程实践

- 工作流式拆分
- 单一职责原则
- 内部 DTO/dataclass
- 回归测试
- 可维护性优化

### 优化价值

- `DecisionEngine.run()` 从大段过程代码变成清晰的工作流编排函数。
- 每个阶段职责更明确，后续可以单独测试、替换或扩展。
- 为后续接入 LangGraph、SSE 流式输出、历史决策回放打基础。
- 面试时更容易讲清楚多智能体决策流程的阶段设计。

## 2026-07-13 第九轮：历史决策记录持久化

### 改动内容

- 新增 `storage.py`，使用 SQLite 保存历史决策记录。
- 默认数据库路径为 `data/decision_records.db`，可通过 `MESSAGE_TALK_DB_PATH` 环境变量覆盖。
- 调整 `.gitignore`，忽略本地数据库文件 `data/*.db` 和相关临时文件。
- 调整 `.env.example`，增加 `MESSAGE_TALK_DB_PATH` 示例配置。
- 调整 `settings.py`，增加 `database_path` 配置项。
- 调整 `schemas.py`，新增：
  - `DecisionRecordSummarySchema`
  - `DecisionRecordDetailSchema`
- 调整 `api_fastapi.py`：
  - `/api/decide` 成功后自动保存本次决策输入和输出。
  - 新增 `GET /api/decisions` 查询历史决策摘要列表。
  - 新增 `GET /api/decisions/{record_id}` 查询单条历史决策详情。
  - 查询不存在的记录时返回统一错误结构，`error_type=record_not_found`。
- 新增 `tests/test_storage.py`，覆盖 SQLite 保存、列表查询、详情查询和缺失记录。
- 扩展 `tests/test_api_fastapi.py`，覆盖 API 层的历史记录保存、查询和 404 错误。
- 调整 `README.md`，补充 SQLite、历史记录接口和本地数据库路径说明。

### 使用技术

- SQLite
- Python `sqlite3`
- 本地文件数据库
- JSON 序列化存储
- Storage/Repository 分层
- FastAPI 查询接口
- pytest 临时数据库测试

### 优化价值

- 项目从“一次请求一次返回”的 demo 形态，升级为可回溯的决策评估平台。
- 每次决策的场景输入、方案排名、动态权重、智能体互评、决策 Trace 都可以保存和查询。
- 为后续前端历史记录页面、决策详情回放、结果对比分析打基础。

## 2026-07-13 第十轮：前端 Trace 时间线与历史记录回看

### 改动内容

- 调整 `frontend/index.html`，新增底部“决策 Trace”和“历史记录”两个展示区域。
- 调整 `frontend/app.js`：
  - 初始化时加载 `/api/decisions` 历史记录。
  - `/api/decide` 成功后自动刷新历史记录列表。
  - 新增 `renderTrace()`，将后端返回的 Trace 渲染为时间线。
  - 新增 `renderHistory()`，展示历史决策摘要。
  - 新增 `loadHistoryDetail()`，点击历史记录后调用 `/api/decisions/{record_id}`，回填历史场景和完整决策结果。
  - 新增基础 HTML 转义和时间格式化工具函数。
- 调整 `frontend/styles.css`，新增 Trace 时间线、历史记录列表、刷新按钮和响应式布局样式。
- 调整前端页面标题，将展示定位统一为“复杂对抗场景智能体策略评估”。
- 调整 `README.md`，补充前端历史记录和 Trace 时间线说明。

### 使用技术

- 原生 JavaScript `fetch`
- DOM 渲染
- 历史详情回填
- Trace 时间线 UI
- 响应式 CSS Grid
- 前端基础 XSS 防护转义

### 优化价值

- 后端保存的历史决策记录现在可以直接在页面中查看和回放。
- Trace 不再只是 API 字段，而是变成可视化流程时间线。
- 项目从“后端能力完成”进一步升级为“前后端闭环展示”的策略评估平台。
- 更适合演示系统的可解释性、决策回溯和工程完整度。

## 2026-07-13 第十一轮：SSE 流式决策进度输出

### 改动内容

- 调整 `decision_engine.py`，新增 `DecisionProgressEvent` 和 `run_stream()`。
- 保留原有 `run()` 行为不变，内部通过消费 `run_stream()` 返回最终结果。
- 调整 `api_fastapi.py`：
  - 新增 `POST /api/decide/stream`。
  - 使用 `StreamingResponse` 返回 `text/event-stream`。
  - 输出事件类型包括 `progress`、`result`、`done`、`error`。
  - 流式决策完成后仍会保存历史记录。
- 调整 `frontend/app.js`：
  - “运行 Python 决策”优先调用 `/api/decide/stream`。
  - 新增 SSE 文本流解析逻辑。
  - `progress` 事件实时更新 Trace 时间线。
  - `result` 事件回填完整决策结果并刷新历史记录。
  - 浏览器不支持流式读取时回退到普通 `/api/decide`。
- 扩展 `tests/test_api_fastapi.py`，覆盖流式接口的 `progress/result/done` 输出和历史记录保存。
- 调整 `README.md`，补充流式决策接口说明。

### 使用技术

- FastAPI `StreamingResponse`
- Server-Sent Events
- `text/event-stream`
- 原生 JavaScript ReadableStream
- 流式事件解析
- pytest 流式接口测试

### 优化价值

- 决策过程从“等待一次性结果”升级为“按阶段实时反馈”。
- 前端 Trace 时间线可以随后端阶段事件逐步更新。
- 更贴近大模型应用常见的流式交互体验。
- 为后续接入更耗时的 LLM 裁决、LangGraph 节点流式输出打基础。

## 2026-07-14 第十二轮：Docker 部署与一键启动优化

### 改动内容

- 新增 `Dockerfile`，支持将 FastAPI 服务和前端静态资源打包为 Docker 镜像。
- 新增 `.dockerignore`，减少镜像构建上下文，排除虚拟环境、缓存、IDE 配置、本地数据库、截图和日志。
- 新增 `docker-compose.yml`，支持通过 `docker compose up --build` 一键启动服务。
- Docker 环境中默认使用 `/app/data/decision_records.db` 保存 SQLite 历史记录。
- 新增 `scripts/start_server.ps1`，提供 Windows PowerShell 本地启动入口。
- 新增 `scripts/start_server.bat`，提供 Windows 批处理本地启动入口。
- 调整 `README.md`，补充本地一键启动、Docker 构建、Docker 运行和 Docker Compose 使用说明。

### 使用技术

- Docker
- Docker Compose
- Uvicorn
- 本地 volume 挂载
- Windows PowerShell 启动脚本
- Windows batch 启动脚本

### 优化价值

- 项目从“本机手动运行”升级为“可复现部署”。
- 其他人拿到项目后，可以通过脚本或 Docker 快速启动。
- SQLite 历史记录通过 volume 持久化，容器重启后数据仍可保留。
- 更适合实习项目演示、作品集提交和后续服务器部署。

## 2026-07-14 第十三轮：请求链路追踪与接口耗时观测

### 改动内容

- 调整 `api_fastapi.py`，新增 FastAPI HTTP 中间件 `request_context_middleware()`。
- 每次请求自动维护 `request_id`：
  - 如果请求头带有 `X-Request-ID`，后端沿用该值。
  - 如果请求头没有 `X-Request-ID`，后端自动生成唯一 ID。
- 每次响应统一返回：
  - `X-Request-ID`
  - `X-Response-Time-Ms`
- 接口访问日志新增 method、path、status、duration_ms、request_id，方便排查接口链路。
- HTTP 异常和参数校验异常的响应体新增 `request_id`，让前端错误、API 响应和后端日志可以关联。
- 调整 `schemas.py`，在 `ErrorResponse` 中补充 `request_id` 字段。
- 扩展 `tests/test_api_fastapi.py`：
  - 覆盖调用方自定义 `X-Request-ID` 的透传。
  - 覆盖后端自动生成请求 ID。
  - 覆盖参数校验错误时响应体和响应头中的 request_id。
- 调整 `README.md`，补充请求链路追踪能力说明。

### 使用技术

- FastAPI Middleware
- HTTP Header
- Request State
- Python `uuid`
- Python `time.perf_counter`
- 结构化接口日志
- pytest 接口链路测试

### 优化价值

- 项目从“接口能用”进一步升级为“接口可观测、问题可追踪”。
- 当前端、SSE、Docker 容器或外部调用出现异常时，可以通过 `request_id` 快速定位对应日志。
- `X-Response-Time-Ms` 可以辅助观察接口耗时，为后续性能优化、LLM 调用耗时统计和慢请求分析打基础。
- 这属于后端工程化能力，适合在实习面试中作为“接口可观测性”和“排障能力”的项目亮点。

## 2026-07-14 第十四轮：RAG 知识库基础版与 Agent 上下文增强

### 改动内容

- 新增 `rag/` 模块，作为项目的本地 RAG 知识检索层。
- 新增 `rag/documents/tactical_knowledge.md`，提供城市、山地、平原、低情报、敌强我弱、高时效、欺骗与火力协同等场景知识片段。
- 新增 `rag/retriever.py`：
  - 支持从 Markdown 文档加载知识片段。
  - 支持根据 `BattlefieldScene` 构造场景查询。
  - 使用 BM25 风格关键词检索召回 TopK 知识片段。
  - 对英文标签、数字、中文文本做基础 token 化。
- 调整 `decision_engine.py`：
  - 在 `start` 后新增 `retrieve_knowledge` 阶段。
  - Agent 生成方案前先召回 RAG 知识上下文。
  - `DecisionResult` 新增 `knowledge_context`。
  - 候选方案新增 `knowledge_sources`，记录 Agent 方案参考的知识片段标题。
  - SSE 流式输出中会新增 `retrieve_knowledge` 进度事件。
- 调整 `models.py`，为 `StrategyProposal` 增加 `knowledge_sources`。
- 调整 `serializers.py` 和 `schemas.py`，让 API 响应返回 `knowledge_context` 和每个方案的 `knowledge_sources`。
- 调整 `frontend/index.html`、`frontend/app.js`、`frontend/styles.css`：
  - 新增“RAG 知识上下文”展示面板。
  - 展示知识片段标题、来源文件、相关性分数和内容。
  - 历史记录回放时也能看到当时保存的 RAG 知识上下文。
- 新增 `tests/test_rag.py`，覆盖知识检索和场景查询标签。
- 扩展决策引擎、序列化和 API 测试，覆盖 RAG Trace、API `knowledge_context` 和 SSE 流式事件。
- 调整 `README.md`，补充 RAG 知识增强说明。

### 使用技术

- RAG
- 本地 Markdown 知识库
- BM25 风格关键词检索
- TopK 召回
- Agent Context
- Decision Trace
- FastAPI 响应模型扩展
- SSE 进度事件
- 原生 JavaScript DOM 渲染
- pytest

### 优化价值

- 项目从“规则型多智能体评分系统”向“知识增强型 Agent 决策系统”升级。
- Agent 生成方案前不再只依赖场景数值，而是先召回相关战术知识片段。
- 决策结果可解释性增强：用户可以看到本次决策参考了哪些知识来源。
- RAG 阶段已经进入 Trace 和 SSE 流式输出，后续可继续升级为 Embedding 向量检索、Hybrid Search、Rerank 和 MCP 工具化检索。
- 这轮是 AI Agent 方向的关键起点，比继续堆后端功能更贴近大模型应用实习项目。

## 2026-07-15 第十五轮：Agent Memory 历史案例召回

### 改动内容

- 新增 `memory.py`，作为 Agent Memory 历史案例召回模块。
- 基于 SQLite 历史决策记录实现轻量级记忆检索：
  - 读取最近历史决策记录。
  - 根据当前 `BattlefieldScene` 与历史 `scene_json` 计算相似度。
  - 相似度特征包括地形、天气、敌方强度、我方强度、补给水平、情报质量、时效压力、平民密度。
  - 返回 TopK 相似历史案例。
- 新增 `MemoryCase` 数据结构，记录历史记录 ID、场景名、历史最优 Agent、历史最优策略、相似度、匹配特征和创建时间。
- 调整 `decision_engine.py`：
  - 在 RAG `retrieve_knowledge` 后新增 `recall_memory` 阶段。
  - `DecisionResult` 新增 `memory_context`。
  - 候选方案新增 `memory_sources`，记录本次方案参考的历史记录 ID。
  - `generate_proposals` Trace 中新增 `memory_sources`。
  - SSE 流式输出中新增 `recall_memory` 进度事件。
- 调整 `api_fastapi.py`，让普通决策接口和 SSE 决策接口使用同一个 `DECISION_STORE` 构建 `DecisionMemory`。
- 调整 `models.py`、`serializers.py`、`schemas.py`，让 API 响应返回 `memory_context` 和每个方案的 `memory_sources`。
- 调整 `frontend/index.html`、`frontend/app.js`、`frontend/styles.css`，新增 “Agent Memory” 展示面板。
- 新增 `tests/test_memory.py`，覆盖场景相似度和历史案例召回。
- 扩展决策引擎、序列化和 API 测试，覆盖 `recall_memory` Trace、`memory_context`、`memory_sources` 和 SSE 事件。
- 调整 `README.md`，补充 Agent Memory 技术说明。

### 使用技术

- Agent Memory
- SQLite 历史案例召回
- 场景特征相似度计算
- TopK 召回
- Agent Context
- Decision Trace
- FastAPI 响应模型扩展
- SSE 进度事件
- 前端历史案例可视化
- pytest

### 优化价值

- 历史记录不再只是用户回看数据，而是升级为 Agent 可使用的经验记忆。
- Agent 在生成方案前可以看到相似历史案例，项目更贴近具备 Memory 能力的 AI Agent 系统。
- `memory_context` 与 `knowledge_context` 形成互补：前者来自历史经验，后者来自知识库。
- Trace 和 SSE 都能展示 Memory 阶段，让决策链路更可解释。
- 为后续 Tool Calling、MCP 工具化历史召回、LangGraph 记忆节点打基础。

## 2026-07-15 第十六轮：Agent Tool Calling 基础架构

### 改动内容

- 新增 `tools/` 工具包，作为 Agent 工具调用的统一抽象层。
- 新增 `tools/base.py`：
  - 定义 `ToolResult`，统一记录工具名、状态、输出、元数据和耗时。
  - 定义 `AgentTool` 协议，约束工具需要提供 `name` 和 `run()`。
  - 新增 `measured_tool_result()`，自动计算工具执行耗时。
- 新增 `tools/registry.py`：
  - 实现 `ToolRegistry`，支持工具注册、按名称查找和执行。
  - 为后续 MCP 工具、外部 API 工具、LangGraph 节点工具化做准备。
- 新增 `tools/knowledge_tool.py`：
  - 将现有 RAG 检索封装为 `knowledge_retrieval` 工具。
  - 输出知识片段和工具调用元数据。
- 新增 `tools/memory_tool.py`：
  - 将现有 Agent Memory 历史案例召回封装为 `memory_recall` 工具。
  - 输出相似历史案例和召回记录 ID。
- 新增 `tools/risk_tool.py`：
  - 实现 `risk_analysis` 风险分析工具。
  - 根据敌我强度、平民密度、时效压力、情报质量、补给水平和地形生成风险分、风险等级、风险因子和建议。
- 调整 `decision_engine.py`：
  - `DecisionEngine` 内部新增默认 `ToolRegistry`。
  - 将 RAG 检索、Memory 召回改为通过工具注册中心调用。
  - 新增 `analyze_risk` 决策阶段。
  - `DecisionResult` 新增 `risk_context` 和 `tool_calls`。
  - Trace 元数据记录工具名和工具耗时。
- 调整 `serializers.py` 和 `schemas.py`：
  - API 响应新增 `risk_context`。
  - API 响应新增 `tool_calls`，记录本次决策执行过的工具调用。
- 调整 `frontend/index.html`、`frontend/app.js`、`frontend/styles.css`：
  - 新增 “Tool Calls” 展示面板。
  - 前端展示工具名称、执行状态、耗时和关键元数据。
- 新增 `tests/test_tools.py`：
  - 覆盖工具注册、工具执行和未知工具错误。
- 扩展 `tests/test_decision_engine.py`、`tests/test_serializers.py`、`tests/test_api_fastapi.py`：
  - 覆盖 `analyze_risk` Trace 阶段。
  - 覆盖 `risk_context` 和 `tool_calls` API 返回字段。
  - 覆盖 SSE 流式输出中的风险分析阶段和工具调用结果。
- 调整 `README.md`：
  - 补充 Agent Tool Calling 工具调用章节。
  - 更新后续优化路线。

### 使用技术

- Agent Tool Calling
- Tool Registry
- Python Protocol
- Python dataclass
- 工具调用耗时统计
- 风险分析规则引擎
- Decision Trace
- FastAPI/Pydantic 响应模型扩展
- SSE 流式进度扩展
- 前端工具调用可视化
- pytest 回归测试

### 优化价值

- 项目从“阶段函数直接调用”升级为“Agent 通过工具注册中心调用能力”的结构，更贴近真实 AI Agent 应用。
- RAG、Memory、Risk Analysis 都变成可观测工具，面试时可以讲清楚 Tool Calling 的输入、输出、执行轨迹和耗时。
- `tool_calls` 让一次决策使用过哪些工具变得可追踪，方便后续接入 MCP、LangGraph、外部搜索、向量库或重试降级策略。
- 风险分析工具补强了复杂对抗场景的领域解释能力，让系统除了方案排序外，还能输出场景风险画像。

## 2026-07-15 第十七轮：Plan-and-Execute 工具规划层

### 改动内容

- 新增 `agent_planner.py`：
  - 定义 `ToolPlanStep`，记录工具执行顺序、工具名、调用目的、参数和是否必需。
  - 定义 `AgentToolPlan`，统一承载本轮 Agent 工具调用计划。
  - 新增 `RuleBasedToolPlanner`，根据场景特征生成工具调用计划。
- 调整 `decision_engine.py`：
  - `DecisionEngine` 新增 `tool_planner`。
  - 决策流程新增 `plan_tools` 阶段。
  - 工具执行前先生成 `tool_plan`，再按计划调用 `knowledge_retrieval`、`memory_recall`、`risk_analysis`。
  - RAG 和 Memory 的 `top_k` 参数改为由计划层决定。
  - Trace 中记录完整 `tool_plan`、工具目的和规划参数。
- 调整 `serializers.py` 和 `schemas.py`：
  - API 响应新增 `tool_plan` 字段。
  - 新增 `ToolPlanStepSchema` 和 `ToolPlanSchema`。
- 调整 `frontend/index.html`、`frontend/app.js`、`frontend/styles.css`：
  - “Tool Calls” 面板新增工具规划展示区域。
  - 前端区分展示“计划”和“实际工具调用结果”。
- 新增 `tests/test_agent_planner.py`：
  - 覆盖工具规划顺序、场景策略标签、动态参数和不可用工具跳过。
- 扩展 `tests/test_decision_engine.py`、`tests/test_serializers.py`、`tests/test_api_fastapi.py`：
  - 覆盖 `plan_tools` Trace 阶段。
  - 覆盖 API 与 SSE 返回中的 `tool_plan`。
- 调整 `README.md`：
  - 补充 Plan-and-Execute 工具规划流程说明。

### 使用技术

- Plan-and-Execute
- Rule-based Planning
- Agent Tool Plan
- Tool Registry
- Decision Trace
- FastAPI/Pydantic 响应模型扩展
- SSE 流式阶段扩展
- 前端执行计划可视化
- pytest 回归测试

### 优化价值

- 系统从“固定顺序调用工具”升级为“先规划、再执行”的 Agent 工作流。
- 面试时可以清楚说明：Agent 会根据场景生成工具计划，计划中包含调用目的、参数和顺序，然后按计划执行工具。
- `tool_plan` 与 `tool_calls` 形成闭环：前者解释为什么调用，后者记录实际调用结果。
- 后续更容易接入 LangGraph：`plan_tools`、`knowledge_retrieval`、`memory_recall`、`risk_analysis` 都可以自然映射成图节点。

## 2026-07-15 第十八轮：LangGraph-style 状态图编排

### 改动内容

- 新增 `workflow/` 包，作为决策流程的状态图编排层。
- 新增 `workflow/decision_graph.py`：
  - 定义 `DecisionGraphState`，统一承载场景、Trace、工具计划、工具结果、Agent 方案、互评消息、权重、LLM 裁决和排序结果。
  - 定义 `DecisionGraphNode`，将每个决策阶段抽象为可执行节点。
  - 定义 `DecisionGraphRunner`，按节点顺序执行并记录 `completed_nodes`。
- 调整 `decision_engine.py`：
  - `run_stream()` 从直接串联阶段函数，改为创建 `DecisionGraphState` 并交给 `DecisionGraphRunner` 执行。
  - 新增 `_build_decision_graph()`，集中声明当前状态图节点路径。
  - 新增节点适配方法：`_plan_tools_node`、`_retrieve_knowledge_node`、`_recall_memory_node`、`_analyze_risk_node`、`_generate_proposals_node`、`_run_dialogue_node`、`_build_weights_node`、`_llm_review_node`、`_score_proposals_node`、`_finalize_decision_node`。
  - `DecisionResult` 新增 `workflow_nodes`，记录实际执行过的图节点。
- 调整 `serializers.py` 和 `schemas.py`：
  - API 响应新增 `workflow_nodes` 字段。
- 新增 `tests/test_decision_graph.py`：
  - 覆盖状态图 Runner 的节点顺序、状态更新和快照。
- 扩展 `tests/test_decision_engine.py`、`tests/test_serializers.py`、`tests/test_api_fastapi.py`：
  - 覆盖 `workflow_nodes` 返回。
  - 验证状态图节点路径与 Trace 结果一致。
- 调整 `README.md`：
  - 补充 LangGraph-style 状态图编排说明。

### 使用技术

- LangGraph-style State Graph
- State-driven Workflow
- Node-based Orchestration
- DecisionGraphState
- DecisionGraphRunner
- Plan-and-Execute
- Tool Calling
- Decision Trace
- SSE Streaming
- FastAPI/Pydantic 响应模型扩展
- pytest 回归测试

### 优化价值

- 项目从“顺序函数编排”升级为“状态图节点编排”，更贴近 LangGraph 的核心思想。
- 每个阶段都有明确节点名和统一 State 输入输出，后续更容易替换、插拔或条件分支。
- `workflow_nodes` 可以直接展示本次决策的图节点执行路径，方便面试讲清楚 Agent Workflow。
- 现有 API、SSE、Trace、前端展示和历史记录能力保持兼容，没有改变原始项目目标。

## 2026-07-15 第十九轮：Agent 工具可靠性与降级策略

### 改动内容

- 调整 `tools/base.py`：
  - 新增 `ToolExecutionPolicy`，支持配置工具最大尝试次数和慢调用阈值。
  - 新增 `summarize_tool_results()`，汇总工具总数、成功数、失败数、fallback 次数、慢调用数和总耗时。
- 调整 `tools/registry.py`：
  - 新增 `run_with_policy()`。
  - 工具调用异常时自动按策略重试。
  - 重试仍失败时返回 `status=failed` 的 `ToolResult`，并使用 fallback 输出。
  - `ToolResult.metadata` 中记录 `attempts`、`max_attempts`、`fallback_used`、`slow_call` 和错误信息。
- 调整 `decision_engine.py`：
  - 新增 `tool_policy` 配置。
  - RAG、Memory、Risk 工具调用改为通过 `run_with_policy()` 执行。
  - RAG / Memory 失败时 fallback 为空列表。
  - Risk 工具失败时 fallback 为 `risk_level=unknown` 的默认风险上下文。
  - `DecisionResult` 新增 `tool_metrics`。
  - Trace 元数据新增 `tool_status`、`fallback_used`。
- 调整 `serializers.py` 和 `schemas.py`：
  - API 响应新增 `tool_metrics` 字段。
- 调整 `frontend/app.js` 和 `frontend/styles.css`：
  - “Tool Calls” 面板新增工具可靠性指标展示。
  - 展示 total、failed、fallback 和总耗时。
- 扩展测试：
  - `tests/test_tools.py` 覆盖工具失败重试、fallback 输出和统计汇总。
  - `tests/test_decision_engine.py` 覆盖 RAG 工具失败时系统继续完成决策。
  - `tests/test_serializers.py`、`tests/test_api_fastapi.py` 覆盖 `tool_metrics` API 返回。

### 使用技术

- Tool Retry
- Fallback Strategy
- ToolExecutionPolicy
- Fault-tolerant Agent Workflow
- Tool Metrics
- Decision Trace
- FastAPI/Pydantic 响应模型扩展
- 前端工具可靠性可视化
- pytest 故障注入测试

### 优化价值

- 项目从“工具能调用”升级为“工具失败也能降级完成决策”，更符合真实 Agent 工程实践。
- 单个工具异常不会直接中断整个多智能体评估流程。
- `tool_metrics` 可以量化工具调用健康状态，适合面试时讲可观测性、容错和工程稳定性。
- 为后续接入外部 MCP 工具、向量库、搜索服务或第三方 API 打下可靠性基础。

## 2026-07-15 第二十轮：MCP-style 工具目录与 Tool Schema

### 改动内容

- 调整 `tools/base.py`：
  - 新增 `ToolSpec`，用于描述工具名、工具说明、输入 schema、输出 schema 和标签。
- 调整 `tools/registry.py`：
  - 新增 `specs()`，统一导出当前注册工具目录。
  - 当工具未提供 `describe()` 时，自动生成基础工具描述。
- 调整 `tools/knowledge_tool.py`：
  - 新增 `describe()`，声明 `knowledge_retrieval` 的输入参数和输出结构。
- 调整 `tools/memory_tool.py`：
  - 新增 `describe()`，声明 `memory_recall` 的输入参数和输出结构。
- 调整 `tools/risk_tool.py`：
  - 新增 `describe()`，声明 `risk_analysis` 的输入参数、风险输出结构和标签。
- 调整 `schemas.py`：
  - 新增 `ToolSpecSchema`。
- 调整 `api_fastapi.py`：
  - 新增 `GET /api/tools`，返回当前 Agent 已注册工具目录。
- 扩展测试：
  - `tests/test_tools.py` 覆盖工具规格导出。
  - `tests/test_api_fastapi.py` 覆盖 `/api/tools` 工具目录接口。
- 调整 `README.md`：
  - 补充 MCP-style 工具目录与 Tool Schema 说明。

### 使用技术

- MCP-style Tool Schema
- Tool Discovery
- Tool Registry
- JSON Schema 风格描述
- FastAPI 工具目录接口
- Pydantic 响应模型
- pytest 接口测试

### 优化价值

- Agent 工具从“内部函数”升级为“可发现、可描述、可协议化”的工具目录。
- `/api/tools` 可以直接展示当前系统具备哪些工具、每个工具需要什么输入、会返回什么输出。
- 更贴近 MCP / Tool Calling 的真实工程形态，为后续外部工具、权限控制、自动工具选择和工具编排打基础。
- 面试时可以把本项目讲成：Tool Plan 负责规划，Tool Registry 负责注册，Tool Spec 负责工具发现，Tool Metrics 负责可靠性观测。

## 2026-07-15 第二十一轮：MCP-style 工具发现与 LangGraph-style 条件分支

### 改动内容

- 调整 `agent_planner.py`：
  - 新增 `SkippedToolStep`，记录被跳过的工具、跳过原因和触发条件。
  - `AgentToolPlan` 新增 `skipped_steps`，让工具计划同时表达“执行什么”和“不执行什么”。
  - `RuleBasedToolPlanner` 根据场景参数动态选择工具：
    - 情报质量不足、平民密度高或时效压力高时调用 `knowledge_retrieval`。
    - 城市/山地、时效压力高或敌方强度不低于我方时调用 `memory_recall`。
    - 平民密度高、时效压力高、敌强我弱或补给不足时调用 `risk_analysis`。
- 调整 `decision_engine.py`：
  - 工具节点不再强制调用所有工具。
  - 当工具未进入本轮计划时，节点写入 `status=skipped` 的 Trace 事件。
  - Trace metadata 记录 `reason`、`condition` 和 `branch=skip_tool`，用于解释条件分支。
- 调整 `schemas.py`：
  - 新增 `SkippedToolStepSchema`。
  - `ToolPlanSchema` 新增 `skipped_steps` 返回字段。
- 扩展测试：
  - `tests/test_decision_engine.py` 覆盖低压场景下跳过 RAG 和 Memory 的分支。
  - `tests/test_api_fastapi.py` 覆盖 API 返回 `tool_plan.skipped_steps` 和 skipped Trace。
- 调整 `README.md`：
  - 补充 MCP-style 工具发现 + LangGraph-style 条件分支说明。

### 使用技术

- MCP-style Tool Discovery
- Tool Schema
- Rule-based Tool Selection
- Conditional Tool Planning
- LangGraph-style Conditional Workflow
- Decision Trace
- FastAPI / Pydantic 响应模型扩展
- pytest 回归测试

### 优化价值

- 系统从“固定调用 RAG、Memory、Risk 三个工具”升级为“根据场景动态选择工具”。
- `tool_plan.steps` 展示实际执行的工具，`tool_plan.skipped_steps` 展示被跳过的工具和原因，面试时更容易讲清楚 Agent 的决策依据。
- Trace 可以解释条件分支路径：某个工具为什么没被调用、触发了哪个跳过条件。
- 这一轮把上一轮的 MCP-style 工具目录能力和已有 LangGraph-style 状态图串起来，形成更完整的 Agent Workflow。
- 低压平原场景会跳过不必要的 RAG 和 Memory，只执行必要的风险分析，减少无效工具调用。

## 2026-07-15 第二十二轮：工具选择评分器与图级条件路由

### 改动内容

- 调整 `agent_planner.py`：
  - `ToolPlanStep` 新增 `need_score` 和 `threshold`。
  - `SkippedToolStep` 新增 `need_score` 和 `threshold`。
  - `RuleBasedToolPlanner` 新增工具需求评分函数：
    - `_knowledge_need_score()`：根据情报缺口、平民压力和时效压力计算 RAG 需求分。
    - `_memory_need_score()`：根据复杂地形、时效压力和敌方压力计算 Memory 需求分。
    - `_risk_need_score()`：根据平民压力、时效压力、敌方压力和补给压力计算 Risk 需求分。
  - 工具是否调用由 `need_score >= threshold` 决定。
- 调整 `workflow/decision_graph.py`：
  - `DecisionGraphNode` 新增 `condition` 和 `on_skip`。
  - `DecisionGraphRunner` 支持图级条件节点：条件满足时执行节点，条件不满足时触发 skip hook。
  - 保持原有 `DecisionGraphNode("name", run)` 用法兼容。
- 调整 `decision_engine.py`：
  - `retrieve_knowledge`、`recall_memory`、`analyze_risk` 三个工具节点迁移到图级条件路由。
  - skip Trace metadata 新增 `need_score` 和 `threshold`。
- 调整 `schemas.py`：
  - `ToolPlanStepSchema` 和 `SkippedToolStepSchema` 暴露 `need_score` 与 `threshold`。
- 扩展测试：
  - `tests/test_agent_planner.py` 覆盖工具评分和跳过评分。
  - `tests/test_decision_graph.py` 覆盖条件节点 skip hook。
  - `tests/test_decision_engine.py` 覆盖 skip Trace 中的评分信息。
  - `tests/test_api_fastapi.py` 覆盖 API 返回的 `need_score` 与 `threshold`。
- 调整 `README.md`：
  - 补充工具选择评分器与图级条件路由说明。

### 使用技术

- Tool Selection Scoring
- Threshold-based Routing
- LangGraph-style Conditional Nodes
- Conditional Edge / Skip Hook
- MCP-style Tool Plan Explanation
- Decision Trace
- FastAPI / Pydantic 响应模型扩展
- pytest 回归测试

### 优化价值

- 工具选择从简单 if/else 升级为可解释评分：每个工具为什么调用、为什么跳过都有分数和阈值。
- 条件分支从业务节点内部判断升级为图 Runner 能力，更贴近 LangGraph 的状态图思想。
- `tool_plan.steps` 和 `tool_plan.skipped_steps` 可以直接展示工具选择依据，适合面试时解释 Agent 的规划过程。
- skip Trace 不只说明“跳过了”，还说明“评分是多少、阈值是多少、为什么没有达到调用条件”。
- 这一轮比上一轮更深入：上一轮实现条件选择结果，这一轮把条件选择机制抽象进 Planner 和 Graph Runner。

## 2026-07-16 第二十三轮：LLM Planner 工具规划与本地规则兜底

### 改动内容

- 调整 `agent_planner.py`：
  - `AgentToolPlan` 新增 `planner_source`、`planner_model`、`planner_error`。
  - 新增 `with_planner_metadata()`，用于在本地规则计划和 fallback 计划中写入规划来源。
- 调整 `llm_coordinator.py`：
  - 新增 `TOOL_PLANNER_SYSTEM_PROMPT`，让模型基于场景、Tool Schema 和本地评分参考生成工具计划。
  - 新增 `LLMToolPlanResult`。
  - 新增 `plan_tools()`，负责调用 LLM Planner。
  - 新增 `_to_tool_plan()`，将模型 JSON 转换为 `AgentToolPlan`。
  - 新增本地校验和参数清洗：
    - 未注册工具会被忽略。
    - `knowledge_retrieval` / `memory_recall` 的 `top_k` 限制在 1-6。
    - `risk_analysis` 不接受额外参数。
    - 模型没有选择任何有效工具时视为非法计划。
- 调整 `decision_engine.py`：
  - `plan_tools` 阶段先生成本地评分计划作为 fallback。
  - 当 `llm_mode=auto/on` 且 LLM 可用时，优先尝试 LLM Planner。
  - 当无 API Key、模型调用失败或模型计划非法时，回退到本地评分 Planner。
  - Trace metadata 新增 `planner_source`、`planner_model`、`planner_error`。
- 调整 `schemas.py`：
  - `ToolPlanSchema` 暴露 `planner_source`、`planner_model`、`planner_error`。
- 扩展测试：
  - `tests/test_decision_engine.py` 覆盖 Fake LLM Planner 成功接管工具计划。
  - 覆盖无 API Key 时 LLM Planner 回退到本地规则。
  - 覆盖 LLM Planner 输出校验、未知工具过滤和 `top_k` 参数清洗。
  - `tests/test_api_fastapi.py` 覆盖 API 返回的 planner 元数据。
- 调整 `README.md`：
  - 补充 LLM Planner 工具规划与本地规则兜底说明。

### 使用技术

- LLM Planner
- MCP-style Tool Schema Prompting
- Structured JSON Output
- Tool Plan Validation
- Local Rule Fallback
- Parameter Sanitization
- Decision Trace
- FastAPI / Pydantic 响应模型扩展
- pytest 回归测试

### 优化价值

- 工具规划从“本地评分器单独决定”升级为“LLM 先规划，本地规则兜底”。
- LLM Planner 会读取工具目录和 Tool Schema，更贴近 MCP / Tool Calling 的真实工程形态。
- 系统不会盲目信任模型输出：所有工具名、参数和计划结构都会经过本地校验。
- 无 API Key 或模型异常时，系统仍然能够稳定完成决策，并在 Trace 中解释 fallback 原因。
- 面试时可以讲成完整闭环：`ToolSpec -> LLM Planner -> Plan Validation -> Conditional Graph -> Tool Execution -> Trace`。

## 2026-07-16 第二十四轮：工具依赖 DAG 与上下文感知风险分析

### 改动内容

- 调整 `tools/risk_tool.py`：
  - `RiskAnalysisTool.run()` 新增可选入参 `knowledge_context` 和 `memory_context`。
  - `analyze_scene_risk()` 支持基于 RAG 知识片段和历史案例进行风险修正。
  - 新增 `context_evidence` 输出，记录：
    - 使用到的知识片段标题。
    - 使用到的历史案例 ID。
    - 上下文触发的风险信号。
    - 上下文带来的风险修正分。
    - 基于上下文生成的补充建议。
  - `ToolSpec` 输入 schema 增加 `knowledge_context`、`memory_context`。
  - `ToolSpec` 输出 schema 增加 `context_evidence`。
  - 工具标签增加 `context_aware`。
- 调整 `decision_engine.py`：
  - `analyze_risk` 节点接收 `state.knowledge_context` 和 `state.memory_context`。
  - 调用 `risk_analysis` 时注入上游 RAG / Memory 工具结果。
  - Trace metadata 增加 `depends_on`、`knowledge_context_count`、`memory_context_count`。
  - fallback 风险上下文补充默认 `context_evidence`。
- 扩展测试：
  - `tests/test_tools.py` 覆盖 Risk 工具使用知识和记忆上下文生成 evidence。
  - `tests/test_tools.py` 覆盖 Risk Tool Schema 中的上下文入参。
  - `tests/test_decision_engine.py` 覆盖完整决策流中 Risk 读取上游 RAG 上下文。
  - `tests/test_api_fastapi.py` 覆盖 API 返回 `risk_context.context_evidence`。
- 调整 `README.md`：
  - 补充工具依赖 DAG 与上下文感知风险分析说明。

### 使用技术

- Tool Dependency DAG
- Context Passing
- RAG Context Injection
- Agent Memory Context Injection
- Context-aware Risk Analysis
- MCP-style Tool Schema Extension
- Decision Trace
- pytest 回归测试

### 优化价值

- 工具调用从“并列执行”升级为“上游工具结果影响下游工具判断”。
- `risk_analysis` 能结合 RAG 知识和历史案例重新评估风险，避免只依赖原始场景数值。
- `context_evidence` 让风险分析更可解释：能看到风险判断参考了哪些知识片段、哪些历史案例和哪些上下文信号。
- Trace 明确展示 `risk_analysis` 依赖 `knowledge_retrieval` 和 `memory_recall`，更容易讲清楚 Agent DAG 工作流。
- 这一轮让项目的 Agent 工具链更像真实工程中的“工具编排 + 上下文传递 + 下游增强分析”。

## 2026-07-16 第二十五轮：Reflection / Critic Agent 决策审查

### 改动内容

- 新增 `decision_auditor.py`：
  - 新增 `AuditFinding`，描述单条审查发现。
  - 新增 `DecisionAudit`，承载最终审查报告。
  - 新增 `RuleBasedDecisionAuditor`，基于场景、最终排序、风险上下文、RAG 上下文和 Memory 上下文执行审查。
  - 审查项包括：
    - 高风险场景下最终方案风险控制不足。
    - 高平民密度下平民安全控制不足。
    - 低情报质量下情报匹配不足。
    - RAG / Memory 上下文显著放大风险。
    - 最终方案置信度偏低。
- 调整 `workflow/decision_graph.py`：
  - `DecisionGraphState` 新增 `decision_audit`。
  - `snapshot()` 新增 `audit_status`。
- 调整 `decision_engine.py`：
  - `DecisionEngine` 新增 `decision_auditor` 依赖。
  - 状态图新增 `audit_decision` 节点，位于 `score_proposals` 和 `finalize_decision` 之间。
  - `DecisionResult` 新增 `decision_audit`。
  - Trace 新增 `audit_decision` 事件，记录审查状态与发现数量。
- 调整 `serializers.py`：
  - API 结果新增 `decision_audit`。
- 调整 `schemas.py`：
  - `DecisionResponse` 新增 `decision_audit` 字段。
- 扩展测试：
  - 新增 `tests/test_decision_auditor.py`，覆盖高风险方案审查和低风险方案通过。
  - 扩展 `tests/test_decision_engine.py`，覆盖审查节点、Trace 和返回结果。
  - 扩展 `tests/test_api_fastapi.py`，覆盖 API 与 SSE 中的 `decision_audit`。
  - 扩展 `tests/test_serializers.py`，覆盖序列化字段。
- 调整 `README.md`：
  - 补充 Reflection / Critic Agent 决策审查说明。

### 使用技术

- Reflection Agent
- Critic Agent
- Rule-based Decision Audit
- Risk-aware Final Review
- Context Evidence Audit
- LangGraph-style Audit Node
- Decision Trace
- FastAPI / Pydantic 响应模型扩展
- pytest 回归测试

### 优化价值

- 决策流程从“生成并排序方案”升级为“排序后进行二次审查”。
- 审查器不会直接篡改最终排名，而是输出结构化风险发现和修正建议，保证评分逻辑与审查逻辑职责清晰。
- `decision_audit` 能解释最终方案是否存在风险控制、平民安全、情报匹配或上下文风险放大问题。
- `audit_decision` Trace 让 Self-Reflection / Critic Agent 的执行过程可追踪。
- 面试时可以讲成：Planner 负责规划工具，Graph 负责执行工具，Scoring 负责排序，Critic 负责最终审查。

## 2026-07-16 第二十六轮：接入真实 LangGraph StateGraph 工作流

### 改动内容

- 调整 `requirements.txt`：
  - 新增 `langgraph` 依赖。
- 调整 `workflow/decision_graph.py`：
  - 引入 `langgraph.graph.StateGraph`、`START`、`END`。
  - `DecisionGraphRunner` 从自定义顺序执行器升级为真实 LangGraph 编排器。
  - 新增 `LangGraphRuntimeState`，将项目原有 `DecisionGraphState` 作为 LangGraph 的共享状态载体。
  - 每个业务节点映射为 LangGraph 内部节点：
    - `router`：负责进入当前业务节点。
    - `run`：执行业务节点。
    - `skip`：执行条件不满足时的跳过逻辑。
  - 条件工具节点通过 `add_conditional_edges()` 路由到 `run` 或 `skip` 分支。
  - `stream()` 输出中只向业务层暴露实际业务节点执行结果，不暴露内部 router 节点。
  - 保留 `DecisionGraphNode`、`DecisionGraphState`、`DecisionEngine` 的现有调用方式，避免业务层大面积重写。
  - `DecisionGraphRunner.backend` 标记为 `langgraph`。
- 调整 `tests/test_decision_graph.py`：
  - 增加对 `runner.backend == "langgraph"` 的断言。
  - 原有顺序节点和条件 skip 测试继续通过。
- 调整 `README.md`：
  - 补充真实 LangGraph StateGraph 接入说明。
  - 收敛当前优化路线，后续聚焦 RAG、Memory、Planner、Evaluation 等 Agent 主流能力。

### 使用技术

- LangGraph
- StateGraph
- Conditional Edges
- Stateful Workflow
- Agent Workflow Orchestration
- Decision Trace
- pytest 回归测试

### 优化价值

- 项目从自定义状态图执行器升级为真实 LangGraph 工作流编排。
- 条件工具节点由 LangGraph 的 `add_conditional_edges()` 负责路由，更符合主流 Agent Workflow 实现方式。
- 保留原有业务状态对象和 API 返回合同，降低迁移风险。
- 面试时可以直接表述为：使用 LangGraph StateGraph 编排多智能体决策工作流，而不是自定义“类 LangGraph”实现。

## 2026-07-16 第二十七轮：RAG Query Rewrite 与 Rerank 检索增强

### 改动内容

- 调整 `rag/retriever.py`：
  - 新增 `QueryRewrite`，记录原始查询、扩展查询、扩展词和扩展原因。
  - 新增 `RetrievalResult`，承载最终知识片段、查询重写信息、候选数量和重排证据。
  - 新增 `rewrite_scene_query()`，根据场景地形、平民密度、时效压力、情报质量、补给和敌我压力生成查询扩展词。
  - 新增 `retrieve_for_scene_with_trace()`，执行“查询重写 -> 候选召回 -> 场景相关性重排”的检索流程。
  - 新增 `_rerank_candidates()`，基于场景信号对 BM25 候选进行重排。
  - 保留 `retrieve_for_scene()` 旧接口兼容性，其他模块仍可直接获取 `List[KnowledgeSnippet]`。
- 调整 `rag/__init__.py`：
  - 导出 `QueryRewrite` 和 `RetrievalResult`。
- 调整 `tools/knowledge_tool.py`：
  - `KnowledgeRetrievalTool.run()` 使用 `retrieve_for_scene_with_trace()`。
  - 工具 metadata 新增 `query_rewrite`、`candidates_considered`、`rerank_evidence`。
  - Tool tags 增加 `query_rewrite`、`rerank`。
- 调整 `decision_engine.py`：
  - `retrieve_knowledge` Trace metadata 新增查询重写、候选数量和重排证据。
- 扩展测试：
  - `tests/test_rag.py` 覆盖查询重写和重排证据。
  - `tests/test_tools.py` 覆盖 Knowledge 工具输出 RAG 流水线 metadata。
  - `tests/test_decision_engine.py` 覆盖 Trace 中的 `query_rewrite` 和 `rerank_evidence`。
  - `tests/test_api_fastapi.py` 覆盖 API Trace 返回检索流水线信息。
- 调整 `README.md`：
  - 补充 RAG Query Rewrite 与 Rerank 检索增强说明。

### 使用技术

- RAG
- Query Rewrite
- BM25 Candidate Recall
- Rule-based Rerank
- Retrieval Evidence
- Tool Metadata
- Decision Trace
- pytest 回归测试

### 优化价值

- RAG 从“直接关键词检索”升级为“查询重写 -> 候选召回 -> 场景相关性重排 -> 证据追踪”的检索流水线。
- Query Rewrite 让高压、低情报、平民密集等场景能生成更完整的检索意图。
- Rerank 能让与当前场景风险信号更匹配的知识片段排到前面。
- Trace 中可以解释本轮 RAG 为什么扩展了这些词、考虑了多少候选、最终片段的重排依据是什么。
- 这轮聚焦 RAG 主线能力，没有新增偏离 Agent 技术主线的业务功能。

## 2026-07-16 第二十八轮：真实 MCP Server 工具入口

### 改动内容

- 调整 `requirements.txt`：
  - 新增 `mcp[cli]>=1.28,<2`，使用官方 MCP Python SDK v1 稳定线。
- 新增 `mcp_server.py`：
  - 新增 `build_agent_tool_registry()`，复用现有 `KnowledgeRetrievalTool`、`MemoryRecallTool`、`RiskAnalysisTool` 构建 Agent 工具注册表。
  - 新增 `call_agent_tool()`，统一处理 MCP 工具调用、场景入参校验、`top_k` 限制、上下文反序列化和 `ToolResult` 序列化。
  - 新增 `create_mcp_server()`，基于 `FastMCP` 注册真实 MCP tools：`knowledge_retrieval`、`memory_recall`、`risk_analysis`。
  - 新增 MCP resource `agent-tools://catalog`，导出当前 Tool Registry 的工具目录。
  - 提供 `python mcp_server.py` 启动入口，默认使用 Streamable HTTP transport，服务地址为 `http://127.0.0.1:8001/mcp`。
- 新增 `tests/test_mcp_server.py`：
  - 覆盖 MCP payload 调用 RAG 工具。
  - 覆盖 RAG 输出注入 Risk 工具形成上下文链路。
  - 覆盖场景入参缺失校验。
  - 覆盖 `top_k` 工具预算限制。
  - 覆盖 FastMCP `list_tools()` 和 `call_tool()`，验证真实 MCP Server 能发现并调用工具。
- 调整 `README.md`：
  - 补充 MCP Server 启动方式。
  - 补充真实 MCP Server 与 FastAPI、Tool Registry 的关系。
  - 将原 “MCP-style 工具目录” 表述收敛为 “Tool Schema 工具目录”，避免和真实 MCP Server 混淆。

### 使用技术

- Model Context Protocol
- MCP Python SDK
- FastMCP
- MCP Tools
- MCP Resource
- Streamable HTTP Transport
- Tool Registry Reuse
- Structured Tool Result
- pytest 回归测试

### 优化价值

- 项目从“内部 Tool Schema / 工具目录”升级为“真实 MCP Server 对外暴露工具”。
- FastAPI 面向普通 Web/API 调用，MCP Server 面向 LLM Agent 客户端调用，两者复用同一套 RAG、Memory、Risk 工具实现。
- 面试时可以更专业地表达为：项目提供标准 MCP 工具入口，支持 Agent 客户端发现并调用 `knowledge_retrieval`、`memory_recall`、`risk_analysis`。
- 这一轮没有新增无关业务功能，而是把现有 Agent 工具链标准化暴露出去，和主流 Agent 工程实践对齐。

## 2026-07-16 第二十九轮：Agent Evaluation 场景评估与回归报告

### 改动内容

- 新增 `evaluation.py`：
  - 新增 `EvaluationCase`，定义评估用例、场景参数、预期工具、最低分数、允许风险等级、必要 Trace 节点和 RAG 扩展词。
  - 新增 `EvaluationCheck`，记录每一项评估检查的名称、结果和解释。
  - 新增 `EvaluationCaseResult` 和 `EvaluationSummary`，输出单用例结果和整体评估报告。
  - 新增 `AgentEvaluator`，运行评估场景集并调用 `DecisionEngine(llm_mode=off)` 生成评估结果。
  - 新增 `build_default_evaluation_cases()`，内置 3 个默认评估场景：
    - `urban_high_pressure`
    - `mountain_enemy_pressure`
    - `plain_low_context_need`
  - 新增 `evaluate_case_result()`，检查工具计划、Trace 完整性、工作流终态、工具失败数、风险等级、最终分数、Decision Audit 和 RAG 证据。
  - 支持 `python evaluation.py` 直接输出 JSON 评估报告。
- 调整 `api_fastapi.py`：
  - 新增 `POST /api/evaluations/run`。
  - 接口运行默认评估集并返回结构化报告。
  - 评估接口不写入 SQLite 历史记录，避免污染业务决策数据。
- 新增 `tests/test_evaluation.py`：
  - 覆盖默认评估集 3/3 通过。
  - 覆盖评估失败时能输出失败检查和 issue。
- 调整 `tests/test_api_fastapi.py`：
  - 覆盖 `/api/evaluations/run` 返回评估报告。
  - 验证评估接口不会新增历史决策记录。
- 调整 `README.md`：
  - 补充 Agent Evaluation 章节。
  - 补充 `python evaluation.py` 和 `POST /api/evaluations/run` 使用方式。
  - 更新后续路线，将 Evaluation 基础版改为后续扩展评估集和 CI 回归。

### 使用技术

- Agent Evaluation
- Scenario-based Evaluation
- Regression Report
- Tool Plan Evaluation
- Trace Completeness Check
- RAG Evidence Evaluation
- Decision Audit Evaluation
- FastAPI Evaluation Endpoint
- pytest 回归测试

### 优化价值

- 项目从“实现 Agent 工作流”升级为“可以评估 Agent 工作流质量”。
- 默认评估集能验证高压城市场景、山地敌压场景、低上下文需求平原场景下的工具选择是否稳定。
- RAG 不只看是否返回知识，还会检查 Query Rewrite 扩展词和 Rerank 证据是否存在。
- 面试时可以讲成：使用 Agent Evaluation 对 Planner、Tool Calling、RAG Evidence、Trace 和 Audit 做回归验证。
- 这轮继续围绕主流 Agent 工程能力，没有新增偏离项目主线的展示型功能。

## 2026-07-17 第三十轮：Agent Memory 写入策略与长期记忆摘要

### 改动内容

- 调整 `storage.py`：
  - 新增 `agent_memory_entries` SQLite 表，用于保存结构化长期记忆。
  - 新增 `MemoryEntryRecord`，表示长期记忆条目。
  - 新增 `save_memory_entry()`，保存摘要、经验、标签、风险等级、重要性分数和写入策略。
  - 新增 `list_memory_entries()`，查询长期记忆条目。
- 调整 `memory.py`：
  - `MemoryCase` 新增 `memory_id`、`summary`、`lessons`、`tags`、`risk_level`、`importance_score`。
  - 新增 `MemoryWriteResult`，记录本次记忆写入是否成功、写入原因和重要性分数。
  - 新增 `DecisionMemory.write_decision()`，在历史决策保存后生成结构化长期记忆。
  - 新增 `build_memory_summary()`、`build_memory_lessons()`、`build_memory_tags()`、`memory_importance_score()`、`should_write_memory()`。
  - `DecisionMemory.recall()` 优先从 `agent_memory_entries` 召回摘要记忆；没有长期记忆时回退到旧的完整历史记录召回。
- 调整 `api_fastapi.py`：
  - 新增 `_save_decision_and_memory()`，普通决策和 SSE 决策保存历史记录后同步写入长期记忆。
  - 新增 `GET /api/memory`，用于查看长期记忆条目。
- 调整 `schemas.py`：
  - `MemoryCaseSchema` 暴露长期记忆 ID、摘要、经验、标签、风险等级和重要性分数。
- 调整 `tools/memory_tool.py`：
  - `memory_recall` 的 Tool Schema 输出字段增加长期记忆相关字段。
  - 工具标签增加 `long_term_memory`。
- 扩展测试：
  - `tests/test_storage.py` 覆盖长期记忆条目保存和查询。
  - `tests/test_memory.py` 覆盖写入策略、摘要召回和重要性分数。
  - `tests/test_api_fastapi.py` 覆盖 `/api/memory` 和决策保存后的长期记忆写入。
- 调整 `README.md`：
  - 将 Agent Memory 章节从“历史案例召回”升级为“长期记忆写入 + 摘要召回”。
  - 补充 `GET /api/memory`。
  - 更新后续路线，将 Memory 后续优化聚焦到质量评估、去重压缩、过期策略和召回排序。

### 使用技术

- Agent Memory
- Long-term Memory
- Memory Write Policy
- Memory Summarization
- SQLite Memory Store
- Memory Importance Scoring
- Similarity Recall
- Tool Schema Extension
- FastAPI Memory Endpoint
- pytest 回归测试

### 优化价值

- Memory 从“临时读取历史记录”升级为“决策完成后沉淀长期经验”。
- 每次成功决策都会根据写入策略生成摘要、经验、标签和重要性分数，后续相似场景可以优先召回这些结构化记忆。
- `memory_recall` 返回的不再只是历史记录 ID，还包含可解释摘要和经验要点，面试时更容易讲清楚 Agent Memory 的写入、存储、召回和注入闭环。
- API 新增 `/api/memory`，可以直接展示当前长期记忆库内容。
- 这一轮继续聚焦 Agent 主流能力中的 Memory，没有新增偏离项目目标的展示型功能。

## 2026-07-22 第三十一轮：模块化 RAG 检索链路与 RRF 融合

### 改动内容

- 参考 `jerry-ai-dev/MODULAR-RAG-MCP-SERVER` 的 Query Pipeline 设计思路，对现有轻量 RAG 做工程化优化，但不直接照搬完整向量库和 Dashboard。
- 调整 `rag/retriever.py`：
  - `retrieve_for_scene_with_trace()` 从单一 BM25 + rerank 流程升级为五阶段检索链路：`query_processing`、`sparse_retrieval`、`scene_signal_retrieval`、`fusion`、`rerank`。
  - 新增 `RouteCandidate` 和 `FusedCandidate`，将候选来源、原始分数、匹配证据和融合贡献拆开记录。
  - 新增 `bm25` 本地关键词召回路线，保留专有词与场景标签精确匹配能力。
  - 新增 `scene_signal` 场景信号召回路线，根据地形、平民密度、情报质量、时效压力、补给和敌我强弱做可解释候选召回。
  - 新增 RRF（Reciprocal Rank Fusion）融合逻辑，用排名贡献融合多路候选，避免直接混合不同路线的原始分数。
  - `RetrievalResult.to_metadata()` 新增 `fusion_evidence` 和 `retrieval_trace`，让 FastAPI、MCP Tool 和决策 Trace 能展示检索中间状态。
- `tools/knowledge_tool.py` 保持现有实现：
  - 由于它已经复用 `RetrievalResult.to_metadata()`，本轮新增的 RRF 融合证据和检索阶段 Trace 会自动透传到工具 metadata。
- 调整 `tests/test_rag.py`：
  - 新增对 `fusion_evidence`、`retrieval_trace`、`scene_signal` 融合贡献的断言。
- 调整 `tests/test_tools.py`：
  - 验证 `knowledge_retrieval` 工具 metadata 中包含 RRF 融合证据和检索阶段 Trace。
- 调整 `README.md`：
  - 补充第三十一轮 RAG 模块化检索链路、RRF 融合和后续替换 Embedding Dense Retriever 的说明。

### 使用技术

- Modular RAG Query Pipeline
- Query Processing
- BM25 Sparse Retrieval
- Scene Signal Retrieval
- Reciprocal Rank Fusion（RRF）
- Retrieval Trace / Observability
- Rerank Evidence
- Tool Metadata Propagation
- pytest 回归测试

### 优化价值

- RAG 从“一个函数里完成检索和重排”升级为“多阶段、可解释、可替换”的检索流水线，更贴近主流 RAG 工程项目的表达方式。
- 当前没有伪装成真实 Dense Embedding 检索，而是明确使用 `bm25` 与 `scene_signal` 两条本地可解释路线；后续可把 `scene_signal` 路线替换为真正的 Embedding Retriever。
- RRF 融合让不同召回路线可以在不做分数归一化的情况下合并排名，面试时可以讲清楚为什么它适合 Hybrid Search。
- `fusion_evidence` 和 `retrieval_trace` 可以解释每个知识片段来自哪条路线、排名贡献是多少、最终为什么被重排到前面，增强项目的可观测性和可答辩性。
- 这一轮继续聚焦 RAG / MCP / Agent 工具主线，没有新增偏离当前项目定位的杂项功能。

## 2026-07-22 第三十二轮：RAG Embedding 与 VectorStore 可插拔骨架

### 改动内容

- 调整 `settings.py`：
  - 新增 `MESSAGE_TALK_EMBEDDING_PROVIDER`、`MESSAGE_TALK_EMBEDDING_MODEL`、`MESSAGE_TALK_EMBEDDING_API_KEY`、`MESSAGE_TALK_EMBEDDING_BASE_URL`、`MESSAGE_TALK_EMBEDDING_DIMENSIONS`。
  - 新增 `MESSAGE_TALK_VECTOR_STORE`、`MESSAGE_TALK_RAG_DENSE_ENABLED`、`MESSAGE_TALK_RAG_RRF_K`。
  - 默认 embedding provider 为 `local-hashing`，用于本地开发、测试和无 API Key 降级。
- 调整 `.env.example`：
  - 补充 RAG embedding、vector store、dense retrieval 和 RRF 参数示例。
- 新增 `rag/embeddings.py`：
  - 定义 `EmbeddingConfig` 和 `EmbeddingProvider` 协议。
  - 新增 `LocalHashingEmbeddingProvider`，通过稳定 hash 向量生成本地确定性 embedding fallback。
  - 新增 `OpenAICompatibleEmbeddingProvider`，预留 OpenAI-compatible embedding 接口，后续配置真实 embedding 模型后可切换。
  - 新增 `create_embedding_provider()` 工厂函数，按配置创建 provider。
- 新增 `rag/vector_store.py`：
  - 定义 `VectorRecord`、`VectorSearchResult`。
  - 新增 `InMemoryVectorStore`，支持文档 upsert、query embedding 和 cosine similarity 检索。
- 调整 `rag/retriever.py`：
  - `KnowledgeRetriever` 支持注入 `EmbeddingProvider`、`VectorStore`、`dense_enabled` 和 `rrf_k`。
  - `KnowledgeRetriever.default()` 会读取 settings 并初始化 embedding/vector route。
  - `retrieve_for_scene_with_trace()` 新增 `dense_retrieval` 阶段，并把 provider、model、dimensions、vector_store 和 fallback_reason 写入 Trace。
  - RRF 融合路线从 `bm25 + scene_signal` 升级为 `bm25 + embedding_dense + scene_signal`。
  - `rerank_evidence` 新增 `dense_score`，用于解释 dense route 对最终排序的贡献。
- 调整 `rag/__init__.py`：
  - 导出 embedding provider、vector store 和 provider factory。
- 调整测试：
  - `tests/test_settings.py` 覆盖新增 RAG 配置默认值。
  - `tests/test_rag.py` 验证 `local-hashing` embedding 的确定性、`dense_retrieval` Trace 和 `embedding_dense` RRF 贡献。

### 使用技术

- EmbeddingProvider Abstraction
- OpenAI-compatible Embedding Provider 预留
- Local Hashing Embedding Fallback
- VectorStore Abstraction
- In-memory Vector Index
- Cosine Similarity
- Dense Retrieval Route
- Hybrid Search
- RRF 多路候选融合
- Retrieval Trace / Fallback Observability
- pytest 回归测试

### 优化价值

- 项目从“没有 embedding 配置”升级为“具备 embedding provider 与 vector store 可插拔骨架”。
- 默认 `local-hashing` 能保证无 API Key 时也能本地运行和测试，但文档中明确说明它不是语义 embedding 模型，避免简历表述失真。
- 后续只需要配置真实 OpenAI-compatible embedding model，就可以把 `embedding_dense` route 升级为语义向量检索，不需要重写 RAG 主流程。
- MCP 的 `knowledge_retrieval` 工具不需要额外改造，就能通过现有 metadata 透传 dense retrieval、RRF 和 fallback 证据。
- 这一轮继续聚焦 RAG + MCP + Agent 工具链主线，补齐了后续接真实向量库和知识库 MCP 工具的基础。

## 2026-07-22 第三十三轮：生产化 OpenAI-compatible Embedding 接入

### 改动内容

- 调整 `rag/embeddings.py`：
  - `OpenAICompatibleEmbeddingProvider` 从简单封装升级为直接调用 OpenAI-compatible `/embeddings` HTTP 接口。
  - 新增 `EmbeddingHealth`，用于记录 provider、model、可用状态、向量维度、延迟和错误信息。
  - `EmbeddingProvider` 协议新增 `is_semantic` 与 `health_check()`，区分真实语义 embedding 和本地 fallback。
  - OpenAI-compatible provider 新增 `timeout_sec`、`batch_size`、`max_retries`。
  - 新增 batch 分片请求、HTTP 状态检查、指数退避重试、响应数量校验、向量维度校验和向量归一化。
  - 保留 `LocalHashingEmbeddingProvider`，但明确标记 `is_semantic=False`，只用于本地开发和无 Key fallback。
- 调整 `settings.py`：
  - 新增 `MESSAGE_TALK_EMBEDDING_TIMEOUT`、`MESSAGE_TALK_EMBEDDING_BATCH_SIZE`、`MESSAGE_TALK_EMBEDDING_MAX_RETRIES`。
  - 新增 `MESSAGE_TALK_RAG_STRICT_EMBEDDING`，生产环境可打开严格模式，embedding 初始化失败时直接报错。
- 调整 `.env.example`：
  - 补充 embedding timeout、batch size、max retries 和 strict embedding 配置项。
- 调整 `rag/vector_store.py`：
  - `upsert_documents()` 新增向量数量校验、空向量校验和维度一致性校验，避免索引写入静默错误。
- 调整 `rag/retriever.py`：
  - `KnowledgeRetriever.default()` 将 embedding timeout、batch size、max retries 和 strict mode 传入 provider。
  - dense 初始化失败时，如果 strict mode 为 `true`，直接抛出错误；否则降级并在 Trace 中记录 fallback reason。
  - `dense_retrieval` Trace 新增 `is_semantic`、`batch_size`、`max_retries`、`provider`、`model`、`dimensions` 和 `vector_store`。
- 调整 `rag/__init__.py`：
  - 导出 `EmbeddingHealth` 和 `OpenAICompatibleEmbeddingProvider`。
- 新增 `tests/test_embeddings.py`：
  - 使用 `httpx.MockTransport` 模拟 OpenAI-compatible embedding 服务。
  - 覆盖 batch 请求、model 入参、健康检查、语义 provider 标记和维度不匹配错误。
- 调整 `tests/test_settings.py`：
  - 覆盖 embedding timeout、batch size、max retries 和 strict embedding 默认值与环境变量读取。
- 调整 `README.md`：
  - 补充真实 embedding 配置示例、生产环境严格模式建议和默认 fallback 的边界说明。

### 使用技术

- OpenAI-compatible Embeddings API
- HTTP Client / httpx
- Batch Embedding Request
- Retry with Exponential Backoff
- Timeout Control
- Response Schema Validation
- Vector Dimension Validation
- Embedding Health Check
- Strict Mode / Fail-fast Configuration
- Retrieval Trace Observability
- pytest + httpx MockTransport

### 优化价值

- 第一阶段从“只预留 OpenAI-compatible provider”升级为“真实可调用、可测试、可观测的 embedding provider”。
- 配置真实 embedding model 后，`embedding_dense` route 才能算语义 Dense Retrieval；默认 `local-hashing` 仍只作为本地 fallback。
- 生产环境可以通过 `MESSAGE_TALK_RAG_STRICT_EMBEDDING=true` 防止 embedding 初始化失败后悄悄降级。
- MCP 和 Agent 工具链无需重复改造，`knowledge_retrieval` 会继续通过 metadata 输出 dense provider、RRF 与 fallback 证据。
- 面试时可以准确表述为：项目支持 OpenAI-compatible embedding provider，具备批量请求、重试、超时、健康检查和向量维度校验；当前是否启用真实语义检索取决于部署配置。

## 2026-07-22 第三十四轮：SQLite 持久化 VectorStore 与索引构建脚本

### 改动内容

- 调整 `settings.py`：
  - 默认 `MESSAGE_TALK_VECTOR_STORE` 从 `in-memory` 升级为 `sqlite`。
  - 新增 `MESSAGE_TALK_VECTOR_DB_PATH`，默认 `data/rag_vectors.db`。
  - 新增 `MESSAGE_TALK_VECTOR_COLLECTION`，默认 `tactical_knowledge`。
- 调整 `.env.example`：
  - 补充 SQLite vector store 路径和 collection 配置。
- 调整 `rag/vector_store.py`：
  - 新增 `SQLiteVectorStore`，使用 SQLite 保存 RAG 向量索引。
  - 新增 `rag_vector_documents` 表，字段包含 collection、record_id、source、title、content、content_hash、embedding_provider、embedding_model、embedding_dimensions、vector_json、created_at、updated_at。
  - 支持按 collection 隔离索引，支持同一数据库保存多套知识集合。
  - `upsert_documents()` 增加幂等写入逻辑：如果 content hash、provider、model、dimensions 未变化，则跳过重新 embedding。
  - 支持 `replace_collection=True` 删除 stale vector，避免知识库删除文档后旧向量仍参与召回。
  - 新增 `stats()`，返回 store、collection、db_path、document_count、source_count、last_updated_at。
  - `InMemoryVectorStore` 保留为测试和临时模式，并统一返回 upsert 统计。
- 调整 `rag/retriever.py`：
  - 根据 settings 创建 `SQLiteVectorStore` 或 `InMemoryVectorStore`。
  - `dense_retrieval` Trace 新增 `vector_collection`、`vector_index` 和 `vector_store_stats`。
  - dense 初始化会通过 `upsert_documents(..., replace_collection=True)` 构建或刷新索引。
- 新增 `scripts/build_rag_index.py`：
  - 支持显式构建或刷新 RAG 向量索引。
  - 支持 documents dir、embedding provider/model/API/base URL/dimensions/timeout/batch/retry、vector store、db path、collection、strict mode 等参数。
  - 输出 JSON 格式结果，包含 documents_loaded、embedding provider、health、vector_index upsert/skip/delete 统计和 vector_store stats。
- 调整 `Dockerfile` 和 `docker-compose.yml`：
  - 默认设置 `MESSAGE_TALK_VECTOR_STORE=sqlite`。
  - 默认向量库路径为 `/app/data/rag_vectors.db`，复用现有 `./data:/app/data` 持久化挂载。
- 新增 `tests/test_vector_store.py`：
  - 覆盖 SQLite vector store 持久化检索。
  - 覆盖未变化文档跳过 embedding。
  - 覆盖删除 stale vector。
- 调整 `tests/test_settings.py`：
  - 覆盖 vector db path 和 collection 默认配置。
- 调整 `README.md`：
  - 补充 `python scripts/build_rag_index.py` 索引构建命令。
  - 补充 SQLite VectorStore 设计、配置和 Docker 持久化说明。

### 使用技术

- SQLite-backed VectorStore
- Persistent Vector Index
- Collection Isolation
- Content Hash Deduplication
- Idempotent Upsert
- Stale Vector Cleanup
- Cosine Similarity Search
- Index Build CLI
- JSON Build Report
- Docker Volume Persistence
- pytest 回归测试

### 优化价值

- RAG 向量索引从“服务启动时临时内存构建”升级为“可持久化、可重复构建、可观测的本地向量索引”。
- 幂等 upsert 避免每次启动都重复 embedding 未变化知识片段，更接近生产环境索引构建方式。
- collection 隔离为后续 `list_knowledge_collections` 和 `query_knowledge_hub` MCP 工具打基础。
- 索引构建脚本让知识库更新可以从服务运行中解耦，后续可接 CI、定时任务或管理接口。
- 当前仍保持无重型向量库依赖；后续如果要接 Chroma/Qdrant，可以复用同一 VectorStore 抽象替换实现。

## 2026-07-22 第三十五轮：轻量 Ingestion Pipeline 与文件级去重

### 改动内容

- 调整 `settings.py`：
  - 新增 `MESSAGE_TALK_INGESTION_HISTORY_DB_PATH`，默认 `data/rag_ingestion.db`。
  - 新增 `MESSAGE_TALK_RAG_CHUNK_SIZE`，默认 `900`。
  - 新增 `MESSAGE_TALK_RAG_CHUNK_OVERLAP`，默认 `120`。
- 调整 `.env.example`：
  - 补充 ingestion history、chunk size 和 chunk overlap 配置。
- 新增 `rag/ingestion.py`：
  - 新增 `MarkdownIngestionPipeline`，负责 Markdown 文件扫描、加载、metadata 提取、section 拆分和 chunk 拆分。
  - 新增 `DocumentChunk`、`SourceDocument`、`IngestionFileResult`、`IngestionResult`。
  - 新增 `IngestionHistoryStore`，使用 SQLite 表 `rag_ingestion_history` 记录 collection、file_path、file_hash、file_size、status、chunk_count、metadata_json、error 和更新时间。
  - 支持 SHA256 文件 hash，用于判断文件是否未变化。
  - 支持从 Markdown 提取 document title、headings、tags、source path、file hash、chunk index、chunk size 等 metadata。
  - 支持 `IngestionResult.to_dict()` 输出 files_total、files_processed、files_unchanged、files_failed、chunks_total 和文件级明细。
- 调整 `rag/retriever.py`：
  - `KnowledgeRetriever.from_directory()` 不再直接解析 Markdown，而是统一调用 `MarkdownIngestionPipeline`。
  - `KnowledgeDocument` 新增 `metadata` 字段，保留 ingestion 产生的 chunk metadata。
  - `dense_retrieval` Trace 新增 `ingestion` 报告，便于排查当前检索基于哪批知识 chunk。
- 调整 `rag/vector_store.py`：
  - SQLite vector index 新增 `metadata_json` 字段，并提供兼容旧库的列迁移。
  - `upsert_documents()` 将 chunk metadata 持久化到 vector index。
  - 幂等判断同时比较 `content_hash` 和 `metadata_json`，避免 metadata 变更后索引记录仍旧。
  - `search()` 返回的 stored document 携带 metadata。
- 调整 `scripts/build_rag_index.py`：
  - 新增 `--ingestion-history-db-path`、`--chunk-size`、`--chunk-overlap` 参数。
  - JSON 输出新增 `ingestion` 报告。
- 调整 `rag/__init__.py`：
  - 导出 `DocumentChunk`、`IngestionHistoryStore`、`IngestionResult`、`MarkdownIngestionPipeline`。
- 新增 `tests/test_ingestion.py`：
  - 覆盖 Markdown metadata 提取、section chunk、文件未变化识别和大段文本拆分。
- 调整 `tests/test_vector_store.py`：
  - 覆盖 vector store 持久化 chunk metadata。
- 调整 `tests/test_rag.py`：
  - 验证 `dense_retrieval` Trace 中包含 ingestion 报告。
- 调整 `README.md`：
  - 补充 Ingestion Pipeline、文件 hash、chunk metadata 和配置说明。

### 使用技术

- Markdown Loader
- Section Splitter
- Chunk Splitter
- Metadata Extraction
- SHA256 File Hash
- SQLite Ingestion History
- File-level Deduplication
- Chunk Metadata Propagation
- Ingestion Report
- Retriever Pipeline Integration
- pytest 回归测试

### 优化价值

- RAG 知识库从“直接读取 Markdown 文件”升级为“可追踪、可复用、可观测的 ingestion pipeline”。
- 文件级 hash 和 ingestion history 为后续增量构建、大规模文档摄取和管理接口打基础。
- chunk metadata 会进入 Retriever、VectorStore 和 Trace，后续可以支持按 source、section、tags 做过滤与解释。
- 索引构建脚本能够输出完整 ingestion 报告，便于判断本次构建是处理新文件、跳过未变化文件，还是出现失败文件。
- 这一轮完成五点规划中的第 3 点，继续聚焦 RAG + MCP + Agent 工具链主线。

## 2026-07-23 第三十六轮：MCP Knowledge Hub 工具与直接 RAG Query Trace

### 改动内容

- 调整 `rag/retriever.py`：
  - 新增 `KnowledgeRetriever.retrieve_query_with_trace()`，支持直接输入自然语言 query 检索本地 RAG 知识库。
  - 将场景检索与普通 query 检索收敛到同一套内部 `_retrieve_with_trace()` 流水线，复用 `sparse_retrieval`、`dense_retrieval`、`fusion` 和 `rerank` 阶段。
  - 场景检索继续保留 `scene_signal_retrieval` 与 `scene_signal_boost`，直接 query 则使用 `query_score_boost`，避免把战场场景信号硬套到普通检索。
  - `retrieve()` 从单纯 BM25 调整为复用 direct query trace 的 hybrid retrieval 结果，保持外部调用更一致。
  - `fusion` Trace 的输入统计补充 dense route 候选数量，让 RRF 阶段的观测数据更完整。
- 调整 `mcp_server.py`：
  - 新增 `query_knowledge_hub(query, top_k)`，允许 MCP 客户端直接查询 RAG 知识库并返回 snippets 与完整 retrieval metadata。
  - 新增 `list_knowledge_collections()`，返回 collection 名称、文档数量、embedding provider、vector store stats、vector index 统计和 ingestion 报告。
  - 新增 `get_retrieval_trace(query, top_k)`，只返回 Query Rewrite、fusion evidence、rerank evidence 和 stage trace，适合调试召回质量。
  - `create_mcp_server()` 新增三个 FastMCP tools：`query_knowledge_hub`、`list_knowledge_collections`、`get_retrieval_trace`。
  - 新增 MCP Resource `knowledge-hub://collections`，让 MCP 客户端可以通过 resource 方式查看知识库集合状态。
  - MCP Knowledge Hub 工具会复用 `ToolRegistry` 中 `KnowledgeRetrievalTool` 持有的同一个 `KnowledgeRetriever`，避免重复初始化多套索引。
- 调整 `tests/test_rag.py`：
  - 新增 direct query trace 测试，覆盖 `raw_query`、dense retrieval、RRF fusion 和 `query_score_boost`。
- 调整 `tests/test_mcp_server.py`：
  - 覆盖 `query_knowledge_hub` 返回 snippets 与 trace metadata。
  - 覆盖 `list_knowledge_collections` 返回 vector store 与 ingestion 状态。
  - 覆盖 `get_retrieval_trace` 返回检索证据且不返回知识片段正文。
  - 覆盖 FastMCP 工具列表新增三个 Knowledge Hub 工具，并验证 MCP tool call 可执行。
- 调整 `README.md`：
  - 补充 MCP tools/resource 列表。
  - 补充 direct query trace 与 MCP Knowledge Hub 的项目说明。
  - 将后续路线中已完成的 MCP 知识库工具项替换为 RAG Evaluation 方向。

### 使用技术

- MCP Python SDK / FastMCP
- MCP Tool / MCP Resource
- Knowledge Hub Tooling
- Direct RAG Query
- Hybrid Retrieval Pipeline
- BM25 Sparse Retrieval
- Dense Retrieval Route
- RRF 多路候选融合
- Query-level Rerank
- Retrieval Trace Observability
- VectorStore Stats
- Ingestion Report
- pytest TDD 回归测试

### 优化价值

- MCP Server 从“只暴露 Agent 执行工具”升级为“Agent 工具 + 知识库工具”，更接近真实 Agent 平台里的工具生态。
- 外部 MCP 客户端现在可以不传完整战场场景，直接查询本地知识库，适合做知识库问答、检索调试和工具链演示。
- `list_knowledge_collections` 让知识库状态可观测：能看到当前 collection、文档数量、向量索引状态和 ingestion 结果，便于解释索引是否构建成功。
- `get_retrieval_trace` 将检索过程拆成可展示证据，面试时可以讲清楚“query 怎么处理、BM25/Dense 召回了什么、RRF 怎么融合、最终为什么重排”。
- direct query 与 scene query 复用同一套 pipeline，减少重复逻辑，也让后续接入 RAG Evaluation 或 Chroma/Qdrant 时改动边界更清晰。
- 这一轮完成前面五点路线中的第 4 点：MCP 知识库工具专业化。

## 2026-07-23 第三十七轮：RAG 专项 Evaluation 检索质量评估

### 改动内容

- 新增 `rag_evaluation.py`：
  - 新增 `RAGEvaluationCase`，定义 RAG 查询用例、预期命中文档标题、预期来源和 TopK。
  - 新增 `RAGEvaluationCaseResult`，记录每个查询的命中情况、预期标题排名、MRR、nDCG、source match、rerank improvement、snippets、fusion evidence、rerank evidence 和 retrieval trace。
  - 新增 `RAGEvaluationSummary`，汇总 total_cases、passed_cases、hit_at_k、mean_reciprocal_rank、mean_ndcg、source_match_rate 和 average_rerank_improvement。
  - 新增 `RAGEvaluator`，统一调用 `KnowledgeRetriever.retrieve_query_with_trace()` 运行检索评估。
  - 新增 `build_default_rag_evaluation_cases()`，默认覆盖城市平民风险、低情报侦察、高时效指挥、山地补给控制、敌强我弱迟滞 5 类知识主题。
  - 新增 `reciprocal_rank()`、`ndcg_at_k()` 和 `first_expected_rank()` 指标函数。
  - 新增 CLI 入口，支持 `python rag_evaluation.py` 运行完整评估，也支持 `--case-id` 运行单个用例。
- 新增 `tests/test_rag_evaluation.py`：
  - 覆盖默认评估集的 case 数量与知识主题。
  - 覆盖 MRR 与 nDCG 指标函数。
  - 覆盖默认 RAG 评估报告的 hit@k、MRR、nDCG、source match 和 rerank improvement。
  - 覆盖预期标题不存在时的失败报告。
  - 覆盖 CLI JSON 输出。
- 调整 `README.md`：
  - 快速启动部分新增 `python rag_evaluation.py`。
  - 新增 “RAG Evaluation 评估”章节，说明评估集、指标和与 Agent Evaluation 的边界。
  - 技术栈补充 `RAG Evaluation / hit@k / MRR / nDCG`。

### 使用技术

- RAG Evaluation
- hit@k
- MRR / Mean Reciprocal Rank
- nDCG
- Expected Source Match
- Rerank Improvement
- Retrieval Trace Evidence
- JSON Evaluation Report
- pytest TDD 回归测试

### 优化价值

- 项目从“RAG 能检索”进一步升级为“RAG 检索质量可量化评估”。
- RAG Evaluation 与 Agent Evaluation 分离：前者评估知识库召回质量，后者评估完整 Agent 工作流和最终决策质量。
- hit@k、MRR、nDCG 可以在面试中解释检索系统常见评估方法，不只是展示接口返回。
- source match 能检查命中的知识片段是否来自预期知识源，避免只看标题命中却忽略来源错误。
- rerank improvement 可以观察最终重排是否相比 RRF 融合排名有提升，为后续优化 Rerank 策略提供基线。
- 这一轮完成剩余未完成点中的第 1 点：RAG 专项 Evaluation。真实语义 Embedding 跑通和外部向量库接入仍保留为后续独立轮次。

## 2026-07-23 第三十八轮：Embedding Provider 验证入口与真实语义检索边界校验

### 改动内容

- 新增 `embedding_validation.py`：
  - 新增 `EmbeddingValidationOptions`，用于配置样本文本、probe query、预期 Top1 标题和是否允许本地 fallback。
  - 新增 `EmbeddingValidationReport`，统一输出 ok、provider、model、dimensions、health、dense_probe、issues 和 checked_at。
  - 新增 `validate_embedding_provider()`，按 `health_check -> sample embed -> vector validation -> dense probe` 的顺序验证 Embedding Provider。
  - 验证逻辑会检查向量数量、空向量、维度一致性，并默认要求 `provider.is_semantic=True`。
  - 内置 dense probe：把 3 条小型知识片段写入 `InMemoryVectorStore`，再用查询向量执行 cosine similarity 检索，验证预期知识片段是否能排到 Top1。
- 新增 `scripts/validate_embedding_provider.py`：
  - 提供命令行验证入口，可通过参数覆盖 provider、model、API Key、base URL、dimensions、timeout、batch size 和 retry。
  - 默认拒绝 `local-hashing` 作为真实语义 embedding；只有显式增加 `--allow-local-fallback` 才允许本地探针通过。
  - 输出 JSON 报告，便于面试演示、部署前检查或后续接入 CI。
- 新增 `tests/test_embedding_validation.py`：
  - 覆盖语义 provider 验证通过。
  - 覆盖默认拒绝 `local-hashing`，避免把本地哈希向量误称为真实语义 embedding。
  - 覆盖 `--allow-local-fallback` 本地探针通过。
  - 覆盖向量数量不一致、dense probe Top1 不符合预期等失败分支。
  - 覆盖 CLI JSON 输出和退出码。
- 调整 `README.md`：
  - 快速启动部分新增真实 OpenAI-compatible embedding 验证命令。
  - 补充 local-hashing fallback 的显式验证命令和边界说明。
  - RAG 知识增强章节新增第三十八轮说明，明确推荐流程：验证 provider -> 构建索引 -> 运行 RAG Evaluation。

### 使用技术

- Embedding Provider Validation
- Semantic Provider Guard
- Dense Retrieval Probe
- InMemory VectorStore
- Cosine Similarity
- Health Check
- OpenAI-compatible Embedding 配置校验
- CLI JSON Report
- pytest TDD 回归测试

### 优化价值

- 项目不再只“有 embedding provider 代码”，而是具备独立验证入口，可以在构建索引前先确认 provider 是否真的可用。
- 默认拒绝 `local-hashing` 作为真实语义 embedding，避免简历和面试表达失真；它只适合无 API Key 时的本地开发与回归测试。
- dense probe 能模拟真实检索链路中“文档向量写入 -> 查询向量生成 -> 向量相似度排序”的最小闭环，帮助发现维度错误、空向量、provider 异常和排序异常。
- JSON 报告可以作为部署前检查结果，也能给后续 CI、Docker 启动检查或管理接口复用。
- 本机当前未配置真实 Embedding API Key，因此这一轮完成的是“生产级验证入口与边界校验”；真实外部 provider 的 live 调用需要在配置真实 Key 后执行。
- 这一轮完成剩余未完成点中的第 2 点：真实语义 Embedding 跑通前的验证链路。外部向量库接入仍保留为后续独立轮次。

## 2026-07-23 第三十九轮：Chroma VectorStore 后端接入

### 改动内容

- 调整 `rag/vector_store.py`：
  - 新增 `ChromaVectorStore`，使用 Chroma `PersistentClient` 将向量 collection 持久化到本地目录。
  - `upsert_documents()` 复用项目已有 `EmbeddingProvider.embed_texts()` 生成向量，再写入 Chroma 的 `ids`、`embeddings`、`documents` 和 `metadatas`。
  - Chroma metadata 记录 source、title、content_hash、metadata_json、embedding provider、embedding model 和 embedding dimensions。
  - 支持幂等 upsert：content hash、metadata、provider、model、dimensions 未变化时跳过重新 embedding。
  - 支持 `replace_collection=True` 删除 stale documents，避免知识库删改后旧向量继续参与召回。
  - `search()` 使用 Chroma `query_embeddings` 查询，并通过 metadata `where` 条件限定 provider/model/dimensions，避免不同 embedding 配置的向量混用。
  - 搜索结果会恢复原始 metadata，并在 evidence 中输出 `vector_store:chroma`、collection、persist_directory 和 record_id。
- 调整 `rag/retriever.py`：
  - `_create_vector_store()` 支持 `chroma`、`chromadb`、`chroma-local`。
  - `KnowledgeRetriever.default()` 可以通过 `MESSAGE_TALK_VECTOR_STORE=chroma` 切换到 Chroma 后端。
- 调整 `scripts/build_rag_index.py`：
  - `--vector-store` 新增 `chroma` 选项。
  - `--vector-db-path` 在 Chroma 模式下作为 persist directory 使用。
- 调整 `rag/__init__.py`：
  - 导出 `ChromaVectorStore`。
- 调整 `requirements.txt`：
  - 新增 `chromadb>=1.0,<2`。
- 调整 `.env.example`：
  - 补充 Chroma 本地持久化配置示例。
- 调整 `.gitignore`：
  - 新增 `data/chroma_vectors/`，避免 Chroma 本地索引目录进入代码版本管理。
- 调整 `tests/test_vector_store.py`：
  - 覆盖 Chroma 持久化搜索、metadata 恢复、幂等 upsert 和 stale document 删除。
- 调整 `tests/test_rag.py`：
  - 覆盖通过环境变量将默认 RAG 检索链路切换到 Chroma，并验证 dense retrieval Trace 中的 vector_store 为 `chroma`。
- 调整 `README.md`：
  - 快速启动部分新增 Chroma 索引构建命令。
  - RAG 知识增强章节新增 Chroma VectorStore 后端说明。
  - 技术栈补充 `Chroma VectorStore / PersistentClient / collection persistence`。

### 使用技术

- Chroma / chromadb
- PersistentClient
- Collection Persistence
- VectorStore Adapter
- Metadata Filter / where 条件
- Embedding Provider 复用
- Idempotent Upsert
- Stale Vector Cleanup
- Retrieval Evidence
- pytest TDD 回归测试

### 优化价值

- 项目从“自写 SQLite 向量表”升级为“可切换标准向量数据库后端”，RAG 工程化程度更强。
- Chroma 后端没有绕开现有 embedding 抽象，仍然由项目统一控制 local fallback 或真实 OpenAI-compatible embedding，避免 provider 分裂。
- metadata filter 让不同 embedding provider、model 和 dimensions 的向量不会混在同一个 collection 中被误召回。
- Chroma embedded 持久化适合个人项目、本地演示和轻量部署；简历中建议表述为“实现 Chroma VectorStore Adapter”，不要只写“用了 Chroma 做 RAG”。
- 这一轮完成剩余未完成点中的第 3 点：外部向量库后端接入。后续如果要进一步偏生产级，可以在同一抽象下接 Qdrant 或增加真实 Embedding live 验证。

## 2026-07-25 第四十轮：Agent Planner Evaluation 与工具计划修复机制

### 改动内容

- 调整 `agent_planner.py`：
  - 新增 `PlanValidationIssue`、`PlanRepairAction` 和 `PlanValidationReport`，统一描述工具计划校验问题、修复动作和最终校验报告。
  - 扩展 `AgentToolPlan`，新增 `validation_status`、`validation_issues`、`repair_actions`，让 API、Trace 和测试都能看到计划校验结果。
  - 新增 `PlanValidator.validate_and_repair()`，在计划进入 LangGraph 执行前进行统一校验与修复。
  - 修复策略覆盖未知工具删除、重复工具删除、`top_k` 参数清洗、缺失必需工具补回、依赖顺序重排和 sequence 重新编号。
  - 固化当前工具依赖顺序：`knowledge_retrieval -> memory_recall -> risk_analysis`，避免风险分析先于上游 RAG/Memory 上下文执行。
- 调整 `decision_engine.py`：
  - `DecisionEngine` 新增 `plan_validator` 注入点，便于测试或后续替换更严格的 planner guardrail。
  - `_plan_tools()` 现在会先生成本地 rule-based fallback plan，再接收 LLM Planner 原始计划，最后通过 `PlanValidator` 输出真正进入图执行的 repaired plan。
  - `plan_tools` Trace metadata 新增 `plan_validation`，记录原始工具顺序、修复后顺序、问题列表、修复动作和修复次数。
- 新增 `planner_evaluation.py`：
  - 新增 `PlannerEvaluationCase`、`PlannerEvaluationCheck`、`PlannerEvaluationCaseResult` 和 `PlannerEvaluationSummary`。
  - 新增 `PlannerEvaluator`，用于评估 Planner 原始选工具是否符合预期，以及修复后的计划是否满足可执行性和依赖顺序。
  - 默认评估集覆盖城市高上下文需求、山地记忆与风险需求、平原低上下文需求 3 类场景。
  - CLI 支持 `python planner_evaluation.py` 输出 JSON 报告，也支持 `--case-id` 单独运行某个评估用例。
- 调整 `schemas.py`：
  - `ToolPlanSchema` 新增 `validation_status`、`validation_issues` 和 `repair_actions` 字段，保证 FastAPI 响应契约能表达计划修复结果。
- 调整测试：
  - `tests/test_agent_planner.py` 覆盖合法计划通过校验，以及非法 LLM 计划被修复为依赖安全顺序。
  - `tests/test_decision_engine.py` 覆盖 LLM Planner 输出不完整或非法计划时，执行前会被补全、清洗、重排，并写入 Trace。
  - 新增 `tests/test_planner_evaluation.py`，覆盖默认 Planner Evaluation、失败用例检测和 CLI JSON 输出。
- 调整 `README.md`：
  - 技术栈新增 `Agent Planner Evaluation / Plan Validation / Plan Repair`。
  - 快速启动新增 `python planner_evaluation.py`。
  - Agent Tool Calling 章节新增第四十轮计划校验与修复说明。
  - 新增 “Agent Planner Evaluation 评估”章节，说明评估集、指标和与 Agent/RAG Evaluation 的边界。

### 使用技术

- Agent Planner Evaluation
- Plan Validation
- Plan Repair
- Planner Guardrail
- Tool Plan Dependency Order
- Tool Parameter Sanitization
- Fallback Planner
- Trace Observability
- CLI JSON Evaluation Report
- pytest TDD 回归测试

### 优化价值

- 这一轮把 Planner 从“生成计划后直接相信”升级为“生成计划 -> 校验计划 -> 修复计划 -> 记录修复证据 -> 再进入图执行”。
- LLM Planner 即使输出未知工具、重复工具、非法 `top_k` 或错误执行顺序，也不会直接污染后续 LangGraph 工具执行链路。
- `PlanValidator` 让工具计划具备生产系统常见的 guardrail 能力：不只依赖 Prompt 约束模型输出，而是在本地代码层做硬校验。
- `planner_evaluation.py` 让 Planner 能单独评估，不需要每次都跑完整多智能体决策流程；当工具选择逻辑变化时，可以先用轻量评估集发现回归。
- Trace 和 API 响应会暴露计划修复证据，面试时可以清楚解释“LLM 工具规划不可靠时，系统如何兜底、修复和保证执行安全”。
- 这一轮完成后，之前后续路线中的“工具计划评估、非法计划修复”已经落地；后续 Planner 方向更适合继续做执行后反思和 plan-vs-actual drift analysis。

## 2026-07-29 第四十一轮：Planner 执行闭环增强

### 改动内容

- 新增 `plan_execution_auditor.py`：
  - 新增 `PlanExecutionFinding`，用于描述工具计划执行过程中的异常或提示。
  - 新增 `PlanExecutionAudit`，统一输出计划执行审计报告。
  - 新增 `PlanExecutionAuditor.audit()`，对比 `AgentToolPlan.steps` 与实际 `ToolResult` 调用结果。
  - 审计字段包括 `planned_tools`、`actual_tools`、`skipped_tools`、`missing_tools`、`unexpected_tools`、`failed_tools`、`fallback_tools`、`sequence_match`、`plan_validation_status` 和 `repaired_before_execution`。
  - 审计状态分为：
    - `passed`：计划与实际调用一致，且工具无失败或 fallback。
    - `attention_required`：计划与实际调用一致，但存在工具失败或 fallback。
    - `drift_detected`：实际调用与修复后的计划出现缺失、额外调用或顺序偏移。
- 调整 `workflow/decision_graph.py`：
  - `DecisionGraphState` 新增 `plan_execution_audit`，用于在 LangGraph 状态中承载审计结果。
  - `snapshot()` 新增 `plan_execution_audit_status`，便于后续调试状态图执行过程。
- 调整 `decision_engine.py`：
  - `DecisionEngine` 新增 `plan_execution_auditor` 依赖注入点。
  - LangGraph 业务节点新增 `audit_tool_plan_execution`，位置在 `analyze_risk` 之后、`generate_proposals` 之前。
  - 新增 `_audit_tool_plan_execution()`，将审计报告写入 Trace metadata。
  - `DecisionResult` 新增 `plan_execution_audit` 字段。
- 调整 `serializers.py`：
  - `result_to_dict()` 新增 `plan_execution_audit` 输出，保证前端和历史记录都能保存审计报告。
- 调整 `schemas.py`：
  - `DecisionResponse` 新增 `plan_execution_audit` 字段，FastAPI 文档会展示 Planner 执行审计报告。
- 调整测试：
  - `tests/test_decision_engine.py` 覆盖正常计划执行审计、Trace 节点顺序、fallback 工具审计和 findings。
  - `tests/test_serializers.py` 覆盖 API 序列化契约中的 `plan_execution_audit`。
- 调整 `README.md`：
  - 技术栈新增 `Plan Execution Audit / plan-vs-actual consistency`。
  - Agent Tool Calling 章节新增第四十一轮执行后审计说明。
  - 更新当前 LangGraph 业务节点路径。
  - 后续 Planner 路线从“plan-vs-actual audit”推进为“planner self-reflection 和失败样例库”。

### 使用技术

- Plan Execution Audit
- Plan-vs-Actual Consistency Check
- Tool Execution Findings
- LangGraph Business Node
- Trace Observability
- FastAPI Response Contract
- pytest TDD 回归测试

### 优化价值

- Planner 不再只停留在执行前校验和修复，而是形成“计划 -> 修复 -> 执行 -> 审计”的闭环。
- 当工具实际执行结果与计划不一致时，系统可以输出结构化 `drift_detected` 结果，便于定位 Planner、条件图或工具执行层的问题。
- 当工具失败或使用 fallback 时，审计报告会给出 `attention_required`，区分“计划偏移”和“执行质量问题”。
- `audit_tool_plan_execution` 作为独立 LangGraph 业务节点存在，说明项目不是简单顺序函数，而是把 Agent 工作流中的质量检查也纳入状态图编排。
- 面试时可以把这一轮讲成生产 Agent 系统中的 planner execution audit：不仅让 LLM 规划工具，还能证明计划是否被正确执行。

## 2026-07-29 第四十二轮：RAG Grounding Evidence 证据归因增强

### 改动内容

- 新增 `grounding.py`：
  - 新增 `GroundingEvidence`，将 RAG 知识片段转换为带 `evidence_id`、title、source、score 和 content excerpt 的证据对象。
  - 新增 `ProposalGrounding`，记录每个 Agent 方案关联了哪些 RAG 证据。
  - 新增 `RiskGrounding`，记录风险分析建议关联了哪些 RAG 证据和上下文信号。
  - 新增 `GroundingReport`，统一输出 `knowledge_evidence`、`proposal_grounding`、`risk_grounding` 和 summary。
  - 新增 `GroundingBuilder.build()`，负责把 `knowledge_context`、Agent 方案和 `risk_context` 组装成 grounding report。
- 调整 `workflow/decision_graph.py`：
  - `DecisionGraphState` 新增 `grounding_evidence`。
  - `snapshot()` 新增 `grounding_status`，便于后续调试 LangGraph 状态。
- 调整 `decision_engine.py`：
  - `DecisionEngine` 新增 `grounding_builder` 依赖注入点。
  - LangGraph 业务节点新增 `build_grounding_evidence`，位于 `generate_proposals` 之后、`run_dialogue` 之前。
  - `DecisionResult` 新增 `grounding_evidence` 字段。
  - Trace 新增 `build_grounding_evidence` 事件，并把完整 grounding report 写入 metadata。
- 调整 `serializers.py` 和 `schemas.py`：
  - API 响应新增 `grounding_evidence`，历史决策记录会同步保存证据归因报告。
- 调整 `evaluation.py`：
  - 默认 Trace 检查新增 `audit_tool_plan_execution` 和 `build_grounding_evidence`。
  - 对需要 RAG 的场景新增 `grounding_evidence_present` 和 `grounding_risk_evidence_present` 检查。
  - Evaluation metrics 新增 `grounding_status`。
- 调整测试：
  - 新增 `tests/test_grounding.py`，覆盖 GroundingBuilder 的 proposal/risk evidence linking。
  - 调整 `tests/test_decision_engine.py`，覆盖 grounding evidence、Trace 节点和 workflow node。
  - 调整 `tests/test_serializers.py`，覆盖 API 序列化字段。
  - 调整 `tests/test_evaluation.py`，覆盖 Agent Evaluation 对 grounding evidence 的检查。
- 调整 `README.md`：
  - 技术栈新增 `RAG Grounding Evidence / Evidence Linking`。
  - RAG 章节新增第四十二轮证据归因说明。
  - 当前 LangGraph 业务节点路径新增 `build_grounding_evidence`。

### 使用技术

- RAG Grounding Evidence
- Evidence Attribution
- Evidence ID Linking
- Proposal Grounding
- Risk Recommendation Grounding
- LangGraph Business Node
- Trace Observability
- Agent Evaluation Check
- pytest TDD 回归测试

### 优化价值

- RAG 不再只是“召回了哪些知识片段”，而是进一步说明这些知识片段如何支撑 Agent 方案和风险建议。
- `proposal_grounding` 可以解释每个 Agent 方案引用了哪些 evidence，避免知识上下文和最终决策之间断链。
- `risk_grounding` 可以解释风险建议的知识依据，让风险分析不只是规则输出，而是有可追溯证据。
- Agent Evaluation 会检查 grounding 是否存在，确保主线从 RAG 召回到最终输出的证据链可验证。
- 面试时可以讲成：`RAG Retrieval -> GroundingBuilder -> Proposal/Risk Evidence Linking -> Trace/API`。

## 2026-07-29 第四十三轮：Evaluation 历史报告持久化

### 改动内容

- 调整 `storage.py`：
  - 新增 `evaluation_reports` SQLite 表，独立保存评估报告，不混入 `decision_records` 决策历史表。
  - 新增 `EvaluationReportSummaryRecord` 和 `EvaluationReportDetailRecord`。
  - 新增 `save_evaluation_report()`、`list_evaluation_reports()` 和 `get_evaluation_report()`。
  - 保存字段包括 `report_type`、`total_cases`、`passed_cases`、`pass_rate`、`summary_json` 和 `created_at`。
- 调整 `api_fastapi.py`：
  - `POST /api/evaluations/run` 运行 Agent Evaluation 后保存 `report_type=agent` 报告，并返回 `report_id`。
  - 新增 `POST /api/evaluations/planner/run`，运行 Planner Evaluation 并保存 `report_type=planner` 报告。
  - 新增 `POST /api/evaluations/rag/run`，运行 RAG Evaluation 并保存 `report_type=rag` 报告。
  - 新增 `GET /api/evaluations`，按 ID 倒序查询评估报告摘要，并支持 `report_type` 过滤。
  - 新增 `GET /api/evaluations/{report_id}`，查询完整评估报告 JSON。
  - 评估报告仍不写入 `/api/decisions`，保持“评估历史”和“真实决策历史”边界清晰。
- 调整测试：
  - `tests/test_storage.py` 覆盖评估报告保存、列表、详情和缺失报告。
  - `tests/test_api_fastapi.py` 覆盖 Agent/Planner/RAG Evaluation 报告持久化和查询。
- 调整 `README.md`：
  - 访问列表新增 `/api/evaluations`。
  - Agent Evaluation 章节新增评估报告历史持久化说明。
  - 后续路线把“评估报告持久化”更新为“评估报告对比分析和 CI 回归”。

### 使用技术

- SQLite Evaluation Report Store
- JSON Report Persistence
- FastAPI Evaluation History API
- Agent Evaluation / Planner Evaluation / RAG Evaluation
- Report Type Filter
- pytest TDD 回归测试

### 优化价值

- Evaluation 从“命令行一次性输出”升级为“可保存、可查询、可回溯”的质量报告系统。
- Agent、Planner、RAG 三类评估报告使用同一张表和统一 API 查询，形成更完整的 AI Agent 质量验证闭环。
- 评估报告与决策历史分表保存，避免把测试/回归报告混入真实业务决策记录。
- 面试时可以讲成：项目不仅有 Agent/RAG/Planner Evaluation，还把评估结果持久化，支持后续回归对比和 CI 集成。

## 2026-07-30 第四十四轮：Qwen Embedding Live 接入验证

### 改动内容

- 读取本机环境变量时只验证 `DASHSCOPE_API_KEY` 是否存在，不在终端或文档中输出密钥内容。
- 使用现有 `OpenAICompatibleEmbeddingProvider` 对 DashScope OpenAI-compatible embedding 接口进行真实 live 验证。
- 验证模型为 `text-embedding-v4`，base URL 为 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- 通过 live 调用确认当前返回向量维度为 `1024`，修正 README 中此前 `1536` 的示例参数。
- 更新 `.env.example`，补充 Qwen `text-embedding-v4` 的维度提示。
- 扩展 `tests/test_settings.py`，明确 `MESSAGE_TALK_EMBEDDING_API_KEY` 未单独设置时，embedding 配置会复用 `DASHSCOPE_API_KEY`。

### 使用技术

- DashScope Qwen Embedding
- OpenAI-compatible Embeddings API
- Environment Variable Secret Handling
- Embedding Provider Health Check
- Dense Probe
- pytest 配置回归测试

### 优化价值

- 项目从“预留真实 embedding provider”推进为“真实 Qwen Embedding provider 已在本机跑通”。
- 文档中的向量维度与真实接口返回一致，避免构建索引时出现 `expected 1536, got 1024` 的维度错误。
- 通过 `DASHSCOPE_API_KEY` fallback 说明，减少重复配置成本；后续如果需要拆分聊天模型和 embedding 模型，也可以单独设置 `MESSAGE_TALK_EMBEDDING_API_KEY`。
- 面试时可以把这一轮讲成真实语义向量接入验证：`EmbeddingProvider -> DashScope-compatible API -> health_check -> dense_probe -> RAG index readiness`。

## 2026-07-30 第四十五轮：Qwen 免费 Embedding 模型切换

### 改动内容

- 将 README 中真实 embedding 验证命令的推荐模型从 `text-embedding-v4` 调整为当前可免费使用的 `qwen3.7-text-embedding`。
- 将 README 中生产化环境变量示例同步调整为 `MESSAGE_TALK_EMBEDDING_MODEL=qwen3.7-text-embedding`。
- 更新 `.env.example` 注释，明确 `qwen3.7-text-embedding` 经 DashScope OpenAI-compatible API live 验证为 `1024` 维。
- 在 `.env.example` 中补充 Qwen 语义检索 profile，包含 provider、model、dimensions、vector db path、collection 和 strict mode。
- 调整 `tests/test_settings.py` 中 embedding runtime option 用例，使用当前推荐模型名保护配置读取行为。
- 使用现有 `scripts/validate_embedding_provider.py` 对 `qwen3.7-text-embedding` 执行真实 provider 验证。
- 使用 `scripts/build_rag_index.py` 构建独立 SQLite 语义向量索引，写入 `data/rag_qwen_vectors.db` 的 `tactical_knowledge_qwen_free` collection，避免覆盖默认本地 fallback 索引。

### 使用技术

- DashScope Qwen 免费 Embedding 模型
- OpenAI-compatible Embeddings API
- Embedding Health Check
- Dense Retrieval Probe
- 配置文档同步
- pytest 配置回归测试

### 优化价值

- 项目当前推荐路线与真实可用的免费模型保持一致，避免文档推荐不可用或计费不合适的模型。
- `qwen3.7-text-embedding` 已通过真实 API 调用验证，返回 `1024` 维向量，可以直接作为后续 RAG 语义向量索引的 provider。
- Qwen 语义向量索引已构建到独立 SQLite 数据库，后续服务只需切换环境变量即可使用真实 semantic dense retrieval。
- dense probe 命中预期知识片段，说明 provider 不只是接口连通，而是能支撑当前知识库的语义检索验证流程。

## 2026-07-30 第四十六轮：默认 LLM 模型切换为 qwen3.7-plus

### 改动内容

- 将 `settings.py` 中默认文本生成模型从 `qwen-plus` 调整为 `qwen3.7-plus`。
- 将 `.env.example` 中的 `MESSAGE_TALK_MODEL` 示例同步调整为 `qwen3.7-plus`。
- 更新 README 的 LLM 配置示例，并补充当前推荐模型组合：
  - LLM 裁决和 LLM Planner 使用 `qwen3.7-plus`。
  - RAG Dense Retrieval 使用 `qwen3.7-text-embedding`。
  - `damo`/通义实验室作为模型来源说明，不作为 API 调用时的 `model` 字段。
- 扩展 `tests/test_settings.py`，新增默认 LLM 模型回归测试，防止后续误改回旧模型。
- 使用 DashScope OpenAI-compatible `chat/completions` 接口对 `qwen3.7-plus` 执行真实 live 验证。

### 使用技术

- DashScope Qwen3.7 Plus
- OpenAI-compatible Chat Completions API
- LangChain OpenAI-compatible client 配置
- 环境变量配置管理
- pytest 回归测试

### 优化价值

- 项目的 LLM 裁决、LLM Planner 默认模型与当前推荐 Qwen3.7 Plus 路线对齐。
- 通过 live 调用验证 `qwen3.7-plus` 可被当前 DashScope key 正常调用，避免只在文档层面“看起来能用”。
- 将聊天模型和 embedding 模型的职责分清：`qwen3.7-plus` 负责生成、裁决和工具规划，`qwen3.7-text-embedding` 负责语义向量检索。

## 2026-07-30 第四十七轮：本机 Qwen 语义检索环境变量配置

### 改动内容

- 将 Windows 用户级环境变量 `MESSAGE_TALK_BASE_URL` 配置为 DashScope OpenAI-compatible 地址。
- 将 Windows 用户级环境变量 `MESSAGE_TALK_MODEL` 配置为 `qwen3.7-plus`。
- 将 Windows 用户级环境变量 `MESSAGE_TALK_EMBEDDING_PROVIDER` 配置为 `openai-compatible`。
- 将 Windows 用户级环境变量 `MESSAGE_TALK_EMBEDDING_MODEL` 配置为 `qwen3.7-text-embedding`。
- 将 Windows 用户级环境变量 `MESSAGE_TALK_EMBEDDING_BASE_URL` 配置为 DashScope OpenAI-compatible 地址。
- 将 Windows 用户级环境变量 `MESSAGE_TALK_EMBEDDING_DIMENSIONS` 配置为 `1024`。
- 将 Windows 用户级环境变量 `MESSAGE_TALK_VECTOR_STORE` 配置为 `sqlite`。
- 将 Windows 用户级环境变量 `MESSAGE_TALK_VECTOR_DB_PATH` 配置为 `data/rag_qwen_vectors.db`。
- 将 Windows 用户级环境变量 `MESSAGE_TALK_VECTOR_COLLECTION` 配置为 `tactical_knowledge_qwen_free`。
- 将 Windows 用户级环境变量 `MESSAGE_TALK_RAG_STRICT_EMBEDDING` 配置为 `true`。
- 未写入或打印任何 API Key；项目继续复用用户级 `DASHSCOPE_API_KEY`。

### 使用技术

- Windows User Environment Variables
- DashScope OpenAI-compatible Base URL
- Qwen3.7 Plus LLM 配置
- Qwen3.7 Text Embedding 配置
- SQLite VectorStore Profile
- Strict Semantic Embedding Mode

### 优化价值

- 新开的终端可以直接读取 Qwen LLM 与 Qwen Embedding 配置，不需要每次手动设置临时 `$env:`。
- 项目默认运行路线从本地 fallback 切换为真实 Qwen 语义检索 profile。
- `MESSAGE_TALK_RAG_STRICT_EMBEDDING=true` 可以防止 embedding 失败时静默退回本地 fallback，更适合面试演示真实 RAG 能力。
- 配置与前面构建好的 `data/rag_qwen_vectors.db` 独立语义索引对齐。

## 2026-07-30 第四十八轮：项目测试文档建设

### 改动内容

- 新增 `TESTING.md`，系统整理项目测试目标、测试环境、测试分层、常用命令、最近一次验证结果、部署前检查清单和面试解释口径。
- 测试文档围绕主线展开：`Qwen Embedding -> RAG 知识增强 -> Agent 工具规划 -> LangGraph 执行 -> Trace 可观测 -> Evaluation 验证质量`。
- 将测试分层拆为配置与基础设施、FastAPI 接口、Agent 决策引擎、Planner 工具规划、RAG 检索与向量索引、Grounding 证据归因、MCP 工具测试。
- 在 README 的测试章节补充 `TESTING.md` 引导，避免 README 测试段落继续膨胀。
- 将最近一次测试结果写入测试文档，包括 `98 passed`、Agent Evaluation `3/3`、Planner Evaluation `3/3`、Qwen RAG Evaluation `5/5` 和 Qwen LLM 集成验证。

### 使用技术

- pytest 测试体系文档化
- Agent Evaluation / Planner Evaluation / RAG Evaluation
- Qwen live provider validation
- RAG 语义索引验证
- 部署前检查清单
- 面试项目表达整理

### 优化价值

- 项目从“有测试”升级为“测试体系可解释、可复现、可展示”。
- 面试官可以直接通过 `TESTING.md` 理解项目如何验证 RAG、Agent Planner、LangGraph、Trace、Evaluation 和 Qwen 模型接入。
- 后续每一轮优化都可以把验证命令和结果追加到测试文档，形成持续回归记录。

## 2026-07-30 第四十九轮：Chroma HTTP 向量数据库服务化

### 改动内容

- 将 `chromadb` Python 客户端和 Docker Server 固定为稳定版 `1.5.9`，避免客户端与服务端协议版本漂移。
- 扩展 `AppSettings`，新增 `MESSAGE_TALK_CHROMA_MODE`、`MESSAGE_TALK_CHROMA_HOST`、`MESSAGE_TALK_CHROMA_PORT`、`MESSAGE_TALK_CHROMA_SSL`。
- 将 `ChromaVectorStore` 从仅支持 `PersistentClient` 扩展为同时支持 `PersistentClient` 与 `HttpClient`。
- Chroma HTTP 模式初始化时执行 heartbeat；连接失败时返回包含 mode 和 endpoint 的明确错误，但不包含 API Key。
- Chroma 检索 evidence 与 stats 新增 `chroma_mode` 和 endpoint，Trace 可以证明 Dense Retrieval 实际经过独立 Chroma 服务。
- `KnowledgeRetriever.default()` 与 `scripts/build_rag_index.py` 已接通 Chroma HTTP 配置。
- 索引 CLI 新增 `--chroma-mode`、`--chroma-host`、`--chroma-port`、`--chroma-ssl/--no-chroma-ssl`。
- `docker-compose.yml` 新增 `chromadb/chroma:1.5.9` 服务，主机端口为 `8001`，避免与 FastAPI `8000` 冲突。
- Compose 中的 FastAPI 服务显式使用 Qwen Embedding 1024 维配置，并仅从运行环境透传 `DASHSCOPE_API_KEY`，避免本地 fallback 与 Qwen collection 维度不一致。
- Chroma `/data` 绑定到 `D:\BaiduNetdiskDownload\message_talk_chroma_data`，容器重建后向量集合仍然保留。
- Chroma 主机端口仅绑定 `127.0.0.1:8001`，避免无认证的本地向量服务暴露到局域网。
- Compose 健康检查通过 Bash TCP 发起真实 `/api/v2/heartbeat` 请求并校验 HTTP 200；`message-talk` 等待 Chroma healthy 后再启动。
- FastAPI 容器新增 `/api/health` 健康检查，能够分别观察应用服务与向量数据库服务状态。
- Windows 用户级 VectorStore 配置已切换为 Chroma HTTP，继续复用既有 Qwen Embedding 配置和 `DASHSCOPE_API_KEY`。
- D 盘项目 `.venv` 已安装完整项目依赖，`chromadb` 实际位置为项目 `.venv\Lib\site-packages`。
- 新增 Chroma 配置、HTTP 客户端、离线错误、工厂传参和 CLI 参数测试。
- `tests/conftest.py` 新增测试环境隔离 fixture，单元测试固定使用 `local-hashing`、临时 SQLite 和测试 collection，避免用户级 Qwen/Chroma 配置触发真实网络调用。
- 新增设计文档与实施计划：
  - `docs/superpowers/specs/2026-07-30-chroma-http-vector-store-design.md`
  - `docs/superpowers/plans/2026-07-30-chroma-http-vector-store.md`

### 使用技术

- ChromaDB 1.5.9
- Chroma HttpClient / PersistentClient
- Docker Compose 服务编排
- D 盘 bind mount 持久化
- HTTP heartbeat / Docker healthcheck
- Qwen `qwen3.7-text-embedding`
- 1024 维语义向量
- HNSW cosine collection
- Metadata filter
- Idempotent Upsert / Content Hash Deduplication
- pytest TDD
- Windows User Environment Variables

### 验证结果

- `python -m pytest -q`：`104 passed`。
- `pip check`：`No broken requirements found`。
- `docker compose config`：通过。
- Chroma 容器：`chromadb/chroma:1.5.9`，`localhost:8001`，状态 `healthy`。
- FastAPI 应用镜像构建通过，`/api/health` 返回 `ok=true`，容器内连接 `chroma:8000` 并读取到 7 条向量记录。
- Chroma heartbeat：`/api/v2/heartbeat` 返回成功。
- Qwen Chroma 首次索引：`documents_loaded=7`、`upserted=7`、`document_count=7`。
- Qwen Chroma 幂等重建：`upserted=0`、`skipped=7`、`deleted=0`、`total=7`。
- Embedding：`provider=openai-compatible`、`model=qwen3.7-text-embedding`、`dimensions=1024`、`health.ok=true`。
- Chroma RAG Evaluation：`5/5 passed`、`hit_at_k=1.0`、`MRR=1.0`、`nDCG=1.0`、`source_match_rate=1.0`。
- D 盘持久化目录生成 `chroma.sqlite3` 和 HNSW collection 数据目录。

### 优化价值

- RAG 向量索引从应用进程内本地文件升级为独立 HTTP 数据服务，FastAPI、索引脚本和 MCP/Agent 检索可以共享同一 collection。
- Docker 容器生命周期与向量数据生命周期分离，能够演示服务发现、健康依赖、持久卷、失败检测和客户端连接配置。
- 保留 SQLite 和 Chroma Persistent 模式，测试、离线开发与服务化演示仍可按环境切换。
- 项目主线更新为：`Qwen Embedding -> Chroma HTTP VectorStore -> Hybrid RAG -> Agent Planner -> LangGraph -> Trace -> Evaluation`。

## 2026-07-30 第五十轮：RAG 领域知识库与检索基准扩容

### 改动内容

- 将原有单文件 `tactical_knowledge.md` 重构为 12 个职责独立的中文主题知识文件。
- 知识主题覆盖地形场景、情报侦察、通信指挥、资源补给、多智能体协作、风险约束、异常处置、评估指标、决策流程、故障恢复、工具治理和复合案例。
- 每个主题文件包含 5 个全局唯一的二级标题语义单元，共 60 个 Chunk。
- 每个知识单元明确适用条件、系统行为、安全限制和可观测评估证据，内容均为虚构仿真语料。
- 默认 RAG Evaluation 从 5 条扩展为 30 条：8 条直接检索、7 条中文改写、6 条复合查询、5 条相似主题区分和 4 条跨文档关联。
- 新增 `tests/test_knowledge_corpus.py`，锁定源文件数、Chunk 范围、标题唯一性和 Metadata 完整性。
- 扩展 `tests/test_rag_evaluation.py`，验证评测 ID、类别数量、预期标题和源文件。
- 4 条 `cross_` 用例升级为强制同时命中两个标题和两个不同源文件，不再只依赖名称前缀表示跨文档。
- 新增 RAG Evaluation Quality Gate：全部用例通过且 Hit@3、MRR、nDCG 和 Source Match 达标时 CLI 才返回退出码 0。
- 新增纯 BM25 难度基线，限制语义改写题不能仅靠词面检索轻易满分。
- 修复 pytest 收集阶段的环境隔离：导入 MCP Server 前即启用 local-hashing 与临时 SQLite，Chroma 停止时也能运行测试。
- 真实索引发现 Qwen 在单批 32 条长文本时返回 HTTP 400；最小复现确认批次 8 可稳定完成 60 条索引。
- 将默认 `MESSAGE_TALK_EMBEDDING_BATCH_SIZE` 从 32 调整为 8，并同步配置模板、Compose、README 和 Windows 用户级环境变量。
- 修复 `.env.example` 与 Docker Compose 的 API Key 透传契约，Compose 同时接受 `DASHSCOPE_API_KEY`、`MESSAGE_TALK_API_KEY` 和独立 Embedding Key。
- 新增中文设计与计划文档：
  - `docs/superpowers/specs/2026-07-30-rag-knowledge-base-expansion-design.md`
  - `docs/superpowers/plans/2026-07-30-rag-knowledge-base-expansion.md`

### 使用技术

- Markdown Heading-aware Chunking
- 900 字符 Chunk 上限 / 120 字符 Overlap 兜底
- Corpus Contract Test / Evaluation Dataset Contract Test
- Qwen `qwen3.7-text-embedding` / 1024 维 Dense Embedding
- Chroma HTTP VectorStore
- BM25 + Dense Retrieval + RRF Fusion + Rerank
- Retrieval Trace / Fusion Evidence / Rerank Evidence
- Hit@3 / MRR / nDCG@3 / Source Match Rate
- Content Hash 幂等 Upsert / Stale Vector Cleanup
- pytest 收集阶段环境隔离

### 验证结果

- 知识库规模：12 个 Markdown 文件、60 个知识单元、60 条 Chroma 向量。
- 首次扩容构建：`upserted=60`、`deleted=7`、`total=60`。
- 幂等重建：`upserted=0`、`skipped=60`、`deleted=0`、`total=60`。
- Embedding：`provider=openai-compatible`、`model=qwen3.7-text-embedding`、`dimensions=1024`、`batch_size=8`。
- VectorStore：`store=chroma`、`mode=http`、`endpoint=http://localhost:8001`、`collection=tactical_knowledge_qwen_free`。
- 纯 BM25 全量基线：26/30 通过、`hit_at_k=0.8667`、`MRR=0.8611`、`nDCG=0.8629`。
- 纯 BM25 语义改写基线：4/7 通过、`hit_at_k=0.5714`、`MRR=0.4762`、`nDCG=0.5`。
- Qwen Chroma 在线 RAG Evaluation：30/30 通过、`hit_at_k=1.0`、`MRR=0.9611`、`nDCG=0.9684`、`source_match_rate=1.0`。
- 在线质量门：通过，`average_rerank_improvement=0.0333`，无失败项。
- `python -m pytest -q`：`110 passed`。

### 优化价值

- 知识库从链路验证样本升级为具有主题重叠、中文改写、复合约束和跨文档查询的领域语料集。
- 评测不再依赖少量接近原文的查询，可以更真实地衡量 Hybrid Search 和 Rerank。
- Corpus Contract 与 Evaluation Contract 能阻止后续误删文档、标题漂移和失效评测。
- 在线实测暴露并修复批量 Embedding 限制，索引构建从小样本可运行提升为中等规模稳定运行。

## 2026-07-31 第五十一轮：实习面试项目介绍与问答文档

### 改动内容

- 新增 `docs/实习面试项目介绍与问答.md`，用于 AI 应用开发、Python 后端和 RAG 方向实习面试。
- 提供 30 秒、3 分钟项目介绍和两种简历项目描述，统一项目名称、技术主线和实测数据口径。
- 使用 Mermaid 描述 FastAPI、Agent Planner、LangGraph、RAG、MCP、Trace 和 Evaluation 的整体关系。
- 按真实代码整理 5 个策略智能体、3 个 Agent 工具、13 个 LangGraph 业务节点和完整请求流程。
- 编写 52 个项目相关面试问题与参考回答，覆盖架构、RAG、Tool Calling、MCP、LangGraph、SSE、FastAPI、Docker、测试和工程边界。
- 补充代码现场讲解顺序、3～5 分钟演示脚本、面试诚实边界、后续优化路线和面试前检查清单。
- 明确区分已实现能力与未完成能力，避免把持久 Checkpoint、大规模生产部署、完整鉴权和高并发压测描述成当前成果。

### 文档核对依据

- 策略智能体：5 个。
- Agent 工具：3 个。
- LangGraph 业务节点：13 个。
- 知识库：12 个文件、60 个 Chunk。
- RAG Evaluation：30 条。
- Qwen Chroma：Hit@3=1.0、MRR=0.9611、nDCG@3=0.9684。
- 自动化测试：110 passed。

### 优化价值

- 将分散在 README、代码和优化日志中的信息整理成可直接用于简历、项目介绍、技术追问和现场演示的统一材料。
- 面试回答同时包含实现原理、项目代码落点、真实数据和不足边界，降低只会背技术名词但无法结合项目解释的风险。

## 当前验证状态

最近一次验证命令：

```text
python -m py_compile workflow/__init__.py workflow/decision_graph.py agent_planner.py agents.py api_server.py api_fastapi.py decision_auditor.py decision_engine.py evaluation.py grounding.py planner_evaluation.py plan_execution_auditor.py rag_evaluation.py embedding_validation.py llm_coordinator.py logging_config.py main.py mcp_server.py memory.py models.py schemas.py serializers.py settings.py standards.py storage.py trace.py rag/__init__.py rag/embeddings.py rag/ingestion.py rag/vector_store.py rag/retriever.py tools/base.py tools/registry.py tools/knowledge_tool.py tools/memory_tool.py tools/risk_tool.py scripts/build_rag_index.py scripts/validate_embedding_provider.py
python -m pytest -q
node --check frontend/app.js
python evaluation.py
python planner_evaluation.py
python rag_evaluation.py
python scripts/build_rag_index.py --skip-health-check
python scripts/build_rag_index.py --vector-store chroma --vector-db-path data/chroma_vectors --skip-health-check
python scripts/validate_embedding_provider.py --embedding-provider local-hashing --embedding-model local-hashing-v1 --embedding-dimensions 32 --allow-local-fallback
python scripts/validate_embedding_provider.py --embedding-provider local-hashing --embedding-model local-hashing-v1 --embedding-dimensions 32
python scripts/validate_embedding_provider.py --embedding-provider openai-compatible --embedding-model qwen3.7-text-embedding --embedding-api-key $env:DASHSCOPE_API_KEY --embedding-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --embedding-dimensions 1024
python scripts/build_rag_index.py --embedding-provider openai-compatible --embedding-model qwen3.7-text-embedding --embedding-api-key $env:DASHSCOPE_API_KEY --embedding-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --embedding-dimensions 1024 --vector-store chroma --chroma-mode http --chroma-host localhost --chroma-port 8001 --no-chroma-ssl --collection tactical_knowledge_qwen_free --strict
DashScope OpenAI-compatible chat/completions live probe: model=qwen3.7-plus
Windows 用户级环境变量检查：Qwen LLM、Qwen Embedding、Chroma HTTP VectorStore 和 strict mode 均已配置。
```

最近一次测试结果：

```text
py_compile 通过。
python -m pytest -q -p no:cacheprovider：141 passed。
pip check：No broken requirements found。
node --check frontend/app.js：通过。
Agent Evaluation 验证通过：`python evaluation.py` 返回 total_cases=3、passed_cases=3、pass_rate=1.0、average_score=100.0。
Agent Planner Evaluation 验证通过：`python planner_evaluation.py` 返回 total_cases=3、passed_cases=3、pass_rate=1.0、tool_match_rate=1.0、average_repair_count=0.0。
RAG Evaluation 验证通过：`python rag_evaluation.py` 返回 total_cases=30、passed_cases=30、hit_at_k=1.0、mean_reciprocal_rank=0.9611、mean_ndcg=0.9684、source_match_rate=1.0、average_rerank_improvement=0.0333、quality_gate.passed=true。
Qwen Chroma HTTP 语义索引扩容通过：documents_loaded=60、upserted=60、deleted=7、document_count=60、health.ok=true。
Qwen Chroma 幂等重建通过：upserted=0、skipped=60、deleted=0、total=60。
Embedding Provider 本地探针验证通过：`python scripts/validate_embedding_provider.py --embedding-provider local-hashing --embedding-model local-hashing-v1 --embedding-dimensions 32 --allow-local-fallback` 返回 ok=true，dense_probe.top_title 命中 `Urban Civilian Risk Control`。
Embedding Provider 语义边界校验通过：不带 `--allow-local-fallback` 时返回 ok=false、退出码为 1，并提示 `local-hashing` 不是真实语义 embedding，需要配置 `openai-compatible`。
RAG Grounding Evidence 验证通过：`tests/test_grounding.py`、`tests/test_decision_engine.py`、`tests/test_serializers.py` 和 `tests/test_evaluation.py` 已覆盖 evidence linking、Trace 节点、API 字段和 Agent Evaluation grounding 检查。
Evaluation 历史报告持久化验证通过：`tests/test_storage.py` 和 `tests/test_api_fastapi.py` 已覆盖 `evaluation_reports` 表、Agent/Planner/RAG 报告保存、列表查询和详情查询。
Qwen Embedding live 验证通过：`qwen3.7-text-embedding` 经 DashScope OpenAI-compatible API 返回 dimensions=1024，dense_probe.top_title 命中 `Urban Civilian Risk Control`，top_score=0.8559，provider.is_semantic=true。
Qwen Embedding 批次验证通过：batch_size=32 时服务返回 HTTP 400，batch_size=8 时 60 条语料成功建立 1024 维索引；默认安全批次已调整为 8。
Qwen LLM live 验证通过：`qwen3.7-plus` 经 DashScope OpenAI-compatible chat/completions 接口返回预期 JSON，finish_reason=stop。
本机用户级环境变量配置验证通过：`get_settings()` 读取到 base_url=`https://dashscope.aliyuncs.com/compatible-mode/v1`、model=`qwen3.7-plus`、embedding_model=`qwen3.7-text-embedding`、vector_store=`chroma`、chroma_mode=`http`、chroma_host=`localhost`、chroma_port=8001、collection=`tactical_knowledge_qwen_free`、rag_strict_embedding=true。
新增 MCP Knowledge Hub 测试通过：`query_knowledge_hub`、`list_knowledge_collections`、`get_retrieval_trace` 均已被 FastMCP 工具列表和直接函数调用覆盖。
Docker Chroma 验证通过：`chromadb/chroma:1.5.9` 容器状态 healthy，主机 `http://localhost:8001/api/v2/heartbeat` 返回成功，数据写入 `D:\BaiduNetdiskDownload\message_talk_chroma_data`。
```

## 当前主要技术栈

- Python
- FastAPI
- Pydantic
- SQLite
- LangChain OpenAI-compatible client
- DashScope Qwen3.7 Plus
- pytest
- Python logging
- Decision Trace
- Request ID 链路追踪
- RAG / BM25 风格关键词检索
- RAG Query Rewrite / Rerank / Retrieval Evidence
- Modular RAG Query Pipeline
- EmbeddingProvider / OpenAI-compatible Embedding 预留
- DashScope Qwen Embedding / qwen3.7-text-embedding
- OpenAI-compatible Embeddings API / httpx
- Embedding Health Check / Strict Mode
- Embedding Provider Validation / Semantic Guard / Dense Probe
- CLI JSON Validation Report
- Local Hashing Embedding Fallback
- InMemory VectorStore / Cosine Similarity
- SQLite VectorStore / Persistent Vector Index
- Chroma VectorStore / PersistentClient / HttpClient / Docker Service
- VectorStore Backend Adapter
- Idempotent Upsert / Content Hash Deduplication
- RAG Index Build CLI
- Markdown Ingestion Pipeline
- Ingestion History / File Hash Deduplication
- Chunk Metadata Extraction
- Dense Retrieval Route
- RRF 多路候选融合
- Retrieval Trace / Fusion Evidence
- Direct RAG Query Trace
- Query-level Rerank
- RAG Grounding Evidence / Evidence Attribution
- Proposal Grounding / Risk Recommendation Grounding
- Agent Context
- Agent Memory / 长期记忆写入 / 历史案例相似度召回
- Agent Tool Calling / Tool Registry
- Tool Schema / Tool Discovery
- MCP Python SDK / FastMCP / MCP Server
- MCP Knowledge Hub Tools
- MCP Resource
- Agent Evaluation / Scenario-based Regression Report
- RAG Evaluation / hit@k / MRR / nDCG
- Agent Planner Evaluation / Tool Selection Match
- Evaluation Report Persistence
- Plan Validation / Plan Repair / Planner Guardrail
- Plan Execution Audit / Plan-vs-Actual Consistency
- Tool Parameter Sanitization
- Expected Source Match / Rerank Improvement
- Plan-and-Execute / Agent Tool Plan
- LangGraph / StateGraph / Conditional Edges
- Conditional Tool Selection / Conditional Workflow
- Tool Selection Scoring / Threshold-based Routing
- Conditional Graph Node / Skip Hook
- LLM Planner / Tool Plan Validation / Local Rule Fallback
- Tool Dependency DAG / Context Passing / Context-aware Risk Analysis
- Reflection Agent / Critic Agent / Decision Audit
- Tool Retry / Fallback Strategy / Tool Metrics
- 风险分析工具
- Docker / Docker Compose
- HTML / CSS / JavaScript

## 当前项目结构变化摘要

新增或重点优化文件：

- `api_fastapi.py`：新版 FastAPI API 入口。
- `embedding_validation.py`：Embedding Provider 验证入口、语义 provider 边界校验和 dense probe。
- `evaluation.py`：Agent Evaluation 场景集、指标检查和回归报告。
- `grounding.py`：RAG evidence 与 Agent 方案、风险建议之间的证据归因和 grounding report。
- `planner_evaluation.py`：Agent Planner Evaluation 工具计划评估集、修复指标和 CLI JSON 报告。
- `rag_evaluation.py`：RAG 检索质量评估集、hit@k、MRR、nDCG、source match 和 rerank improvement 报告。
- `mcp_server.py`：基于 FastMCP 的真实 MCP Server 工具入口与 Knowledge Hub 工具入口。
- `schemas.py`：请求、响应和错误结构定义。
- `serializers.py`：统一对象转 JSON 的序列化逻辑。
- `settings.py`：统一配置管理。
- `logging_config.py`：统一日志配置。
- `storage.py`：SQLite 历史决策记录、长期记忆条目与 Evaluation 报告存储。
- `trace.py`：决策流程 Trace 事件模型。
- `agent_planner.py`：Agent 工具调用规划、Plan-and-Execute 计划结构、Plan Validation 和 Plan Repair。
- `plan_execution_auditor.py`：Planner 计划与实际工具调用一致性审计，输出 missing、unexpected、failed、fallback 和 sequence match 指标。
- `rag/embeddings.py`：EmbeddingProvider 抽象、local-hashing fallback 和 OpenAI-compatible provider 预留。
- `rag/ingestion.py`：Markdown Ingestion Pipeline、文件 hash、chunk metadata 和 SQLite ingestion history。
- `rag/vector_store.py`：InMemory/SQLite/Chroma VectorStore、向量记录、持久化索引、幂等 upsert、metadata filter 和 cosine similarity 检索。
- `rag/retriever.py`：RAG Query Pipeline、direct query trace、BM25、Dense route、Scene Signal route、RRF 融合和 Rerank。
- `scripts/build_rag_index.py`：RAG 向量索引构建脚本。
- `scripts/validate_embedding_provider.py`：Embedding Provider 命令行验证脚本，输出 JSON 报告并区分真实语义 provider 与本地 fallback。
- `workflow/`：基于 LangGraph StateGraph 的状态图节点与工作流编排。
- `tools/`：Agent 工具注册、工具调用结果和工具实现。
- `tests/test_embeddings.py`：OpenAI-compatible embedding provider 的 batch、health check 和维度校验测试。
- `tests/test_vector_store.py`：SQLite vector store 持久化、幂等 upsert 和 stale cleanup 测试。
- `tests/test_vector_store.py`：Chroma vector store 持久化、metadata 恢复、幂等 upsert 和 stale cleanup 测试。
- `tests/test_ingestion.py`：Markdown ingestion metadata、文件去重和 chunk split 测试。
- `tests/test_rag_evaluation.py`：RAG Evaluation 默认用例、指标函数、失败报告和 CLI 输出测试。
- `tests/test_planner_evaluation.py`：Agent Planner Evaluation 默认用例、失败检测和 CLI 输出测试。
- `tests/test_grounding.py`：RAG Grounding Evidence 的 proposal/risk evidence linking 测试。
- `tests/test_embedding_validation.py`：Embedding Provider 验证、dense probe、fallback 边界和 CLI 输出测试。
- `Dockerfile`：容器镜像构建配置。
- `docker-compose.yml`：容器编排启动配置。
- `scripts/`：本地启动脚本。
- `tests/`：pytest 测试目录。
- `README.md`：项目说明文档。
- `.env.example`：环境变量模板。
- `.gitignore`：版本管理忽略规则。
- `OPTIMIZATION_LOG.md`：项目技术优化记录。

## 后续可继续优化方向

- 已完成 Qwen Embedding live provider 验证；下一步可用真实语义向量刷新 SQLite/Chroma RAG 索引，并对比本地 fallback 与真实 embedding 的检索质量。
- 扩大 RAG Evaluation：增加中文自然语言查询、噪声文档、跨文件检索和 TopK 敏感性测试。
- 深化 Memory：补充记忆质量评估、去重压缩、过期策略和召回排序优化。
- 深化 Planner：补充 planned tools 与 actual tool calls 的执行后对比，以及 planner self-reflection。

## 2026-08-04 第五十二轮：并行 LLM Strategy Agent 与单角色 Fallback

### 本轮目标

将原有 5 个规则型候选方案生成器升级为 5 个真正独立调用 Qwen 的角色化 Strategy Agent，同时保留原规则实现作为指标基线和单角色 fallback，使项目从“规则多 Agent + LLM 统一评审”升级为“LLM Planner + 并行 LLM Strategy Agents + Reviewer”。

### 主要改动

- 新增 `llm_strategy_agents.py`：
  - 定义强攻、迂回、防御、诱骗、火力压制 5 份独立角色 Profile。
  - 通过同一 `qwen3.7-plus` 模型并行执行 5 次角色推理。
  - 使用 Pydantic `extra="forbid"` 校验模型 JSON，约束摘要、行动列表、推理依据、证据引用、指标调整和置信度。
  - 指标采用“规则基线 + LLM `[-10, 10]` 有限调整”，最终约束在 `[0, 100]`。
  - 知识标题和 Memory ID 必须来自上游实际提供的白名单，防止模型伪造证据。
  - 使用 `ThreadPoolExecutor` 实现最多 5 路并发，并在汇总阶段恢复固定 Agent 顺序。
  - `auto` 模式只降级失败 Agent；`on` 模式聚合失败并终止请求；`off` 模式不调用模型。
- `llm_coordinator.py` 新增窄接口 `generate_strategy_payload()`，只负责消息发送和 JSON 对象提取，角色级错误隔离由并发 Runner 统一处理。
- `models.py` 新增 `AgentGenerationRecord`，记录模型、生成模式、耗时、校验状态、fallback 原因、证据和指标调整。
- `decision_engine.py` 将并发 Runner 接入 `generate_proposals` 节点，并把 RAG、Memory、Risk Context 直接传入每个角色 Agent。
- `workflow/decision_graph.py` 新增 `agent_generation_records` 状态字段。
- `serializers.py`、`schemas.py` 和 FastAPI 响应新增 `agent_generation` 字段，保持原请求接口与 SSE 事件名称兼容。
- 新增 `MESSAGE_TALK_AGENT_MAX_WORKERS`，默认值和上限为 5；`.env.example` 与 Docker Compose 已同步。
- 完成独立审查后的边界加固：
  - Action 列表先清洗空项，再校验 2～6 项；置信度统一截断到 `[0.2, 1.0]`。
  - 指标调整显式拒绝 `NaN`、`Infinity` 等非有限数值，避免污染规则基线。
  - 失败 Agent 的耗时改为在线程任务内部统计，不包含线程池排队时间。
  - `on` 严格模式通过 FastAPI 与 SSE 返回失败角色、模型、耗时和 fallback 原因等结构化详情。
  - `DecisionResult.agent_generation_records` 增加空列表默认值，保持内部构造兼容。
- 新增设计文档与实施计划：
  - `docs/superpowers/specs/2026-08-04-parallel-llm-strategy-agents-design.md`
  - `docs/superpowers/plans/2026-08-04-parallel-llm-strategy-agents.md`

### 模式语义

```text
off  -> 5 个规则 Agent，0 次 Strategy Agent 模型调用
auto -> 5 个 Qwen Agent 并行调用，单个失败仅回退对应规则 Agent
on   -> 强制 5 个 Qwen Agent 全部成功，任一失败则返回错误
```

一次完整在线决策最多产生 7 次 Qwen 调用：1 次 Planner、5 次 Strategy Agent、1 次 Reviewer。

### 测试与真实验证

```text
pytest -q -p no:cacheprovider：141 passed
python -m py_compile llm_strategy_agents.py decision_engine.py api_fastapi.py tests/test_llm_strategy_agents.py tests/test_api_fastapi.py：通过
规则模式 CLI：在 local-hashing + SQLite 隔离配置下运行通过
```

真实 Qwen 全链路验证：

- 模型：`qwen3.7-plus`
- Planner：`llm-planner`
- Strategy Agent 生成：5/5
- Strategy Agent fallback：0
- 结构化输出校验：5/5 valid
- Grounded proposals：5/5
- Reviewer 决策模式：`llm+rules(qwen3.7-plus)`
- Reviewer 推荐：诱骗智能体
- 单 Agent 在线耗时范围：约 29.6 秒到 37.3 秒

在线验证使用一次性 SQLite Qwen 向量索引绕过当时本机 Chroma HTTP `localhost:8001` 的 502，验证结束后已清理临时索引文件。没有输出或记录 API Key。

### 当前边界

- 5 个 Agent 共享 Planner 已召回的 RAG、Memory 和 Risk Context，目前没有分别执行独立工具循环。
- 5 路并发位于 LangGraph 的 `generate_proposals` 业务节点内部，尚未重构为 LangGraph 原生 fan-out/fan-in reducer 图。
- 默认 Agent Evaluation 仍以 `llm_mode=off` 做确定性回归；本轮真实 Qwen 验证属于独立 live smoke test，不应表述为已有大规模 LLM Agent 质量评测集。

## 2026-08-05 第五十三轮：实习面试文档 Agent 内容整体同步

### 本轮目标

将 `docs/实习面试项目介绍与问答.md` 全面同步到当前“5 路并行 LLM Strategy Agent + 单角色 fallback”实现，避免项目介绍已经更新，但技术讲解、代码入口和面试问答仍停留在规则 Agent 版本。

### 主要改动

- 核心模块表同时加入 `agents.py` 与 `llm_strategy_agents.py`，明确前者负责规则基线，后者负责角色 Profile、结构化生成、并发调度和 fallback。
- 新增“并行 LLM Strategy Agent”技术专节，完整说明：
  - 规则基线与 LLM 有限指标调整。
  - RAG、Memory、Risk Context 的共享上下文边界。
  - Pydantic 输出契约和证据白名单。
  - `ThreadPoolExecutor` 五路并发、固定顺序汇总和 `off/auto/on` 模式语义。
  - `AgentGenerationRecord`、FastAPI 与 SSE 结构化失败详情。
  - 单次完整链路最多 7 次 Qwen 调用及 Token 成本边界。
- 新增真实问题复盘：Action 清洗顺序、置信度截断、`NaN/Infinity` 防护和失败耗时排队污染。
- 面试问答从 Q52 扩展到 Q57，增加真实并发证明、局部 fallback、严格模式诊断、规则基线设计和成本控制。
- 更新 Q47 的 141 条测试覆盖说明，加入线程屏障并发测试、非有限数值校验和 API/SSE 错误详情。
- 更新代码现场讲解路线与演示脚本，要求展示 `llm_strategy_agents.py` 和响应中的 `agent_generation`。

### 保留的诚实边界

- 当前五路并发位于 LangGraph 的 `generate_proposals` 业务节点内部，不是原生 fan-out/fan-in reducer 图。
- 每个 Strategy Agent 使用 Planner 上游共享的 RAG、Memory 和 Risk Context，尚未分别执行独立工具循环。
- 真实 Qwen 的 5/5 成功、0 fallback 是 live smoke test，不表述为大规模 LLM Agent Evaluation。
- 本轮只更新求职与面试文档，没有修改业务代码，自动化测试总数保持 `141 passed`。

### 文档入口

- `docs/实习面试项目介绍与问答.md`
- `docs/superpowers/specs/2026-08-05-interview-document-agent-sync-design.md`
- `docs/superpowers/plans/2026-08-05-interview-document-agent-sync.md`
