from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from rag import KnowledgeRetriever


@dataclass(frozen=True)
class RAGEvaluationCase:
    case_id: str
    query: str
    expected_titles: list[str]
    expected_source_contains: str
    top_k: int = 3
    require_all_expected_titles: bool = False
    expected_title_sources: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "query": self.query,
            "expected_titles": self.expected_titles,
            "expected_source_contains": self.expected_source_contains,
            "top_k": self.top_k,
            "require_all_expected_titles": self.require_all_expected_titles,
            "expected_title_sources": self.expected_title_sources,
        }


@dataclass(frozen=True)
class RAGEvaluationCaseResult:
    case_id: str
    query: str
    expected_titles: list[str]
    ranked_titles: list[str]
    expected_ranks: dict[str, int | None]
    hit: bool
    expected_rank: int | None
    reciprocal_rank: float
    ndcg: float
    source_match: bool
    source_matches: dict[str, bool]
    require_all_expected_titles: bool
    rerank_improvement: int
    snippets: list[dict[str, Any]]
    fusion_evidence: list[dict[str, Any]]
    rerank_evidence: list[dict[str, Any]]
    retrieval_trace: list[dict[str, Any]]
    issues: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "query": self.query,
            "expected_titles": self.expected_titles,
            "ranked_titles": self.ranked_titles,
            "expected_ranks": self.expected_ranks,
            "hit": self.hit,
            "expected_rank": self.expected_rank,
            "reciprocal_rank": self.reciprocal_rank,
            "ndcg": self.ndcg,
            "source_match": self.source_match,
            "source_matches": self.source_matches,
            "require_all_expected_titles": self.require_all_expected_titles,
            "rerank_improvement": self.rerank_improvement,
            "snippets": self.snippets,
            "fusion_evidence": self.fusion_evidence,
            "rerank_evidence": self.rerank_evidence,
            "retrieval_trace": self.retrieval_trace,
            "issues": self.issues,
        }


@dataclass(frozen=True)
class RAGEvaluationSummary:
    total_cases: int
    passed_cases: int
    hit_at_k: float
    mean_reciprocal_rank: float
    mean_ndcg: float
    source_match_rate: float
    average_rerank_improvement: float
    results: list[RAGEvaluationCaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "hit_at_k": round(self.hit_at_k, 4),
            "mean_reciprocal_rank": round(self.mean_reciprocal_rank, 4),
            "mean_ndcg": round(self.mean_ndcg, 4),
            "source_match_rate": round(self.source_match_rate, 4),
            "average_rerank_improvement": round(self.average_rerank_improvement, 4),
            "results": [item.to_dict() for item in self.results],
        }


class RAGEvaluator:
    def __init__(self, retriever: KnowledgeRetriever | None = None) -> None:
        self.retriever = retriever or KnowledgeRetriever.default()

    def evaluate(self, cases: Iterable[RAGEvaluationCase]) -> RAGEvaluationSummary:
        results = [self.evaluate_case(case) for case in cases]
        total_cases = len(results)
        passed_cases = sum(1 for item in results if item.passed)
        return RAGEvaluationSummary(
            total_cases=total_cases,
            passed_cases=passed_cases,
            hit_at_k=_average(1.0 if item.hit else 0.0 for item in results),
            mean_reciprocal_rank=_average(item.reciprocal_rank for item in results),
            mean_ndcg=_average(item.ndcg for item in results),
            source_match_rate=_average(1.0 if item.source_match else 0.0 for item in results),
            average_rerank_improvement=_average(float(item.rerank_improvement) for item in results),
            results=results,
        )

    def evaluate_case(self, case: RAGEvaluationCase) -> RAGEvaluationCaseResult:
        top_k = max(1, int(case.top_k))
        retrieval = self.retriever.retrieve_query_with_trace(case.query, top_k=top_k)
        snippets = [snippet.to_dict() for snippet in retrieval.snippets]
        ranked_titles = [snippet.title for snippet in retrieval.snippets]
        expected_ranks = {
            title: first_expected_rank(ranked_titles, [title])
            for title in case.expected_titles
        }
        expected_rank = first_expected_rank(ranked_titles, case.expected_titles)
        hit = (
            all(rank is not None for rank in expected_ranks.values())
            if case.require_all_expected_titles
            else expected_rank is not None
        )
        source_matches = _source_match_details(
            snippets,
            expected_titles=case.expected_titles,
            expected_source_contains=case.expected_source_contains,
            expected_title_sources=case.expected_title_sources,
        )
        source_match = all(source_matches.values()) if source_matches else False
        fusion_rank = first_expected_rank(
            [str(item.get("title", "")) for item in retrieval.fusion_evidence],
            case.expected_titles,
        )
        rerank_improvement = (fusion_rank or 0) - (expected_rank or 0) if hit and fusion_rank else 0
        issues = _case_issues(
            hit=hit,
            source_match=source_match,
            retrieval_trace=retrieval.retrieval_trace,
            fusion_evidence=retrieval.fusion_evidence,
            rerank_evidence=retrieval.rerank_evidence,
            expected_titles=case.expected_titles,
            ranked_titles=ranked_titles,
        )
        return RAGEvaluationCaseResult(
            case_id=case.case_id,
            query=case.query,
            expected_titles=case.expected_titles,
            ranked_titles=ranked_titles,
            expected_ranks=expected_ranks,
            hit=hit,
            expected_rank=expected_rank,
            reciprocal_rank=reciprocal_rank(ranked_titles, case.expected_titles),
            ndcg=ndcg_at_k(ranked_titles, case.expected_titles, top_k),
            source_match=source_match,
            source_matches=source_matches,
            require_all_expected_titles=case.require_all_expected_titles,
            rerank_improvement=rerank_improvement,
            snippets=snippets,
            fusion_evidence=retrieval.fusion_evidence,
            rerank_evidence=retrieval.rerank_evidence,
            retrieval_trace=retrieval.retrieval_trace,
            issues=issues,
        )


