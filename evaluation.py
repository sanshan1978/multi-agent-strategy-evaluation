from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from decision_engine import DecisionEngine, DecisionResult
from models import BattlefieldScene


DEFAULT_TRACE_STEPS = [
    "start",
    "plan_tools",
    "retrieve_knowledge",
    "recall_memory",
    "analyze_risk",
    "audit_tool_plan_execution",
    "generate_proposals",
    "build_grounding_evidence",
    "run_dialogue",
    "build_weights",
    "llm_review",
    "score_proposals",
    "audit_decision",
    "finalize_decision",
]


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    scene: BattlefieldScene
    expected_tools: list[str]
    min_final_score: float
    allowed_risk_levels: set[str] = field(default_factory=lambda: {"low", "medium", "high"})
    required_trace_steps: list[str] = field(default_factory=lambda: list(DEFAULT_TRACE_STEPS))
    required_rag_expansions: list[str] = field(default_factory=list)
    allowed_audit_statuses: set[str] = field(default_factory=lambda: {"passed", "review_recommended"})

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "scene": {
                "name": self.scene.name,
                "objective": self.scene.objective,
                "terrain": self.scene.terrain,
                "weather": self.scene.weather,
                "enemy_strength": self.scene.enemy_strength,
                "own_strength": self.scene.own_strength,
                "supply_level": self.scene.supply_level,
                "intel_quality": self.scene.intel_quality,
                "urgency": self.scene.urgency,
                "civilian_presence": self.scene.civilian_presence,
            },
            "expected_tools": self.expected_tools,
            "min_final_score": self.min_final_score,
            "allowed_risk_levels": sorted(self.allowed_risk_levels),
            "required_rag_expansions": self.required_rag_expansions,
            "allowed_audit_statuses": sorted(self.allowed_audit_statuses),
        }


@dataclass(frozen=True)
class EvaluationCheck:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class EvaluationCaseResult:
    case_id: str
    passed: bool
    score: float
    checks: list[EvaluationCheck]
    metrics: dict[str, Any]
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "score": round(self.score, 2),
            "checks": [item.to_dict() for item in self.checks],
            "metrics": self.metrics,
            "issues": self.issues,
        }


@dataclass(frozen=True)
class EvaluationSummary:
    total_cases: int
    passed_cases: int
    average_score: float
    results: list[EvaluationCaseResult]

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed_cases / self.total_cases

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "average_score": round(self.average_score, 2),
            "results": [item.to_dict() for item in self.results],
        }


class AgentEvaluator:
    def __init__(self, engine_factory: Callable[[], DecisionEngine] | None = None) -> None:
        self.engine_factory = engine_factory or (lambda: DecisionEngine(llm_mode="off"))

    def evaluate(self, cases: Iterable[EvaluationCase]) -> EvaluationSummary:
        results: list[EvaluationCaseResult] = []
        for case in cases:
            engine = self.engine_factory()
            result = engine.run(case.scene)
            results.append(evaluate_case_result(case, result))

        passed_cases = sum(1 for item in results if item.passed)
        average_score = sum(item.score for item in results) / len(results) if results else 0.0
        return EvaluationSummary(
            total_cases=len(results),
            passed_cases=passed_cases,
            average_score=average_score,
            results=results,
        )


def evaluate_case_result(case: EvaluationCase, result: DecisionResult) -> EvaluationCaseResult:
    trace_steps = [event.step for event in result.trace]
    called_tools = [item.tool_name for item in result.tool_calls]
    checks = [
        _check(
            "tool_plan_matches_expected",
            called_tools == case.expected_tools,
            f"expected={case.expected_tools}, actual={called_tools}",
        ),
        _check(
            "trace_contains_required_steps",
            _contains_all(trace_steps, case.required_trace_steps),
            f"required={case.required_trace_steps}, actual={trace_steps}",
        ),
        _check(
            "workflow_finalized",
            bool(result.workflow_nodes) and result.workflow_nodes[-1] == "finalize_decision",
            f"workflow_nodes={result.workflow_nodes}",
        ),
        _check(
            "tool_execution_has_no_failures",
            result.tool_metrics.get("failed", 0) == 0,
            f"tool_metrics={result.tool_metrics}",
        ),
        _check(
            "risk_level_allowed",
            str(result.risk_context.get("risk_level")) in case.allowed_risk_levels,
            f"risk_level={result.risk_context.get('risk_level')}",
        ),
        _check(
            "final_score_above_floor",
            result.best.final_score >= case.min_final_score,
            f"final_score={round(result.best.final_score, 2)}, min={case.min_final_score}",
        ),
        _check(
            "decision_audit_allowed",
            str(result.decision_audit.get("overall_status")) in case.allowed_audit_statuses,
            f"audit_status={result.decision_audit.get('overall_status')}",
        ),
    ]

    if "knowledge_retrieval" in case.expected_tools:
        checks.extend(_rag_checks(case, result))
        checks.extend(_grounding_checks(result))

    passed_checks = sum(1 for item in checks if item.passed)
    score = 100.0 * passed_checks / len(checks) if checks else 0.0
    issues = [item.detail for item in checks if not item.passed]
    return EvaluationCaseResult(
        case_id=case.case_id,
        passed=not issues,
        score=score,
        checks=checks,
        metrics=_case_metrics(result),
        issues=issues,
    )


