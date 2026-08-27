from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List

from agents import BaseAgent, build_default_agents
from agent_planner import AgentToolPlan, PlanValidator, RuleBasedToolPlanner, SkippedToolStep, ToolPlanStep
from decision_auditor import RuleBasedDecisionAuditor
from grounding import GroundingBuilder
from llm_coordinator import LLMCoordinator
from llm_strategy_agents import ParallelStrategyAgentRunner, StrategyAgentGenerationBatch
from memory import DecisionMemory, MemoryCase
from models import AgentGenerationRecord, BattlefieldScene, DebateMessage, ScoredProposal, StrategyProposal, clamp
from plan_execution_auditor import PlanExecutionAuditor
from rag import KnowledgeRetriever, KnowledgeSnippet
from standards import build_dynamic_weights, evaluate_weighted_score, priority_metrics
from settings import get_settings
from tools import (
    KnowledgeRetrievalTool,
    MemoryRecallTool,
    RiskAnalysisTool,
    ToolExecutionPolicy,
    ToolRegistry,
    ToolResult,
    summarize_tool_results,
)
from trace import TraceEvent
from workflow import DecisionGraphNode, DecisionGraphRunner, DecisionGraphState


@dataclass
class DecisionResult:
    best: ScoredProposal
    ranking: List[ScoredProposal]
    messages: List[DebateMessage]
    weights: Dict[str, float]
    decision_mode: str
    trace: List[TraceEvent]
    knowledge_context: List[KnowledgeSnippet]
    memory_context: List[MemoryCase]
    risk_context: Dict[str, Any]
    grounding_evidence: Dict[str, Any]
    tool_plan: AgentToolPlan
    tool_calls: List[ToolResult]
    tool_metrics: Dict[str, Any]
    plan_execution_audit: Dict[str, Any]
    workflow_nodes: List[str]
    decision_audit: Dict[str, Any]
    agent_generation_records: List[AgentGenerationRecord] = field(default_factory=list)
    llm_recommended_agent: str | None = None
    llm_reason: str | None = None
    llm_error: str | None = None


@dataclass
class DecisionProgressEvent:
    event_type: str
    trace_event: TraceEvent | None = None
    result: DecisionResult | None = None


@dataclass
class LLMReviewDecision:
    score_bonus: Dict[str, float]
    decision_mode: str
    recommended_agent: str | None = None
    reason: str | None = None
    error: str | None = None