def build_default_rag_evaluation_cases() -> list[RAGEvaluationCase]:
    return [
        RAGEvaluationCase(
            case_id="direct_urban_safety_zone",
            query="urban civilian safety protected zones hospital school evacuation route",
            expected_titles=["Urban Civilian Safety Zone"],
            expected_source_contains="terrain_and_scenarios.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="direct_low_confidence_reconnaissance",
            query="low confidence intelligence reconnaissance gate collect evidence before planning",
            expected_titles=["Low Confidence Reconnaissance Gate"],
            expected_source_contains="intelligence_and_reconnaissance.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="direct_high_urgency_command",
            query="high urgency shorten decision chain immediate action short review command rhythm",
            expected_titles=["High Urgency Command Rhythm"],
            expected_source_contains="communication_and_command.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="direct_logistics_node_rerouting",
            query="logistics node failure reroute alternative capacity load balance",
            expected_titles=["Logistics Node Failure Rerouting"],
            expected_source_contains="resources_and_logistics.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="direct_shared_blackboard",
            query="shared blackboard structured schema versioned events agent coordination",
            expected_titles=["Shared Blackboard Coordination"],
            expected_source_contains="multi_agent_coordination.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="direct_human_review_gate",
            query="human review approval gate irreversible high risk plan evidence alternatives",
            expected_titles=["Human Review Escalation Gate"],
            expected_source_contains="risk_and_safety_constraints.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="direct_tool_schema_validation",
            query="tool schema validate required fields enum unknown parameters structured error",
            expected_titles=["Tool Schema Validation"],
            expected_source_contains="tool_calling_governance.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="direct_trace_failure_buffer",
            query="trace storage failure bounded memory buffer sequence replay critical events",
            expected_titles=["Trace Storage Failure Buffering"],
            expected_source_contains="degradation_and_recovery.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="paraphrase_expired_intelligence",
            query="早先收到的消息可能跟不上局势变化，怎样避免拿旧结论直接行动",
            expected_titles=["Stale Intelligence Expiration"],
            expected_source_contains="intelligence_and_reconnaissance.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="paraphrase_bandwidth_priority",
            query="链路严重拥塞而且只能放行少量报文时，哪类消息应当抢占队列",
            expected_titles=["Bandwidth Priority Scheduling"],
            expected_source_contains="communication_and_command.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="paraphrase_medical_reservation",
            query="怎样避免救治能力被日常工作耗光，确保突发伤情仍有处置余量",
            expected_titles=["Medical Resource Reservation"],
            expected_source_contains="resources_and_logistics.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="paraphrase_consensus_timeout",
            query="团队讨论到截止点仍各执一词，调度器接下来应该怎样选择方案",
            expected_titles=["Consensus Timeout Fallback"],
            expected_source_contains="multi_agent_coordination.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="paraphrase_prompt_injection",
            query="外部资料假装拥有管理员身份，并催促模型交出登录凭据，该怎样处置",
            expected_titles=["Adversarial Prompt Injection Defense"],
            expected_source_contains="deception_and_anomaly_response.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="paraphrase_latency_breakdown",
            query="一次请求很慢，如何判断时间耗在模型思考、外部能力还是排队等待",
            expected_titles=["Response Time Efficiency"],
            expected_source_contains="strategy_evaluation_metrics.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="paraphrase_termination_validation",
            query="目标看起来已经做完，但遗留隐患没有收尾，状态机现在可以结束吗",
            expected_titles=["Termination Condition Validation"],
            expected_source_contains="decision_workflow_and_termination.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="compound_urban_low_intelligence",
            query="城市人员密集且情报不足，先保护疏散区域并通过多源侦察确认路线",
            expected_titles=["Urban Low Intel Evacuation Case"],
            expected_source_contains="compound_scenario_cases.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="compound_mountain_supply_communication",
            query="山地补给紧张又发生通信中断，智能体在授权范围自治并保留安全储备",
            expected_titles=["Mountain Supply Communication Case"],
            expected_source_contains="compound_scenario_cases.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="compound_plain_urgent_deception",
            query="开放平原的紧急任务发现诱导信号，需要快速验证且只做可撤销动作",
            expected_titles=["Plain Urgent Deception Case"],
            expected_source_contains="compound_scenario_cases.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="compound_multi_agent_sensor_conflict",
            query="多个侦察代理的传感器结论冲突，检查证据独立性并补充观测",
            expected_titles=["Multi Agent Sensor Conflict Case"],
            expected_source_contains="compound_scenario_cases.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="compound_long_duration_recovery",
            query="长期运行同时发生向量生成限流、代理故障和审计轨迹存储中断",
            expected_titles=["Long Duration Recovery Case"],
            expected_source_contains="compound_scenario_cases.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="compound_fuel_return_reserve",
            query="路线距离较短但返程燃料可能不足，需要计算地形成本并保留安全余量",
            expected_titles=["Fuel Budget Route Selection"],
            expected_source_contains="resources_and_logistics.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="discrimination_protected_area_constraint",
            query="禁止区域属于硬约束，候选计划一旦触碰就直接淘汰而不是降低风险分",
            expected_titles=["Protected Area Hard Constraint"],
            expected_source_contains="risk_and_safety_constraints.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="discrimination_sensor_conflict",
            query="不同传感器观测矛盾时结合可靠度新鲜度和历史偏差，不使用简单多数投票",
            expected_titles=["Sensor Conflict Resolution"],
            expected_source_contains="intelligence_and_reconnaissance.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="discrimination_embedding_outage",
            query="向量模型超时限流时不能把另一个维度模型静默写入原有集合",
            expected_titles=["Embedding Service Degradation"],
            expected_source_contains="degradation_and_recovery.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="discrimination_idempotent_tool_retry",
            query="有状态工具网络超时后重试必须复用相同请求标识，避免重复执行",
            expected_titles=["Tool Call Idempotency Key"],
            expected_source_contains="tool_calling_governance.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="discrimination_agent_handoff",
            query="侦察角色把任务交给支援角色时传递证据来源、置信度和未解决风险",
            expected_titles=["Scout Support Agent Handoff"],
            expected_source_contains="multi_agent_coordination.md",
            top_k=3,
        ),
        RAGEvaluationCase(
            case_id="cross_intelligence_planning_gate",
            query="关键前提缺失时，把信息缺口分派为侦察任务，同时在证据补齐前禁止生成高影响计划",
            expected_titles=["Intelligence Gap Task Allocation", "Evidence First Planning Gate"],
            expected_source_contains="decision_workflow_and_termination.md",
            top_k=3,
            require_all_expected_titles=True,
            expected_title_sources={
                "Intelligence Gap Task Allocation": "intelligence_and_reconnaissance.md",
                "Evidence First Planning Gate": "decision_workflow_and_termination.md",
            },
        ),
        RAGEvaluationCase(
            case_id="cross_uncertainty_risk_budget",
            query="长期保障趋势显示恢复能力将下降时，系统应提前预测资源缺口并同步收紧可接受风险",
            expected_titles=["Sustained Operation Resource Forecast", "Risk Budget Dynamic Adjustment"],
            expected_source_contains="risk_and_safety_constraints.md",
            top_k=3,
            require_all_expected_titles=True,
            expected_title_sources={
                "Sustained Operation Resource Forecast": "resources_and_logistics.md",
                "Risk Budget Dynamic Adjustment": "risk_and_safety_constraints.md",
            },
        ),
        RAGEvaluationCase(
            case_id="cross_reconnect_state_sync",
            query="离线成员重新加入协作空间后，既要合并带版本的共享记录，也要保证公告板最终一致",
            expected_titles=["Cross Agent State Synchronization", "Shared Blackboard Coordination"],
            expected_source_contains="communication_and_command.md",
            top_k=3,
            require_all_expected_titles=True,
            expected_title_sources={
                "Cross Agent State Synchronization": "communication_and_command.md",
                "Shared Blackboard Coordination": "multi_agent_coordination.md",
            },
        ),
        RAGEvaluationCase(
            case_id="cross_anomalous_tool_quarantine",
            query="外部能力返回的数据虽然通过格式检查却明显反常，需要先做参数契约校验并隔离结果",
            expected_titles=["Tool Schema Validation", "Anomalous Tool Output Quarantine"],
            expected_source_contains="deception_and_anomaly_response.md",
            top_k=3,
            require_all_expected_titles=True,
            expected_title_sources={
                "Tool Schema Validation": "tool_calling_governance.md",
                "Anomalous Tool Output Quarantine": "deception_and_anomaly_response.md",
            },
        ),
    ]


