from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class SceneSchema(BaseModel):
    name: str = Field(description="场景名称")
    objective: str = Field(description="任务目标描述")
    terrain: str = Field(description="地形类型，例如 urban、mountain、plain、forest")
    weather: str = Field(description="天气条件")
    enemy_strength: int = Field(ge=0, le=100, description="敌方强度，取值范围 0-100")
    own_strength: int = Field(ge=0, le=100, description="我方强度，取值范围 0-100")
    supply_level: int = Field(ge=0, le=100, description="补给水平，取值范围 0-100")
    intel_quality: int = Field(ge=0, le=100, description="情报质量，取值范围 0-100")
    urgency: int = Field(ge=0, le=100, description="时效压力，取值范围 0-100")
    civilian_presence: int = Field(ge=0, le=100, description="平民密度，取值范围 0-100")


class DecisionRequest(BaseModel):
    scene: SceneSchema = Field(description="待评估的战场对抗场景参数")
    llm_mode: Literal["auto", "on", "off"] = Field(
        default="auto",
        description="LLM 调用模式：off 仅本地规则，auto 有密钥则调用且失败降级，on 强制调用",
    )
    llm_model: str | None = Field(default=None, description="可选的大模型名称，用于覆盖环境变量中的默认模型")


class StrategyProposalSchema(BaseModel):
    agent_name: str = Field(description="提出方案的智能体名称")
    strategy_name: str = Field(description="策略方案名称")
    summary: str = Field(description="方案摘要")
    actions: List[str] = Field(description="方案核心动作列表")
    metric_scores: Dict[str, float] = Field(description="各评价指标得分")
    rationale: str = Field(description="方案推荐或生成理由")
    confidence: float = Field(description="智能体对该方案的置信度")
    peer_support: float = Field(description="其他智能体互评带来的支持度")


    knowledge_sources: List[str] = Field(default_factory=list, description="Agent 生成方案时参考的 RAG 知识片段标题")


    memory_sources: List[int] = Field(default_factory=list, description="Agent 生成方案时参考的历史决策记录 ID")


class KnowledgeSnippetSchema(BaseModel):
    title: str = Field(description="知识片段标题")
    content: str = Field(description="知识片段内容")
    score: float = Field(description="检索相关性分数")
    source: str = Field(description="知识来源文件")


class MemoryCaseSchema(BaseModel):
    memory_id: int | None = Field(default=None, description="Agent Memory entry id")
    record_id: int = Field(description="历史决策记录 ID")
    scene_name: str = Field(description="历史场景名称")
    decision_mode: str = Field(description="历史决策模式")
    best_agent: str = Field(description="历史最优 Agent")
    best_strategy: str = Field(description="历史最优策略")
    similarity: float = Field(description="与当前场景的相似度")
    matched_features: List[str] = Field(description="命中的相似特征")
    created_at: str = Field(description="历史记录创建时间")
    summary: str = Field(default="", description="Agent Memory summary")
    lessons: List[str] = Field(default_factory=list, description="Agent Memory lessons")
    tags: List[str] = Field(default_factory=list, description="Agent Memory tags")
    risk_level: str = Field(default="", description="historical risk level")
    importance_score: float = Field(default=0.0, description="memory importance score")


class ToolCallSchema(BaseModel):
    tool_name: str = Field(description="工具名称")
    status: str = Field(description="工具调用状态")
    output: Any = Field(description="工具输出")
    metadata: Dict[str, Any] = Field(description="工具调用元数据")
    duration_ms: float = Field(description="工具执行耗时，单位毫秒")


class ToolPlanStepSchema(BaseModel):
    sequence: int = Field(description="tool execution order")
    tool_name: str = Field(description="planned tool name")
    purpose: str = Field(description="reason for calling the tool")
    parameters: Dict[str, Any] = Field(description="planned tool parameters")
    required: bool = Field(description="whether this step is required")
    need_score: float = Field(description="tool selection need score")
    threshold: float = Field(description="minimum score required to call the tool")


class SkippedToolStepSchema(BaseModel):
    tool_name: str = Field(description="skipped tool name")
    reason: str = Field(description="reason why the tool was skipped")
    condition: str = Field(description="condition that caused the tool to be skipped")
    need_score: float = Field(description="tool selection need score")
    threshold: float = Field(description="minimum score required to call the tool")


class ToolPlanSchema(BaseModel):
    objective: str = Field(description="planning objective")
    strategy: str = Field(description="planning strategy label")
    steps: List[ToolPlanStepSchema] = Field(description="planned tool steps")
    skipped_steps: List[SkippedToolStepSchema] = Field(description="tools skipped by conditional planning")
    planner_source: str = Field(description="tool planner source, such as rule-based or llm-planner")
    planner_model: str | None = Field(default=None, description="LLM model used by the tool planner")
    planner_error: str | None = Field(default=None, description="LLM planner error when fallback is used")
    validation_status: str = Field(description="tool plan validation status: not_checked, valid, repaired or invalid")
    validation_issues: List[Dict[str, Any]] = Field(description="tool plan validation issues")
    repair_actions: List[Dict[str, Any]] = Field(description="repair actions applied before graph execution")


class ToolSpecSchema(BaseModel):
    name: str = Field(description="tool name")
    description: str = Field(description="tool description")
    input_schema: Dict[str, Any] = Field(description="tool input schema")
    output_schema: Dict[str, Any] = Field(description="tool output schema")
    tags: List[str] = Field(description="tool tags")