class DecisionEngine:
    def __init__(
        self,
        agents: List[BaseAgent] | None = None,
        llm_mode: str = "auto",
        llm_model: str | None = None,
        knowledge_retriever: KnowledgeRetriever | None = None,
        decision_memory: DecisionMemory | None = None,
        tool_registry: ToolRegistry | None = None,
        tool_planner: RuleBasedToolPlanner | None = None,
        plan_validator: PlanValidator | None = None,
        plan_execution_auditor: PlanExecutionAuditor | None = None,
        grounding_builder: GroundingBuilder | None = None,
        decision_auditor: RuleBasedDecisionAuditor | None = None,
        tool_policy: ToolExecutionPolicy | None = None,
        strategy_agent_runner: ParallelStrategyAgentRunner | None = None,
    ) -> None:
        self.agents = agents or build_default_agents()
        self.llm_mode = llm_mode.lower()
        if self.llm_mode not in {"auto", "on", "off"}:
            raise ValueError("llm_mode 必须是 auto / on / off")
        self.llm = None if self.llm_mode == "off" else LLMCoordinator.from_env(model=llm_model)
        self.knowledge_retriever = knowledge_retriever or KnowledgeRetriever.default()
        self.decision_memory = decision_memory or DecisionMemory.default()
        self.tool_registry = tool_registry or self._build_tool_registry()
        self.tool_planner = tool_planner or RuleBasedToolPlanner()
        self.plan_validator = plan_validator or PlanValidator()
        self.plan_execution_auditor = plan_execution_auditor or PlanExecutionAuditor()
        self.grounding_builder = grounding_builder or GroundingBuilder()
        self.decision_auditor = decision_auditor or RuleBasedDecisionAuditor()
        self.tool_policy = tool_policy or ToolExecutionPolicy()
        self.strategy_agent_runner = strategy_agent_runner or ParallelStrategyAgentRunner(
            max_workers=get_settings().agent_max_workers
        )

    def _build_tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(KnowledgeRetrievalTool(self.knowledge_retriever))
        registry.register(MemoryRecallTool(self.decision_memory))
        registry.register(RiskAnalysisTool())
        return registry

    def run(self, scene: BattlefieldScene) -> DecisionResult:
        result: DecisionResult | None = None
        for event in self.run_stream(scene):
            if event.result is not None:
                result = event.result
        if result is None:
            raise RuntimeError("决策流程未生成结果")
        return result

    def run_stream(self, scene: BattlefieldScene) -> Iterator[DecisionProgressEvent]:
        trace = self._start_trace(scene)
        state = DecisionGraphState(scene=scene, trace=trace)
        yield DecisionProgressEvent(event_type="trace", trace_event=trace[-1])
        for state in self._build_decision_graph().run(state):
            yield DecisionProgressEvent(event_type="trace", trace_event=state.trace[-1])
        if state.tool_plan is None or state.llm_decision is None or not state.ranking:
            raise RuntimeError("decision graph did not produce a complete result")
        result = DecisionResult(
            best=state.ranking[0],
            ranking=state.ranking,
            messages=state.messages,
            weights=state.weights,
            decision_mode=state.llm_decision.decision_mode,
            trace=trace,
            knowledge_context=state.knowledge_context,
            memory_context=state.memory_context,
            risk_context=state.risk_context,
            grounding_evidence=state.grounding_evidence,
            tool_plan=state.tool_plan,
            tool_calls=state.tool_calls,
            tool_metrics=summarize_tool_results(state.tool_calls),
            plan_execution_audit=state.plan_execution_audit,
            workflow_nodes=state.completed_nodes,
            decision_audit=state.decision_audit,
            agent_generation_records=state.agent_generation_records,
            llm_recommended_agent=state.llm_decision.recommended_agent,
            llm_reason=state.llm_decision.reason,
            llm_error=state.llm_decision.error,
        )
        yield DecisionProgressEvent(event_type="result", result=result)

    def _build_decision_graph(self) -> DecisionGraphRunner:
        return DecisionGraphRunner(
            [
                DecisionGraphNode("plan_tools", self._plan_tools_node),
                DecisionGraphNode(
                    "retrieve_knowledge",
                    self._retrieve_knowledge_node,
                    condition=self._tool_is_planned("knowledge_retrieval"),
                    on_skip=self._skip_tool_node("retrieve_knowledge", "knowledge_retrieval"),
                ),
                DecisionGraphNode(
                    "recall_memory",
                    self._recall_memory_node,
                    condition=self._tool_is_planned("memory_recall"),
                    on_skip=self._skip_tool_node("recall_memory", "memory_recall"),
                ),
                DecisionGraphNode(
                    "analyze_risk",
                    self._analyze_risk_node,
                    condition=self._tool_is_planned("risk_analysis"),
                    on_skip=self._skip_tool_node("analyze_risk", "risk_analysis"),
                ),
                DecisionGraphNode("audit_tool_plan_execution", self._audit_tool_plan_execution_node),
                DecisionGraphNode("generate_proposals", self._generate_proposals_node),
                DecisionGraphNode("build_grounding_evidence", self._build_grounding_evidence_node),
                DecisionGraphNode("run_dialogue", self._run_dialogue_node),
                DecisionGraphNode("build_weights", self._build_weights_node),
                DecisionGraphNode("llm_review", self._llm_review_node),
                DecisionGraphNode("score_proposals", self._score_proposals_node),
                DecisionGraphNode("audit_decision", self._audit_decision_node),
                DecisionGraphNode("finalize_decision", self._finalize_decision_node),
            ]
        )

    def _plan_tools_node(self, state: DecisionGraphState) -> None:
        state.tool_plan = self._plan_tools(state.scene, state.trace)

    def _retrieve_knowledge_node(self, state: DecisionGraphState) -> None:
        if state.tool_plan is None:
            raise RuntimeError("tool plan is required before knowledge retrieval")
        state.knowledge_context = self._retrieve_knowledge(
            state.scene,
            state.trace,
            state.tool_calls,
            state.tool_plan.step_for("knowledge_retrieval"),
        )

    def _recall_memory_node(self, state: DecisionGraphState) -> None:
        if state.tool_plan is None:
            raise RuntimeError("tool plan is required before memory recall")
        state.memory_context = self._recall_memory(
            state.scene,
            state.trace,
            state.tool_calls,
            state.tool_plan.step_for("memory_recall"),
        )

    def _analyze_risk_node(self, state: DecisionGraphState) -> None:
        if state.tool_plan is None:
            raise RuntimeError("tool plan is required before risk analysis")
        state.risk_context = self._analyze_risk(
            state.scene,
            state.trace,
            state.tool_calls,
            state.tool_plan.step_for("risk_analysis"),
            state.knowledge_context,
            state.memory_context,
        )

    def _generate_proposals_node(self, state: DecisionGraphState) -> None:
        batch = self._generate_proposals(
            state.scene,
            state.knowledge_context,
            state.memory_context,
            state.risk_context,
            state.trace,
        )
        state.proposals = batch.proposals
        state.agent_generation_records = batch.records

    def _audit_tool_plan_execution_node(self, state: DecisionGraphState) -> None:
        if state.tool_plan is None:
            raise RuntimeError("tool plan is required before plan execution audit")
        state.plan_execution_audit = self._audit_tool_plan_execution(
            state.tool_plan,
            state.tool_calls,
            state.trace,
        )

    def _build_grounding_evidence_node(self, state: DecisionGraphState) -> None:
        state.grounding_evidence = self._build_grounding_evidence(
            state.knowledge_context,
            state.proposals,
            state.risk_context,
            state.trace,
        )

    def _run_dialogue_node(self, state: DecisionGraphState) -> None:
        state.messages = self._run_dialogue_stage(state.scene, state.proposals, state.trace)

    def _build_weights_node(self, state: DecisionGraphState) -> None:
        state.weights = self._build_weights_stage(state.scene, state.trace)

    def _llm_review_node(self, state: DecisionGraphState) -> None:
        state.llm_decision = self._review_with_llm(
            state.scene,
            state.proposals,
            state.weights,
            state.messages,
            state.trace,
        )

    def _score_proposals_node(self, state: DecisionGraphState) -> None:
        if state.llm_decision is None:
            raise RuntimeError("LLM review decision is required before scoring")
        state.ranking = self._score_and_rank(
            state.proposals,
            state.weights,
            state.llm_decision.score_bonus,
            state.trace,
        )

    def _audit_decision_node(self, state: DecisionGraphState) -> None:
        state.decision_audit = self._audit_decision(
            state.scene,
            state.ranking,
            state.risk_context,
            state.knowledge_context,
            state.memory_context,
            state.trace,
        )

    def _finalize_decision_node(self, state: DecisionGraphState) -> None:
        if state.llm_decision is None:
            raise RuntimeError("LLM review decision is required before finalization")
        self._finalize_trace(state.ranking, state.llm_decision.decision_mode, state.trace)

    def _start_trace(self, scene: BattlefieldScene) -> List[TraceEvent]:
        return [
            TraceEvent(
                step="start",
                message="开始执行多智能体策略评估",
                metadata={"scene": scene.name, "llm_mode": self.llm_mode},
            )
        ]

    def _plan_tools(self, scene: BattlefieldScene, trace: List[TraceEvent]) -> AgentToolPlan:
        available_tools = self.tool_registry.names()
        fallback_plan = self.tool_planner.plan(
            scene=scene,
            available_tools=available_tools,
        ).with_planner_metadata(planner_source="rule-based")
        raw_tool_plan = self._plan_tools_with_llm(scene, fallback_plan)
        tool_plan, validation_report = self.plan_validator.validate_and_repair(
            raw_tool_plan,
            fallback_plan=fallback_plan,
            available_tools=available_tools,
        )
        trace.append(
            TraceEvent(
                step="plan_tools",
                message=(
                    f"Planned {len(tool_plan.steps)} agent tool calls before strategy generation "
                    f"using {tool_plan.planner_source}"
                ),
                metadata={
                    "tool_plan": tool_plan.to_dict(),
                    "planner_source": tool_plan.planner_source,
                    "planner_model": tool_plan.planner_model,
                    "planner_error": tool_plan.planner_error,
                    "plan_validation": validation_report.to_dict(),
                },
            )
        )
        return tool_plan

    def _plan_tools_with_llm(self, scene: BattlefieldScene, fallback_plan: AgentToolPlan) -> AgentToolPlan:
        if self.llm_mode == "off":
            return fallback_plan
        if self.llm is None:
            return fallback_plan.with_planner_metadata(
                planner_source="rule-based-fallback",
                planner_error="missing_api_key_for_llm_planner",
            )

        tool_specs = [spec.to_dict() for spec in self.tool_registry.specs()]
        plan_result = self.llm.plan_tools(
            scene=scene,
            tool_specs=tool_specs,
            fallback_plan=fallback_plan,
        )
        if plan_result.plan is not None:
            return plan_result.plan
        return fallback_plan.with_planner_metadata(
            planner_source="rule-based-fallback",
            planner_model=self.llm.model,
            planner_error=plan_result.error or "llm_planner_failed",
        )

    @staticmethod
    def _tool_is_planned(tool_name: str):
        def condition(state: DecisionGraphState) -> bool:
            if state.tool_plan is None:
                return False
            return state.tool_plan.optional_step_for(tool_name) is not None

        return condition

    def _skip_tool_node(self, trace_step: str, tool_name: str):
        def on_skip(state: DecisionGraphState) -> None:
            skipped_step = state.tool_plan.skipped_step_for(tool_name) if state.tool_plan else None
            self._skip_tool_trace(
                state.trace,
                trace_step=trace_step,
                tool_name=tool_name,
                skipped_step=skipped_step,
            )

        return on_skip

    @staticmethod
    def _skip_tool_trace(
        trace: List[TraceEvent],
        trace_step: str,
        tool_name: str,
        skipped_step: SkippedToolStep | None,
    ) -> None:
        reason = skipped_step.reason if skipped_step else "tool_not_selected"
        condition = skipped_step.condition if skipped_step else "tool was not included in current plan"
        trace.append(
            TraceEvent(
                step=trace_step,
                message=f"Skipped {tool_name} according to conditional tool plan",
                status="skipped",
                metadata={
                    "tool_name": tool_name,
                    "reason": reason,
                    "condition": condition,
                    "need_score": round(skipped_step.need_score, 2) if skipped_step else 0.0,
                    "threshold": round(skipped_step.threshold, 2) if skipped_step else 0.0,
                    "branch": "skip_tool",
                },
            )
        )

    def _retrieve_knowledge(
        self,
        scene: BattlefieldScene,
        trace: List[TraceEvent],
        tool_calls: List[ToolResult],
        plan_step: ToolPlanStep,
    ) -> List[KnowledgeSnippet]:
        top_k = int(plan_step.parameters.get("top_k", 3))
        tool_result = self._run_tool(plan_step.tool_name, fallback_output=[], scene=scene, top_k=top_k)
        tool_calls.append(tool_result)
        snippets = list(tool_result.output)
        trace.append(
            TraceEvent(
                step="retrieve_knowledge",
                message=f"RAG 知识库召回 {len(snippets)} 条场景相关知识片段",
                metadata={
                    "top_k": len(snippets),
                    "planned_top_k": top_k,
                    "sources": [
                        {"title": item.title, "score": round(item.score, 4), "source": item.source}
                        for item in snippets
                    ],
                    "tool_name": tool_result.tool_name,
                    "tool_status": tool_result.status,
                    "tool_purpose": plan_step.purpose,
                    "query_rewrite": tool_result.metadata.get("query_rewrite", {}),
                    "candidates_considered": tool_result.metadata.get("candidates_considered", 0),
                    "rerank_evidence": tool_result.metadata.get("rerank_evidence", []),
                    "fallback_used": tool_result.metadata.get("fallback_used", False),
                    "duration_ms": round(tool_result.duration_ms, 3),
                },
            )
        )
        return snippets

    def _recall_memory(
        self,
        scene: BattlefieldScene,
        trace: List[TraceEvent],
        tool_calls: List[ToolResult],
        plan_step: ToolPlanStep,
    ) -> List[MemoryCase]:
        top_k = int(plan_step.parameters.get("top_k", 3))
        tool_result = self._run_tool(plan_step.tool_name, fallback_output=[], scene=scene, top_k=top_k)
        tool_calls.append(tool_result)
        cases = list(tool_result.output)
        trace.append(
            TraceEvent(
                step="recall_memory",
                message=f"Agent Memory 召回 {len(cases)} 条相似历史决策案例",
                metadata={
                    "top_k": len(cases),
                    "planned_top_k": top_k,
                    "cases": [
                        {
                            "record_id": item.record_id,
                            "scene_name": item.scene_name,
                            "similarity": round(item.similarity, 4),
                            "best_strategy": item.best_strategy,
                            "matched_features": item.matched_features,
                        }
                        for item in cases
                    ],
                    "tool_name": tool_result.tool_name,
                    "tool_status": tool_result.status,
                    "tool_purpose": plan_step.purpose,
                    "fallback_used": tool_result.metadata.get("fallback_used", False),
                    "duration_ms": round(tool_result.duration_ms, 3),
                },
            )
        )
        return cases

    def _analyze_risk(
        self,
        scene: BattlefieldScene,
        trace: List[TraceEvent],
        tool_calls: List[ToolResult],
        plan_step: ToolPlanStep,
        knowledge_context: List[KnowledgeSnippet],
        memory_context: List[MemoryCase],
    ) -> Dict[str, Any]:
        tool_result = self._run_tool(
            plan_step.tool_name,
            fallback_output=_fallback_risk_context(),
            scene=scene,
            knowledge_context=knowledge_context,
            memory_context=memory_context,
        )
        tool_calls.append(tool_result)
        risk_context = dict(tool_result.output)
        trace.append(
            TraceEvent(
                step="analyze_risk",
                message=f"风险分析工具识别为 {risk_context.get('risk_level')} 风险",
                metadata={
                    "risk_context": risk_context,
                    "tool_name": tool_result.tool_name,
                    "tool_status": tool_result.status,
                    "tool_purpose": plan_step.purpose,
                    "fallback_used": tool_result.metadata.get("fallback_used", False),
                    "duration_ms": round(tool_result.duration_ms, 3),
                    "depends_on": ["knowledge_retrieval", "memory_recall"],
                    "knowledge_context_count": len(knowledge_context),
                    "memory_context_count": len(memory_context),
                },
            )
        )
        return risk_context

    def _run_tool(self, tool_name: str, fallback_output: Any, **kwargs: Any) -> ToolResult:
        return self.tool_registry.run_with_policy(
            tool_name,
            fallback_output=fallback_output,
            policy=self.tool_policy,
            **kwargs,
        )

    def _audit_tool_plan_execution(
        self,
        tool_plan: AgentToolPlan,
        tool_calls: List[ToolResult],
        trace: List[TraceEvent],
    ) -> Dict[str, Any]:
        audit = self.plan_execution_auditor.audit(tool_plan, tool_calls).to_dict()
        trace.append(
            TraceEvent(
                step="audit_tool_plan_execution",
                message=(
                    f"Tool plan execution audit completed with status={audit['status']} "
                    f"and findings={audit['summary']['finding_count']}"
                ),
                metadata={"plan_execution_audit": audit},
            )
        )
        return audit

    def _generate_proposals(
        self,
        scene: BattlefieldScene,
        knowledge_context: List[KnowledgeSnippet],
        memory_context: List[MemoryCase],
        risk_context: Dict[str, Any],
        trace: List[TraceEvent],
    ) -> StrategyAgentGenerationBatch:
        batch = self.strategy_agent_runner.generate(
            agents=self.agents,
            llm=self.llm,
            llm_mode=self.llm_mode,
            scene=scene,
            knowledge_context=knowledge_context,
            memory_context=memory_context,
            risk_context=risk_context,
        )
        llm_success_count = sum(record.generation_mode == "llm" for record in batch.records)
        fallback_count = sum(record.generation_mode == "rule-fallback" for record in batch.records)
        trace.append(
            TraceEvent(
                step="generate_proposals",
                message=(
                    f"{len(batch.proposals)} 个策略智能体完成候选方案生成，"
                    f"LLM={llm_success_count}，fallback={fallback_count}"
                ),
                metadata={
                    "agents": [record.to_dict() for record in batch.records],
                    "llm_success_count": llm_success_count,
                    "fallback_count": fallback_count,
                    "duration_ms": round(batch.duration_ms, 3),
                    "max_agent_duration_ms": round(
                        max((record.duration_ms for record in batch.records), default=0.0),
                        3,
                    ),
                    "knowledge_sources": [item.title for item in knowledge_context],
                    "memory_sources": [item.record_id for item in memory_context],
                },
            )
        )
        return batch

    def _build_grounding_evidence(
        self,
        knowledge_context: List[KnowledgeSnippet],
        proposals: List[StrategyProposal],
        risk_context: Dict[str, Any],
        trace: List[TraceEvent],
    ) -> Dict[str, Any]:
        report = self.grounding_builder.build(
            knowledge_context=knowledge_context,
            proposals=proposals,
            risk_context=risk_context,
        ).to_dict()
        trace.append(
            TraceEvent(
                step="build_grounding_evidence",
                message=(
                    f"Built RAG grounding evidence with status={report['status']} "
                    f"and snippets={report['summary']['knowledge_snippet_count']}"
                ),
                metadata={"grounding_evidence": report},
            )
        )
        return report

    @staticmethod
    def _attach_knowledge_context(
        proposals: List[StrategyProposal],
        knowledge_context: List[KnowledgeSnippet],
    ) -> None:
        source_titles = [item.title for item in knowledge_context]
        for proposal in proposals:
            proposal.knowledge_sources = source_titles

    @staticmethod
    def _attach_memory_context(
        proposals: List[StrategyProposal],
        memory_context: List[MemoryCase],
    ) -> None:
        source_ids = [item.record_id for item in memory_context]
        for proposal in proposals:
            proposal.memory_sources = source_ids

    def _run_dialogue_stage(
        self,
        scene: BattlefieldScene,
        proposals: List[StrategyProposal],
        trace: List[TraceEvent],
    ) -> List[DebateMessage]:
        messages = self._run_dialogue(scene, proposals)
        trace.append(
            TraceEvent(
                step="run_dialogue",
                message=f"完成智能体互评，生成 {len(messages)} 条互评消息",
                metadata={"message_count": len(messages)},
            )
        )
        return messages

    @staticmethod
    def _build_weights_stage(scene: BattlefieldScene, trace: List[TraceEvent]) -> Dict[str, float]:
        weights = build_dynamic_weights(scene)
        trace.append(
            TraceEvent(
                step="build_weights",
                message="根据场景参数生成动态评价权重",
                metadata={"weights": weights, "priority_metrics": priority_metrics(scene)},
            )
        )
        return weights

    def _review_with_llm(
        self,
        scene: BattlefieldScene,
        proposals: List[StrategyProposal],
        weights: Dict[str, float],
        messages: List[DebateMessage],
        trace: List[TraceEvent],
    ) -> LLMReviewDecision:
        if self.llm_mode == "off":
            trace.append(
                TraceEvent(
                    step="llm_review",
                    message="LLM 模式关闭，仅使用本地规则决策",
                    status="skipped",
                    metadata={"reason": "llm_mode_off"},
                )
            )
            return LLMReviewDecision(score_bonus={}, decision_mode="local-rules")

        if not self.llm:
            if self.llm_mode == "on":
                raise RuntimeError("未检测到 API_KEY 或 OPENAI_API_KEY，无法启用外部模型裁决。")
            trace.append(
                TraceEvent(
                    step="llm_review",
                    message="未检测到模型密钥，自动降级为本地规则决策",
                    status="skipped",
                    metadata={"reason": "missing_api_key"},
                )
            )
            return LLMReviewDecision(score_bonus={}, decision_mode="local-rules(no-api-key)")

        review = self.llm.review(scene=scene, proposals=proposals, weights=weights)
        if review.error:
            if self.llm_mode == "on":
                raise RuntimeError(f"外部模型调用失败: {review.error}")
            trace.append(
                TraceEvent(
                    step="llm_review",
                    message="LLM 裁决失败，已回退到本地规则决策",
                    status="failed",
                    metadata={"error": review.error},
                )
            )
            return LLMReviewDecision(
                score_bonus={},
                decision_mode="local-rules(llm-failed)",
                error=review.error,
            )

        messages.extend(review.messages)
        self._apply_llm_effects(proposals, review.messages, review.confidence_deltas)
        trace.append(
            TraceEvent(
                step="llm_review",
                message="LLM 完成候选方案裁决增强",
                metadata={
                    "model": self.llm.model,
                    "recommended_agent": review.recommended_agent,
                    "message_count": len(review.messages),
                    "score_delta_count": len(review.score_deltas),
                },
            )
        )
        return LLMReviewDecision(
            score_bonus=review.score_deltas,
            decision_mode=f"llm+rules({self.llm.model})",
            recommended_agent=review.recommended_agent,
            reason=review.reason,
        )

    def _score_and_rank(
        self,
        proposals: List[StrategyProposal],
        weights: Dict[str, float],
        llm_score_bonus: Dict[str, float],
        trace: List[TraceEvent],
    ) -> List[ScoredProposal]:
        scored = [self._score_proposal(p, weights, llm_score_bonus.get(p.agent_name, 0.0)) for p in proposals]
        ranking = sorted(scored, key=lambda x: x.final_score, reverse=True)
        trace.append(
            TraceEvent(
                step="score_proposals",
                message="完成候选方案综合评分与排序",
                metadata={
                    "ranking": [
                        {"agent_name": item.proposal.agent_name, "final_score": item.final_score}
                        for item in ranking
                    ]
                },
            )
        )
        return ranking

    def _audit_decision(
        self,
        scene: BattlefieldScene,
        ranking: List[ScoredProposal],
        risk_context: Dict[str, Any],
        knowledge_context: List[KnowledgeSnippet],
        memory_context: List[MemoryCase],
        trace: List[TraceEvent],
    ) -> Dict[str, Any]:
        audit = self.decision_auditor.audit(
            scene=scene,
            ranking=ranking,
            risk_context=risk_context,
            knowledge_context=knowledge_context,
            memory_context=memory_context,
        ).to_dict()
        trace.append(
            TraceEvent(
                step="audit_decision",
                message=(
                    f"Decision audit completed with status={audit['overall_status']} "
                    f"and findings={audit['finding_count']}"
                ),
                metadata={"decision_audit": audit},
            )
        )
        return audit

    @staticmethod
    def _finalize_trace(
        ranking: List[ScoredProposal],
        decision_mode: str,
        trace: List[TraceEvent],
    ) -> None:
        trace.append(
            TraceEvent(
                step="finalize_decision",
                message=f"最终推荐 {ranking[0].proposal.agent_name} 的 {ranking[0].proposal.strategy_name}",
                metadata={
                    "best_agent": ranking[0].proposal.agent_name,
                    "best_strategy": ranking[0].proposal.strategy_name,
                    "decision_mode": decision_mode,
                },
            )
        )

    def _score_proposal(self, proposal: StrategyProposal, weights: Dict[str, float], llm_bonus: float = 0.0) -> ScoredProposal:
        weighted = evaluate_weighted_score(proposal, weights)
        confidence_bonus = proposal.confidence * 8.0
        peer_bonus = proposal.peer_support * 20.0
        final = clamp(weighted + confidence_bonus + peer_bonus + llm_bonus, 0.0, 100.0)
        return ScoredProposal(
            proposal=proposal,
            weighted_score=weighted,
            final_score=final,
            llm_bonus=llm_bonus,
            weights=weights,
        )

    @staticmethod
    def _apply_llm_effects(
        proposals: List[StrategyProposal],
        llm_messages: List[DebateMessage],
        confidence_deltas: Dict[str, float],
    ) -> None:
        proposal_index = {p.agent_name: p for p in proposals}
        for msg in llm_messages:
            target = proposal_index.get(msg.to_agent)
            if not target:
                continue
            target.peer_support = clamp(target.peer_support + msg.impact * 0.6, -0.2, 0.2)
        for proposal in proposals:
            delta = confidence_deltas.get(proposal.agent_name, 0.0)
            proposal.confidence = clamp(proposal.confidence + delta, 0.2, 1.0)

    def _run_dialogue(self, scene: BattlefieldScene, proposals: List[StrategyProposal]) -> List[DebateMessage]:
        messages: List[DebateMessage] = []
        key_metrics = priority_metrics(scene)
        index = {p.agent_name: p for p in proposals}

        for src in proposals:
            for dst in proposals:
                if src.agent_name == dst.agent_name:
                    continue
                msg = self._build_message(src, dst, key_metrics)
                messages.append(msg)
                index[dst.agent_name].peer_support += msg.impact

        for p in proposals:
            p.peer_support = clamp(p.peer_support / max(len(proposals) - 1, 1), -0.2, 0.2)
            p.confidence = clamp(p.confidence + p.peer_support * 0.5, 0.2, 1.0)
        return messages

    @staticmethod
    def _build_message(src: StrategyProposal, dst: StrategyProposal, key_metrics: List[str]) -> DebateMessage:
        score_map = dst.normalized_metric_scores()
        important = key_metrics[0]
        dst_value = score_map.get(important, 50.0)
        src_value = src.normalized_metric_scores().get(important, 50.0)
        gap = src_value - dst_value

        if gap >= 12:
            impact = -0.08
            text = f"在关键指标 {important} 上，{dst.strategy_name}存在明显短板，建议补充保障措施。"
        elif gap <= -12:
            impact = 0.06
            text = f"{dst.strategy_name}在关键指标 {important} 上表现突出，可作为主方案候选。"
        else:
            impact = 0.01
            text = f"{dst.strategy_name}整体可行，建议与其他方案形成联合行动预案。"

        return DebateMessage(
            from_agent=src.agent_name,
            to_agent=dst.agent_name,
            content=text,
            impact=impact,
        )


