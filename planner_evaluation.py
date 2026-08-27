from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, Sequence

from agent_planner import AgentToolPlan, PlanValidator, RuleBasedToolPlanner
from models import BattlefieldScene


DEFAULT_AVAILABLE_TOOLS = ["knowledge_retrieval", "memory_recall", "risk_analysis"]


class PlannerProtocol(Protocol):
    def plan(self, scene: BattlefieldScene, available_tools: list[str]) -> AgentToolPlan:
        ...


@dataclass(frozen=True)
class PlannerEvaluationCase:
    case_id: str
    scene: BattlefieldScene
    expected_tools: list[str]
    available_tools: list[str] = field(default_factory=lambda: list(DEFAULT_AVAILABLE_TOOLS))
    max_repair_count: int = 0

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
            "available_tools": self.available_tools,
            "max_repair_count": self.max_repair_count,
        }


@dataclass(frozen=True)
class PlannerEvaluationCheck:
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
class PlannerEvaluationCaseResult:
    case_id: str
    passed: bool
    score: float
    checks: list[PlannerEvaluationCheck]
    metrics: dict[str, Any]
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "score": round(self.score, 2),
            "checks": [check.to_dict() for check in self.checks],
            "metrics": self.metrics,
            "issues": self.issues,
        }


@dataclass(frozen=True)
class PlannerEvaluationSummary:
    total_cases: int
    passed_cases: int
    average_score: float
    tool_match_rate: float
    average_repair_count: float
    results: list[PlannerEvaluationCaseResult]

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
            "tool_match_rate": round(self.tool_match_rate, 4),
            "average_repair_count": round(self.average_repair_count, 2),
            "results": [result.to_dict() for result in self.results],
        }


class PlannerEvaluator:
    def __init__(
        self,
        planner: PlannerProtocol | None = None,
        fallback_planner: PlannerProtocol | None = None,
        validator: PlanValidator | None = None,
    ) -> None:
        self.planner = planner or RuleBasedToolPlanner()
        self.fallback_planner = fallback_planner or RuleBasedToolPlanner()
        self.validator = validator or PlanValidator()

    def evaluate(self, cases: Iterable[PlannerEvaluationCase]) -> PlannerEvaluationSummary:
        results = [self.evaluate_case(case) for case in cases]
        passed_cases = sum(1 for result in results if result.passed)
        average_score = sum(result.score for result in results) / len(results) if results else 0.0
        tool_match_rate = (
            sum(1 for result in results if result.metrics.get("selected_tools_match") is True) / len(results)
            if results
            else 0.0
        )
        average_repair_count = (
            sum(int(result.metrics.get("repair_count", 0)) for result in results) / len(results)
            if results
            else 0.0
        )
        return PlannerEvaluationSummary(
            total_cases=len(results),
            passed_cases=passed_cases,
            average_score=average_score,
            tool_match_rate=tool_match_rate,
            average_repair_count=average_repair_count,
            results=results,
        )

    def evaluate_case(self, case: PlannerEvaluationCase) -> PlannerEvaluationCaseResult:
        raw_plan = self.planner.plan(case.scene, case.available_tools)
        fallback_plan = self.fallback_planner.plan(case.scene, case.available_tools)
        repaired_plan, validation_report = self.validator.validate_and_repair(
            raw_plan,
            fallback_plan=fallback_plan,
            available_tools=case.available_tools,
        )
        selected_tools = [step.tool_name for step in raw_plan.steps]
        repaired_tools = [step.tool_name for step in repaired_plan.steps]
        covered_tools = {step.tool_name for step in repaired_plan.steps}
        covered_tools.update(step.tool_name for step in repaired_plan.skipped_steps)
        checks = [
            _check(
                "selected_tools_match_expected",
                selected_tools == case.expected_tools,
                f"expected={case.expected_tools}, actual={selected_tools}",
            ),
            _check(
                "repaired_plan_executable",
                validation_report.status in {"valid", "repaired"},
                f"validation_status={validation_report.status}",
            ),
            _check(
                "repair_count_within_limit",
                validation_report.repair_count <= case.max_repair_count,
                f"max={case.max_repair_count}, actual={validation_report.repair_count}",
            ),
            _check(
                "repaired_sequence_contiguous",
                [step.sequence for step in repaired_plan.steps] == list(range(1, len(repaired_plan.steps) + 1)),
                f"sequences={[step.sequence for step in repaired_plan.steps]}",
            ),
            _check(
                "available_tools_covered",
                set(case.available_tools).issubset(covered_tools),
                f"available={case.available_tools}, covered={sorted(covered_tools)}",
            ),
            _check(
                "dependency_order_valid",
                _is_dependency_order_valid(repaired_tools),
                f"repaired_tools={repaired_tools}",
            ),
        ]
        passed_checks = sum(1 for check in checks if check.passed)
        score = 100.0 * passed_checks / len(checks) if checks else 0.0
        issues = [check.detail for check in checks if not check.passed]
        return PlannerEvaluationCaseResult(
            case_id=case.case_id,
            passed=not issues,
            score=score,
            checks=checks,
            metrics={
                "planner_source": raw_plan.planner_source,
                "strategy": raw_plan.strategy,
                "selected_tools": selected_tools,
                "expected_tools": case.expected_tools,
                "selected_tools_match": selected_tools == case.expected_tools,
                "repaired_tools": repaired_tools,
                "validation_status": validation_report.status,
                "repair_count": validation_report.repair_count,
                "repair_actions": [action.to_dict() for action in validation_report.repair_actions],
            },
            issues=issues,
        )


def build_default_planner_evaluation_cases() -> list[PlannerEvaluationCase]:
    return [
        PlannerEvaluationCase(
            case_id="urban_high_context_need",
            scene=BattlefieldScene(
                name="urban high context planner evaluation",
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
        ),
        PlannerEvaluationCase(
            case_id="mountain_memory_risk_need",
            scene=BattlefieldScene(
                name="mountain memory risk planner evaluation",
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
        ),
        PlannerEvaluationCase(
            case_id="plain_low_context_need",
            scene=BattlefieldScene(
                name="plain low context planner evaluation",
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
        ),
    ]


def run_default_planner_evaluation() -> PlannerEvaluationSummary:
    return PlannerEvaluator().evaluate(build_default_planner_evaluation_cases())


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cases = build_default_planner_evaluation_cases()
    if args.case_id:
        cases = [case for case in cases if case.case_id == args.case_id]
        if not cases:
            raise SystemExit(f"unknown planner evaluation case_id: {args.case_id}")
    summary = PlannerEvaluator().evaluate(cases)
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0 if summary.passed_cases == summary.total_cases else 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run planner-only evaluation cases.")
    parser.add_argument("--case-id", help="Run a single planner evaluation case.")
    return parser.parse_args(argv)


def _check(name: str, passed: bool, detail: str) -> PlannerEvaluationCheck:
    return PlannerEvaluationCheck(name=name, passed=passed, detail=detail)


def _is_dependency_order_valid(tools: Sequence[str]) -> bool:
    order = {"knowledge_retrieval": 1, "memory_recall": 2, "risk_analysis": 3}
    positions = [order.get(tool, 99) for tool in tools]
    return positions == sorted(positions)


if __name__ == "__main__":
    raise SystemExit(main())
