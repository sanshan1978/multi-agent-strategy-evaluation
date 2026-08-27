from __future__ import annotations

import json

from agent_planner import AgentToolPlan, ToolPlanStep
from main import PRESET_SCENES
from planner_evaluation import (
    PlannerEvaluationCase,
    PlannerEvaluator,
    build_default_planner_evaluation_cases,
    main,
    run_default_planner_evaluation,
)


class RiskOnlyPlanner:
    def plan(self, scene, available_tools):  # noqa: ANN001
        return AgentToolPlan(
            objective=scene.objective,
            strategy="risk_only",
            steps=[
                ToolPlanStep(
                    sequence=1,
                    tool_name="risk_analysis",
                    purpose="risk only",
                    parameters={},
                )
            ],
            skipped_steps=[],
        )


def test_default_planner_evaluation_cases_pass() -> None:
    cases = build_default_planner_evaluation_cases()
    summary = run_default_planner_evaluation()

    assert len(cases) == 3
    assert summary.total_cases == 3
    assert summary.passed_cases == 3
    assert summary.tool_match_rate == 1.0
    assert summary.average_repair_count == 0.0
    assert all(result.metrics["validation_status"] == "valid" for result in summary.results)


def test_planner_evaluation_detects_missing_expected_tools() -> None:
    case = PlannerEvaluationCase(
        case_id="urban_missing_context_tools",
        scene=PRESET_SCENES["urban_fast_capture"],
        expected_tools=["knowledge_retrieval", "memory_recall", "risk_analysis"],
        max_repair_count=0,
    )

    summary = PlannerEvaluator(planner=RiskOnlyPlanner()).evaluate([case])

    assert summary.total_cases == 1
    assert summary.passed_cases == 0
    assert summary.results[0].passed is False
    assert any(check.name == "selected_tools_match_expected" and not check.passed for check in summary.results[0].checks)


def test_planner_evaluation_cli_outputs_json(capsys) -> None:
    exit_code = main([])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["total_cases"] == 3
    assert payload["passed_cases"] == 3
    assert payload["tool_match_rate"] == 1.0