def run_default_rag_evaluation() -> RAGEvaluationSummary:
    return RAGEvaluator().evaluate(build_default_rag_evaluation_cases())


def quality_gate_issues(
    summary: RAGEvaluationSummary,
    *,
    min_hit_at_k: float = 0.90,
    min_mean_reciprocal_rank: float = 0.75,
    min_mean_ndcg: float = 0.80,
    min_source_match_rate: float = 0.90,
) -> list[str]:
    issues: list[str] = []
    if summary.total_cases <= 0:
        issues.append("evaluation contains no cases")
    if summary.passed_cases != summary.total_cases:
        issues.append(
            f"passed cases below requirement: {summary.passed_cases}/{summary.total_cases}"
        )
    thresholds = {
        "hit_at_k": (summary.hit_at_k, min_hit_at_k),
        "mean_reciprocal_rank": (
            summary.mean_reciprocal_rank,
            min_mean_reciprocal_rank,
        ),
        "mean_ndcg": (summary.mean_ndcg, min_mean_ndcg),
        "source_match_rate": (
            summary.source_match_rate,
            min_source_match_rate,
        ),
    }
    for metric, (actual, minimum) in thresholds.items():
        if actual < minimum:
            issues.append(
                f"{metric} below threshold: actual={actual:.4f}, minimum={minimum:.4f}"
            )
    return issues


