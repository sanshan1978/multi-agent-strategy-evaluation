from __future__ import annotations

from decision_engine import DecisionEngine
from main import PRESET_SCENES
from serializers import result_to_dict, scene_to_dict


def test_scene_serializer_keeps_frontend_contract() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]

    data = scene_to_dict(scene)

    assert data == {
        "name": "城市快速夺控",
        "objective": "在4小时内控制交通枢纽并维持通信稳定",
        "terrain": "urban",
        "weather": "cloudy",
        "enemy_strength": 68,
        "own_strength": 72,
        "supply_level": 63,
        "intel_quality": 58,
        "urgency": 88,
        "civilian_presence": 82,
    }


def test_result_serializer_keeps_api_contract() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    result = DecisionEngine(llm_mode="off").run(scene)

    data = result_to_dict(result)

    assert set(data) == {
        "best",
        "ranking",
        "messages",
        "weights",
        "decision_mode",
        "knowledge_context",
        "memory_context",
        "risk_context",
        "grounding_evidence",
        "tool_plan",
        "tool_calls",
        "tool_metrics",
        "plan_execution_audit",
        "workflow_nodes",
        "decision_audit",
        "trace",
        "llm_recommended_agent",
        "llm_reason",
        "llm_error",
        "agent_generation",
    }
    assert {"proposal", "weightedScore", "finalScore", "llmBonus"} <= set(data["best"])
    assert len(data["ranking"]) == 5
    assert data["messages"]
    assert data["knowledge_context"]
    assert {"title", "content", "score", "source"} <= set(data["knowledge_context"][0])
    assert isinstance(data["memory_context"], list)
    assert data["risk_context"]["risk_level"] in {"low", "medium", "high"}
    assert data["grounding_evidence"]["status"] == "grounded"
    assert data["grounding_evidence"]["proposal_grounding"]
    assert data["grounding_evidence"]["risk_grounding"]["evidence"]
    assert [step["tool_name"] for step in data["tool_plan"]["steps"]] == [
        "knowledge_retrieval",
        "memory_recall",
        "risk_analysis",
    ]
    assert data["tool_calls"]
    assert data["tool_metrics"]["total"] == 3
    assert data["tool_metrics"]["failed"] == 0
    assert data["plan_execution_audit"]["status"] == "passed"
    assert data["plan_execution_audit"]["sequence_match"] is True
    assert data["plan_execution_audit"]["planned_tools"] == [
        "knowledge_retrieval",
        "memory_recall",
        "risk_analysis",
    ]
    assert data["workflow_nodes"][0] == "plan_tools"
    assert data["workflow_nodes"][-1] == "finalize_decision"
    assert "audit_tool_plan_execution" in data["workflow_nodes"]
    assert "build_grounding_evidence" in data["workflow_nodes"]
    assert "audit_decision" in data["workflow_nodes"]
    assert data["decision_audit"]["checked_agent"] == data["best"]["proposal"]["agent_name"]
    assert {"tool_name", "status", "output", "metadata", "duration_ms"} <= set(data["tool_calls"][0])
    assert data["best"]["proposal"]["knowledge_sources"]
    assert "memory_sources" in data["best"]["proposal"]
    assert data["trace"][0]["step"] == "start"
    assert {"step", "message", "status", "metadata", "timestamp"} <= set(data["trace"][0])
    assert len(data["agent_generation"]) == 5
    assert {item["generation_mode"] for item in data["agent_generation"]} == {"rule"}
    assert {
        "agent_name",
        "strategy_name",
        "generation_mode",
        "model",
        "duration_ms",
        "validation_status",
        "fallback_reason",
        "knowledge_sources",
        "memory_sources",
        "metric_adjustments",
    } <= set(data["agent_generation"][0])
