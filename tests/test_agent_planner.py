from __future__ import annotations

from agent_planner import AgentToolPlan, PlanValidator, RuleBasedToolPlanner, ToolPlanStep
from main import PRESET_SCENES


def test_rule_based_tool_planner_builds_ordered_tool_plan() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    planner = RuleBasedToolPlanner()

    plan = planner.plan(
        scene=scene,
        available_tools=["risk_analysis", "memory_recall", "knowledge_retrieval"],
    )

    assert plan.strategy == "time_sensitive+civilian_sensitive+intel_constrained"
    assert [step.tool_name for step in plan.steps] == [
        "knowledge_retrieval",
        "memory_recall",
        "risk_analysis",
    ]
    assert plan.step_for("knowledge_retrieval").parameters["top_k"] == 4
    assert plan.step_for("knowledge_retrieval").need_score >= plan.step_for("knowledge_retrieval").threshold
    assert plan.to_dict()["steps"][0]["sequence"] == 1
    assert "need_score" in plan.to_dict()["steps"][0]


def test_rule_based_tool_planner_skips_unavailable_tools() -> None:
    scene = PRESET_SCENES["plain_counterstrike"]
    planner = RuleBasedToolPlanner()

    plan = planner.plan(scene=scene, available_tools=["risk_analysis"])

    assert [step.tool_name for step in plan.steps] == ["risk_analysis"]


def test_rule_based_tool_planner_records_scored_skips() -> None:
    scene = PRESET_SCENES["plain_counterstrike"]
    planner = RuleBasedToolPlanner()

    plan = planner.plan(
        scene=scene,
        available_tools=["knowledge_retrieval", "memory_recall", "risk_analysis"],
    )

    skipped = {step.tool_name: step for step in plan.skipped_steps}
    assert skipped["knowledge_retrieval"].need_score < skipped["knowledge_retrieval"].threshold
    assert skipped["memory_recall"].need_score < skipped["memory_recall"].threshold
    assert plan.step_for("risk_analysis").need_score >= plan.step_for("risk_analysis").threshold
    assert plan.to_dict()["skipped_steps"][0]["threshold"] > 0


def test_plan_validator_accepts_valid_rule_based_plan() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    available_tools = ["knowledge_retrieval", "memory_recall", "risk_analysis"]
    fallback_plan = RuleBasedToolPlanner().plan(scene=scene, available_tools=available_tools)

    repaired_plan, report = PlanValidator().validate_and_repair(
        fallback_plan,
        fallback_plan=fallback_plan,
        available_tools=available_tools,
    )

    assert report.status == "valid"
    assert report.repair_count == 0
    assert repaired_plan.validation_status == "valid"
    assert repaired_plan.validation_issues == []
    assert repaired_plan.repair_actions == []


def test_plan_validator_repairs_invalid_llm_plan() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    available_tools = ["knowledge_retrieval", "memory_recall", "risk_analysis"]
    fallback_plan = RuleBasedToolPlanner().plan(scene=scene, available_tools=available_tools)
    invalid_plan = AgentToolPlan(
        objective=fallback_plan.objective,
        strategy="broken_llm_plan",
        steps=[
            ToolPlanStep(
                sequence=7,
                tool_name="risk_analysis",
                purpose="risk first with illegal params",
                parameters={"top_k": 99, "unexpected": True},
            ),
            ToolPlanStep(
                sequence=3,
                tool_name="unknown_tool",
                purpose="unknown tool must be removed",
                parameters={},
            ),
            ToolPlanStep(
                sequence=2,
                tool_name="knowledge_retrieval",
                purpose="retrieve too many docs",
                parameters={"top_k": 99},
            ),
            ToolPlanStep(
                sequence=4,
                tool_name="knowledge_retrieval",
                purpose="duplicate knowledge call",
                parameters={"top_k": 2},
            ),
        ],
        skipped_steps=[],
        planner_source="llm-planner",
        planner_model="fake-model",
    )

    repaired_plan, report = PlanValidator().validate_and_repair(
        invalid_plan,
        fallback_plan=fallback_plan,
        available_tools=available_tools,
    )

    assert report.status == "repaired"
    assert repaired_plan.validation_status == "repaired"
    assert [step.tool_name for step in repaired_plan.steps] == [
        "knowledge_retrieval",
        "memory_recall",
        "risk_analysis",
    ]
    assert [step.sequence for step in repaired_plan.steps] == [1, 2, 3]
    assert repaired_plan.step_for("knowledge_retrieval").parameters["top_k"] == 6
    assert repaired_plan.step_for("memory_recall").parameters["top_k"] == 4
    assert repaired_plan.step_for("risk_analysis").parameters == {}
    repair_actions = {item["action"] for item in repaired_plan.repair_actions}
    assert {
        "remove_unknown_tool",
        "remove_duplicate_tool",
        "sanitize_parameters",
        "add_missing_required_tool",
        "reorder_steps",
    }.issubset(repair_actions)
    assert report.repair_count == len(repaired_plan.repair_actions)
