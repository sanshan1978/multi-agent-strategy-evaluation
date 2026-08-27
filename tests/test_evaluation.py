from __future__ import annotations

from decision_engine import DecisionEngine
from evaluation import (
    AgentEvaluator,
    EvaluationCase,
    build_default_evaluation_cases,
    evaluate_case_result,
)
from memory import DecisionMemory
from models import BattlefieldScene
from storage import DecisionRecordStore


def _engine_factory(tmp_path):
    return lambda: DecisionEngine(
        llm_mode="off",
        decision_memory=DecisionMemory(DecisionRecordStore(tmp_path / "evaluation_records.db")),
    )


def test_default_agent_evaluation_cases_pass(tmp_path) -> None:
    evaluator = AgentEvaluator(_engine_factory(tmp_path))

    summary = evaluator.evaluate(build_default_evaluation_cases())

    assert summary.total_cases == 3
    assert summary.passed_cases == 3
    assert summary.pass_rate == 1.0
    assert summary.average_score == 100.0
    case_ids = {item.case_id for item in summary.results}
    assert case_ids == {
        "urban_high_pressure",
        "mountain_enemy_pressure",
        "plain_low_context_need",
    }
    urban_result = next(item for item in summary.results if item.case_id == "urban_high_pressure")
    check_names = {item.name for item in urban_result.checks}
    assert "rag_query_rewrite_present" in check_names
    assert "rag_rerank_evidence_present" in check_names
    assert "grounding_evidence_present" in check_names
    assert urban_result.metrics["grounding_status"] == "grounded"


def test_evaluation_reports_failed_expectations(tmp_path) -> None:
    scene = BattlefieldScene(
        name="plain eval failure probe",
        objective="probe evaluation failure reporting",
        terrain="plain",
        weather="clear",
        enemy_strength=62,
        own_strength=70,
        supply_level=79,
        intel_quality=76,
        urgency=72,
        civilian_presence=30,
    )
    result = _engine_factory(tmp_path)().run(scene)
    case = EvaluationCase(
        case_id="wrong_expectation",
        scene=scene,
        expected_tools=["knowledge_retrieval", "risk_analysis"],
        min_final_score=75.0,
        allowed_risk_levels={"low"},
    )

    case_result = evaluate_case_result(case, result)

    assert case_result.passed is False
    assert case_result.score < 100.0
    assert case_result.issues
    failed_checks = [item.name for item in case_result.checks if not item.passed]
    assert "tool_plan_matches_expected" in failed_checks