def reciprocal_rank(ranked_titles: list[str], expected_titles: list[str]) -> float:
    rank = first_expected_rank(ranked_titles, expected_titles)
    if rank is None:
        return 0.0
    return round(1.0 / rank, 4)


def ndcg_at_k(ranked_titles: list[str], expected_titles: list[str], k: int) -> float:
    expected = set(expected_titles)
    limited_titles = ranked_titles[: max(1, k)]
    dcg = sum(
        1.0 / _log2(rank + 1)
        for rank, title in enumerate(limited_titles, start=1)
        if title in expected
    )
    ideal_hits = min(len(expected), len(limited_titles))
    ideal_dcg = sum(1.0 / _log2(rank + 1) for rank in range(1, ideal_hits + 1))
    if ideal_dcg == 0:
        return 0.0
    return round(dcg / ideal_dcg, 4)


def first_expected_rank(ranked_titles: list[str], expected_titles: list[str]) -> int | None:
    expected = set(expected_titles)
    for rank, title in enumerate(ranked_titles, start=1):
        if title in expected:
            return rank
    return None


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cases = build_default_rag_evaluation_cases()
    if args.case_id:
        cases = [case for case in cases if case.case_id == args.case_id]
    if not cases:
        raise SystemExit(f"unknown RAG evaluation case: {args.case_id}")

    summary = RAGEvaluator().evaluate(cases)
    gate_issues = quality_gate_issues(summary)
    payload = summary.to_dict()
    payload["quality_gate"] = {
        "passed": not gate_issues,
        "issues": gate_issues,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not gate_issues else 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAG retrieval quality evaluation cases.")
    parser.add_argument("--case-id", help="Run one default RAG evaluation case by id.")
    return parser.parse_args(argv)


def _source_match_details(
    snippets: list[dict[str, Any]],
    *,
    expected_titles: list[str],
    expected_source_contains: str,
    expected_title_sources: dict[str, str],
) -> dict[str, bool]:
    title_sources = expected_title_sources or {
        title: expected_source_contains for title in expected_titles
    }
    return {
        title: any(
            snippet.get("title") == title
            and source in str(snippet.get("source", ""))
            for snippet in snippets
        )
        for title, source in title_sources.items()
    }


def _case_issues(
    *,
    hit: bool,
    source_match: bool,
    retrieval_trace: list[dict[str, Any]],
    fusion_evidence: list[dict[str, Any]],
    rerank_evidence: list[dict[str, Any]],
    expected_titles: list[str],
    ranked_titles: list[str],
) -> list[str]:
    issues: list[str] = []
    if not hit:
        issues.append(f"expected titles not retrieved: expected={expected_titles}, ranked={ranked_titles}")
    if hit and not source_match:
        issues.append("matched title source did not match expected source")
    if not retrieval_trace:
        issues.append("retrieval trace is empty")
    if not fusion_evidence:
        issues.append("fusion evidence is empty")
    if not rerank_evidence:
        issues.append("rerank evidence is empty")
    return issues


def _average(values: Iterable[float]) -> float:
    collected = list(values)
    if not collected:
        return 0.0
    return sum(collected) / len(collected)


def _log2(value: int) -> float:
    return 1.0 if value <= 1 else __import__("math").log2(value)


if __name__ == "__main__":
    raise SystemExit(main())