def _fallback_risk_context() -> Dict[str, Any]:
    return {
        "risk_score": 0.0,
        "risk_level": "unknown",
        "factors": [],
        "recommendations": ["risk analysis tool failed; use conservative local scoring"],
        "context_evidence": {
            "knowledge_titles": [],
            "memory_case_ids": [],
            "signals": [],
            "context_adjustment": 0.0,
            "recommendations": [],
        },
    }


def format_result(scene: BattlefieldScene, result: DecisionResult, show_messages: bool = True) -> str:
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append(f"场景: {scene.name}")
    lines.append(f"任务目标: {scene.objective}")
    lines.append(f"决策模式: {result.decision_mode}")
    if result.llm_error:
        lines.append(f"LLM状态: 回退到本地规则 ({result.llm_error})")
    lines.append(
        "场景参数: "
        f"地形={scene.terrain}, 天气={scene.weather}, 敌强={scene.enemy_strength}, 我强={scene.own_strength}, "
        f"补给={scene.supply_level}, 情报={scene.intel_quality}, 时效={scene.urgency}, 平民密度={scene.civilian_presence}"
    )
    lines.append("-" * 70)
    lines.append("动态评价权重:")
    for k, v in result.weights.items():
        lines.append(f"  - {k}: {v:.2%}")
    lines.append("-" * 70)
    lines.append("方案排名:")
    for i, item in enumerate(result.ranking, 1):
        p = item.proposal
        llm_info = f" | LLM加分={item.llm_bonus:+.2f}" if abs(item.llm_bonus) >= 0.01 else ""
        lines.append(
            f"{i}. {p.agent_name} / {p.strategy_name} | 综合分={item.final_score:.2f} | "
            f"基础加权分={item.weighted_score:.2f} | 置信度={p.confidence:.2f} | 互评支持={p.peer_support:.2f}{llm_info}"
        )
        lines.append(f"   摘要: {p.summary}")
    lines.append("-" * 70)
    top = result.best.proposal
    lines.append("最终推荐:")
    lines.append(f"  {top.agent_name} -> {top.strategy_name}")
    lines.append(f"  理由: {top.rationale}")
    if result.llm_recommended_agent:
        lines.append(f"  LLM推荐: {result.llm_recommended_agent}")
    if result.llm_reason:
        lines.append(f"  LLM说明: {result.llm_reason}")
    lines.append("  核心动作:")
    for action in top.actions:
        lines.append(f"    * {action}")

    if show_messages:
        lines.append("-" * 70)
        lines.append("智能体交流摘录:")
        for msg in result.messages[:12]:
            lines.append(f"  {msg.from_agent} -> {msg.to_agent}: {msg.content} (impact={msg.impact:+.2f})")

    lines.append("=" * 70)
    return "\n".join(lines)