class ScoredProposalSchema(BaseModel):
    proposal: StrategyProposalSchema = Field(description="候选策略方案详情")
    weightedScore: float = Field(description="基于动态权重计算出的基础加权分")
    finalScore: float = Field(description="综合置信度、互评支持和 LLM 加分后的最终得分")
    llmBonus: float = Field(description="LLM 裁决增强带来的加减分")


class DebateMessageSchema(BaseModel):
    from_agent: str = Field(description="发起点评的智能体")
    to_agent: str = Field(description="被点评的智能体")
    content: str = Field(description="互评内容")
    impact: float = Field(description="该互评对目标方案支持度的影响，通常在 -0.2 到 0.2 之间")


class TraceEventSchema(BaseModel):
    step: str = Field(description="决策流程步骤标识")
    message: str = Field(description="该步骤的人类可读说明")
    status: str = Field(description="步骤状态，例如 completed、skipped、failed")
    metadata: Dict[str, Any] = Field(description="该步骤的结构化补充信息")
    timestamp: str = Field(description="Trace 事件生成时间，使用 UTC ISO 格式")


class AgentGenerationRecordSchema(BaseModel):
    agent_name: str = Field(description="策略 Agent 名称")
    strategy_name: str = Field(description="策略名称")
    generation_mode: str = Field(description="生成模式：llm、rule 或 rule-fallback")
    model: str | None = Field(default=None, description="生成方案使用的模型")
    duration_ms: float = Field(description="该 Agent 生成方案的耗时，单位毫秒")
    validation_status: str = Field(description="模型结构化输出校验状态")
    fallback_reason: str | None = Field(default=None, description="该 Agent 使用规则 fallback 的原因")
    knowledge_sources: List[str] = Field(description="该 Agent 实际引用的知识标题")
    memory_sources: List[int] = Field(description="该 Agent 实际引用的历史记录 ID")
    metric_adjustments: Dict[str, float] = Field(description="相对规则指标基线的有限调整")


class DecisionResponse(BaseModel):
    workflow_nodes: List[str] = Field(description="decision graph executed node path")
    tool_metrics: Dict[str, Any] = Field(description="tool execution reliability metrics")
    memory_context: List[MemoryCaseSchema] = Field(description="本次决策召回并注入 Agent 上下文的历史案例记忆")
    knowledge_context: List[KnowledgeSnippetSchema] = Field(description="本次决策召回并注入 Agent 上下文的 RAG 知识片段")
    risk_context: Dict[str, Any] = Field(description="风险分析工具输出")
    grounding_evidence: Dict[str, Any] = Field(description="RAG 证据与 Agent 方案、风险建议之间的 grounding 关联报告")
    tool_plan: ToolPlanSchema = Field(description="Agent 执行前生成的工具调用计划")
    tool_calls: List[ToolCallSchema] = Field(description="本次决策执行的工具调用记录")
    best: ScoredProposalSchema = Field(description="最终推荐的最佳方案")
    ranking: List[ScoredProposalSchema] = Field(description="所有候选方案的排序结果")
    plan_execution_audit: Dict[str, Any] = Field(description="Planner 计划与实际工具执行结果的一致性审计报告")
    decision_audit: Dict[str, Any] = Field(description="Reflection/Critic audit report for the final decision")
    messages: List[DebateMessageSchema] = Field(description="智能体互评与 LLM 裁决消息")
    weights: Dict[str, float] = Field(description="本次场景下的动态评价权重")
    decision_mode: str = Field(description="实际使用的决策模式")
    trace: List[TraceEventSchema] = Field(description="本次决策的流程追踪记录")
    llm_recommended_agent: str | None = Field(default=None, description="LLM 推荐的智能体名称")
    llm_reason: str | None = Field(default=None, description="LLM 推荐理由")
    llm_error: str | None = Field(default=None, description="LLM 调用失败时的错误信息")
    agent_generation: List[AgentGenerationRecordSchema] = Field(
        description="五个策略 Agent 的生成模式、模型、耗时、证据和 fallback 记录"
    )


class DecisionRecordSummarySchema(BaseModel):
    id: int = Field(description="历史决策记录 ID")
    scene_name: str = Field(description="场景名称")
    decision_mode: str = Field(description="本次决策模式")
    best_agent: str = Field(description="最终推荐的智能体名称")
    best_strategy: str = Field(description="最终推荐的策略名称")
    created_at: str = Field(description="记录创建时间，UTC ISO 格式")


class DecisionRecordDetailSchema(DecisionRecordSummarySchema):
    scene: Dict[str, Any] = Field(description="本次决策的输入场景参数")
    result: Dict[str, Any] = Field(description="本次决策的完整输出结果")


class ErrorResponse(BaseModel):
    error: str = Field(description="错误描述")
    error_type: str = Field(description="错误类型标识")
    details: Any | None = Field(default=None, description="可选的错误详情，通常用于参数校验失败")


    request_id: str | None = Field(default=None, description="璇锋眰杩借釜 ID锛岀敤浜庡榻愬搷搴斿拰鍚庣鏃ュ織")


class HealthResponse(BaseModel):
    ok: bool = Field(description="服务是否可用")
    service: str = Field(description="服务名称")
    version: str = Field(description="服务版本号")


ScenarioMap = Dict[str, Dict[str, Any]]