def build_default_evaluation_cases() -> list[EvaluationCase]:
    return [
        EvaluationCase(
            case_id="urban_high_pressure",
            scene=BattlefieldScene(
                name="urban high pressure evaluation",
                objective="capture transport hub under time pressure while controlling civilian collateral risk",
                terrain="urban",
                weather="cloudy",
                enemy_strength=68,
                own_strength=72,
                supply_level=63,
                intel_quality=58,
                urgency=88,
                civilian_presence=82,
            ),
            expected_tools=["knowledge_retrieval", "memory_recall", "risk_analysis"],
            min_final_score=70.0,
            allowed_risk_levels={"medium", "high"},
            required_rag_expansions=["civilian_dense", "high_urgency", "low_intel"],
        ),
        EvaluationCase(
            case_id="mountain_enemy_pressure",
            scene=BattlefieldScene(
                name="mountain enemy pressure evaluation",
                objective="block mountain pass and delay enemy reinforcement",
                terrain="mountain",
                weather="fog",
                enemy_strength=74,
                own_strength=61,
                supply_level=55,
                intel_quality=64,
                urgency=65,
                civilian_presence=25,
            ),
            expected_tools=["memory_recall", "risk_analysis"],
            min_final_score=70.0,
            allowed_risk_levels={"low", "medium"},
        ),
        EvaluationCase(
            case_id="plain_low_context_need",
            scene=BattlefieldScene(
                name="plain low context need evaluation",
                objective="retake plain supply node with sufficient intelligence and manageable civilian pressure",
                terrain="plain",
                weather="clear",
                enemy_strength=62,
                own_strength=70,
                supply_level=79,
                intel_quality=76,
                urgency=72,
                civilian_presence=30,
            ),
            expected_tools=["risk_analysis"],
            min_final_score=75.0,
            allowed_risk_levels={"low"},
        ),
    ]


def run_default_evaluation() -> EvaluationSummary:
    return AgentEvaluator().evaluate(build_default_evaluation_cases())


def _rag_checks(case: EvaluationCase, result: DecisionResult) -> list[EvaluationCheck]:
    retrieve_trace = _trace_event(result, "retrieve_knowledge")
    metadata = retrieve_trace.metadata if retrieve_trace is not None else {}
    query_rewrite = metadata.get("query_rewrite", {})
    expansions = set(query_rewrite.get("expansions", []))
    return [
        _check(
            "rag_query_rewrite_present",
            bool(query_rewrite.get("expanded_query")),
            f"query_rewrite={query_rewrite}",
        ),
        _check(
            "rag_required_expansions_present",
            set(case.required_rag_expansions).issubset(expansions),
            f"required={case.required_rag_expansions}, expansions={sorted(expansions)}",
        ),
        _check(
            "rag_rerank_evidence_present",
            bool(metadata.get("rerank_evidence")),
            f"rerank_evidence={metadata.get('rerank_evidence')}",
        ),
    ]


def _grounding_checks(result: DecisionResult) -> list[EvaluationCheck]:
    grounding = result.grounding_evidence
    risk_grounding = grounding.get("risk_grounding", {})
    return [
        _check(
            "grounding_evidence_present",
            grounding.get("status") == "grounded",
            f"grounding_status={grounding.get('status')}",
        ),
        _check(
            "grounding_risk_evidence_present",
            bool(risk_grounding.get("evidence")),
            f"risk_grounding={risk_grounding}",
        ),
    ]


def _case_metrics(result: DecisionResult) -> dict[str, Any]:
    return {
        "best_agent": result.best.proposal.agent_name,
        "best_strategy": result.best.proposal.strategy_name,
        "final_score": round(result.best.final_score, 2),
        "decision_mode": result.decision_mode,
        "risk_level": result.risk_context.get("risk_level"),
        "risk_score": result.risk_context.get("risk_score"),
        "audit_status": result.decision_audit.get("overall_status"),
        "grounding_status": result.grounding_evidence.get("status"),
        "tool_calls": [item.tool_name for item in result.tool_calls],
        "tool_metrics": result.tool_metrics,
        "trace_steps": [event.step for event in result.trace],
    }


def _check(name: str, passed: bool, detail: str) -> EvaluationCheck:
    return EvaluationCheck(name=name, passed=passed, detail=detail)


def _contains_all(values: Sequence[str], required: Sequence[str]) -> bool:
    current = set(values)
    return all(item in current for item in required)


def _trace_event(result: DecisionResult, step: str):
    for event in result.trace:
        if event.step == step:
            return event
    return None


def main() -> None:
    summary = run_default_evaluation()
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
