from __future__ import annotations

import json

from fastapi.testclient import TestClient

import api_fastapi
from api_fastapi import app
from llm_strategy_agents import StrategyAgentGenerationError
from main import PRESET_SCENES
from models import AgentGenerationRecord
from storage import DecisionRecordStore


client = TestClient(app)


def _use_temp_store(monkeypatch, tmp_path) -> DecisionRecordStore:
    store = DecisionRecordStore(tmp_path / "api_records.db")
    monkeypatch.setattr(api_fastapi, "DECISION_STORE", store)
    return store


def _strict_generation_failure() -> StrategyAgentGenerationError:
    return StrategyAgentGenerationError(
        [
            AgentGenerationRecord(
                agent_name="防御智能体",
                strategy_name="弹性防御反击",
                generation_mode="rule-fallback",
                model="qwen3.7-plus",
                duration_ms=123.456,
                validation_status="failed",
                fallback_reason="model_timeout",
            )
        ]
    )


def _decision_payload(llm_mode: str = "on") -> dict[str, object]:
    scene = PRESET_SCENES["urban_fast_capture"]
    return {
        "scene": {
            "name": scene.name,
            "objective": scene.objective,
            "terrain": scene.terrain,
            "weather": scene.weather,
            "enemy_strength": scene.enemy_strength,
            "own_strength": scene.own_strength,
            "supply_level": scene.supply_level,
            "intel_quality": scene.intel_quality,
            "urgency": scene.urgency,
            "civilian_presence": scene.civilian_presence,
        },
        "llm_mode": llm_mode,
    }


def test_health_endpoint() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "message_talk"
    assert data["version"] == "0.2.0"


def test_request_id_header_is_preserved() -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "it-test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "it-test-request"
    assert float(response.headers["X-Response-Time-Ms"]) >= 0


def test_request_id_header_is_generated() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert len(response.headers["X-Request-ID"]) >= 16
    assert float(response.headers["X-Response-Time-Ms"]) >= 0


def test_scenarios_endpoint_returns_presets() -> None:
    response = client.get("/api/scenarios")

    assert response.status_code == 200
    data = response.json()
    assert "urban_fast_capture" in data
    assert data["urban_fast_capture"]["name"] == "城市快速夺控"


def test_tools_endpoint_returns_registered_agent_tools() -> None:
    response = client.get("/api/tools")

    assert response.status_code == 200
    data = response.json()
    names = {item["name"] for item in data}
    assert names == {"knowledge_retrieval", "memory_recall", "risk_analysis"}
    risk_tool = next(item for item in data if item["name"] == "risk_analysis")
    assert "scene" in risk_tool["input_schema"]["required"]
    assert risk_tool["output_schema"]["type"] == "object"


def test_evaluation_endpoint_returns_regression_report(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)

    response = client.post("/api/evaluations/run")
    records = client.get("/api/decisions").json()
    reports = client.get("/api/evaluations").json()

    assert response.status_code == 200
    data = response.json()
    assert data["report_id"] >= 1
    assert data["total_cases"] == 3
    assert data["passed_cases"] == 3
    assert data["pass_rate"] == 1.0
    assert data["average_score"] == 100.0
    assert {item["case_id"] for item in data["results"]} == {
        "urban_high_pressure",
        "mountain_enemy_pressure",
        "plain_low_context_need",
    }
    urban_result = next(item for item in data["results"] if item["case_id"] == "urban_high_pressure")
    assert any(item["name"] == "rag_query_rewrite_present" for item in urban_result["checks"])
    assert records == []
    assert len(reports) == 1
    assert reports[0]["id"] == data["report_id"]
    assert reports[0]["report_type"] == "agent"
    assert reports[0]["passed_cases"] == 3

    detail = client.get(f"/api/evaluations/{data['report_id']}").json()
    assert detail["id"] == data["report_id"]
    assert detail["report_type"] == "agent"
    assert detail["summary"]["total_cases"] == 3


def test_planner_and_rag_evaluation_reports_can_be_persisted(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)

    planner_response = client.post("/api/evaluations/planner/run")
    rag_response = client.post("/api/evaluations/rag/run")
    reports = client.get("/api/evaluations").json()

    assert planner_response.status_code == 200
    assert rag_response.status_code == 200
    assert planner_response.json()["report_id"] >= 1
    assert rag_response.json()["report_id"] >= 1
    report_types = {item["report_type"] for item in reports}
    assert {"planner", "rag"} <= report_types


def test_decide_endpoint_uses_schema_validation_and_returns_ranking(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    scene = PRESET_SCENES["urban_fast_capture"]
    response = client.post(
        "/api/decide",
        json={
            "scene": {
                "name": scene.name,
                "objective": scene.objective,
                "terrain": scene.terrain,
                "weather": scene.weather,
                "enemy_strength": scene.enemy_strength,
                "own_strength": scene.own_strength,
                "supply_level": scene.supply_level,
                "intel_quality": scene.intel_quality,
                "urgency": scene.urgency,
                "civilian_presence": scene.civilian_presence,
            },
            "llm_mode": "off",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decision_mode"] == "local-rules"
    assert len(data["ranking"]) == 5
    assert len(data["agent_generation"]) == 5
    assert {item["generation_mode"] for item in data["agent_generation"]} == {"rule"}
    assert data["best"]["finalScore"] == max(item["finalScore"] for item in data["ranking"])
    assert data["knowledge_context"]
    assert isinstance(data["memory_context"], list)
    assert data["risk_context"]["risk_level"] in {"low", "medium", "high"}
    assert data["risk_context"]["context_evidence"]["knowledge_titles"]
    assert data["risk_context"]["context_evidence"]["context_adjustment"] > 0
    assert [step["tool_name"] for step in data["tool_plan"]["steps"]] == [
        "knowledge_retrieval",
        "memory_recall",
        "risk_analysis",
    ]
    assert data["tool_plan"]["planner_source"] == "rule-based"
    assert data["tool_plan"]["planner_model"] is None
    assert data["tool_plan"]["planner_error"] is None
    assert [item["tool_name"] for item in data["tool_calls"]] == [
        "knowledge_retrieval",
        "memory_recall",
        "risk_analysis",
    ]
    assert data["tool_metrics"]["total"] == 3
    assert data["tool_metrics"]["failed"] == 0
    assert data["workflow_nodes"][0] == "plan_tools"
    assert data["workflow_nodes"][-1] == "finalize_decision"
    assert "audit_decision" in data["workflow_nodes"]
    assert data["decision_audit"]["checked_agent"] == data["best"]["proposal"]["agent_name"]
    assert data["decision_audit"]["overall_status"] in {"passed", "review_recommended", "attention_required"}
    assert data["best"]["proposal"]["knowledge_sources"]
    assert "memory_sources" in data["best"]["proposal"]
    assert any(item["step"] == "plan_tools" for item in data["trace"])
    assert any(item["step"] == "retrieve_knowledge" for item in data["trace"])
    retrieve_trace = next(item for item in data["trace"] if item["step"] == "retrieve_knowledge")
    assert "civilian_dense" in retrieve_trace["metadata"]["query_rewrite"]["expansions"]
    assert retrieve_trace["metadata"]["rerank_evidence"]
    assert any(item["step"] == "recall_memory" for item in data["trace"])
    assert any(item["step"] == "analyze_risk" for item in data["trace"])
    assert any(item["step"] == "audit_decision" for item in data["trace"])
    assert data["trace"][-1]["step"] == "finalize_decision"


def test_decide_endpoint_exposes_conditional_tool_skips(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    scene = PRESET_SCENES["plain_counterstrike"]
    response = client.post(
        "/api/decide",
        json={
            "scene": {
                "name": scene.name,
                "objective": scene.objective,
                "terrain": scene.terrain,
                "weather": scene.weather,
                "enemy_strength": scene.enemy_strength,
                "own_strength": scene.own_strength,
                "supply_level": scene.supply_level,
                "intel_quality": scene.intel_quality,
                "urgency": scene.urgency,
                "civilian_presence": scene.civilian_presence,
            },
            "llm_mode": "off",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert [step["tool_name"] for step in data["tool_plan"]["steps"]] == ["risk_analysis"]
    assert data["tool_plan"]["steps"][0]["need_score"] >= data["tool_plan"]["steps"][0]["threshold"]
    assert {step["tool_name"] for step in data["tool_plan"]["skipped_steps"]} == {
        "knowledge_retrieval",
        "memory_recall",
    }
    assert all(
        step["need_score"] < step["threshold"]
        for step in data["tool_plan"]["skipped_steps"]
    )
    assert [item["tool_name"] for item in data["tool_calls"]] == ["risk_analysis"]
    assert data["tool_metrics"]["total"] == 1
    assert any(
        item["step"] == "retrieve_knowledge" and item["status"] == "skipped"
        for item in data["trace"]
    )
    assert any(item["step"] == "recall_memory" and item["status"] == "skipped" for item in data["trace"])


def test_decide_endpoint_persists_history_record(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    scene = PRESET_SCENES["urban_fast_capture"]
    payload = {
        "scene": {
            "name": scene.name,
            "objective": scene.objective,
            "terrain": scene.terrain,
            "weather": scene.weather,
            "enemy_strength": scene.enemy_strength,
            "own_strength": scene.own_strength,
            "supply_level": scene.supply_level,
            "intel_quality": scene.intel_quality,
            "urgency": scene.urgency,
            "civilian_presence": scene.civilian_presence,
        },
        "llm_mode": "off",
    }

    decide_response = client.post("/api/decide", json=payload)
    list_response = client.get("/api/decisions")
    record_id = list_response.json()[0]["id"]
    detail_response = client.get(f"/api/decisions/{record_id}")
    memory_response = client.get("/api/memory")

    assert decide_response.status_code == 200
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["scene"]["name"] == scene.name
    assert detail_response.json()["result"]["decision_mode"] == "local-rules"
    assert detail_response.json()["result"]["knowledge_context"]
    assert isinstance(detail_response.json()["result"]["memory_context"], list)
    assert memory_response.status_code == 200
    memory_entries = memory_response.json()
    assert len(memory_entries) == 1
    assert memory_entries[0]["record_id"] == record_id
    assert memory_entries[0]["summary"]
    assert memory_entries[0]["lessons"]
    assert "tool:knowledge_retrieval" in memory_entries[0]["tags"]
    assert memory_entries[0]["importance_score"] >= 45.0


def test_decision_history_returns_404_for_missing_record(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)

    response = client.get("/api/decisions/999")

    assert response.status_code == 404
    assert response.json()["error_type"] == "record_not_found"


def test_decide_stream_returns_progress_result_and_persists_record(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    scene = PRESET_SCENES["urban_fast_capture"]
    payload = {
        "scene": {
            "name": scene.name,
            "objective": scene.objective,
            "terrain": scene.terrain,
            "weather": scene.weather,
            "enemy_strength": scene.enemy_strength,
            "own_strength": scene.own_strength,
            "supply_level": scene.supply_level,
            "intel_quality": scene.intel_quality,
            "urgency": scene.urgency,
            "civilian_presence": scene.civilian_presence,
        },
        "llm_mode": "off",
    }

    response = client.post("/api/decide/stream", json=payload)
    text = response.text
    records = client.get("/api/decisions").json()

    assert response.status_code == 200
    assert "event: progress" in text
    assert "event: result" in text
    assert "event: done" in text
    assert "event: error" not in text
    assert '"step": "plan_tools"' in text
    assert '"step": "retrieve_knowledge"' in text
    assert '"step": "recall_memory"' in text
    assert '"step": "analyze_risk"' in text
    assert '"step": "generate_proposals"' in text
    assert '"knowledge_context"' in text
    assert '"memory_context"' in text
    assert '"risk_context"' in text
    assert '"tool_plan"' in text
    assert '"tool_calls"' in text
    assert '"tool_metrics"' in text
    assert '"workflow_nodes"' in text
    assert '"decision_audit"' in text
    assert '"agent_generation"' in text
    assert '"decision_mode": "local-rules"' in text
    assert len(records) == 1


def test_decide_endpoint_rejects_invalid_score() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    response = client.post(
        "/api/decide",
        headers={"X-Request-ID": "invalid-score-request"},
        json={
            "scene": {
                "name": scene.name,
                "objective": scene.objective,
                "terrain": scene.terrain,
                "weather": scene.weather,
                "enemy_strength": 101,
                "own_strength": scene.own_strength,
                "supply_level": scene.supply_level,
                "intel_quality": scene.intel_quality,
                "urgency": scene.urgency,
                "civilian_presence": scene.civilian_presence,
            },
            "llm_mode": "off",
        },
    )

    assert response.status_code == 422
    data = response.json()
    assert data["error_type"] == "validation_error"
    assert data["request_id"] == "invalid-score-request"
    assert response.headers["X-Request-ID"] == "invalid-score-request"
    assert data["error"] == "请求参数校验失败"


def test_decide_endpoint_returns_missing_api_key_error_in_on_mode(monkeypatch) -> None:
    for key in [
        "MESSAGE_TALK_API_KEY",
        "SAFETY_AGENT_API_KEY",
        "DASHSCOPE_API_KEY",
        "API_KEY",
        "OPENAI_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)
    scene = PRESET_SCENES["urban_fast_capture"]

    response = client.post(
        "/api/decide",
        json={
            "scene": {
                "name": scene.name,
                "objective": scene.objective,
                "terrain": scene.terrain,
                "weather": scene.weather,
                "enemy_strength": scene.enemy_strength,
                "own_strength": scene.own_strength,
                "supply_level": scene.supply_level,
                "intel_quality": scene.intel_quality,
                "urgency": scene.urgency,
                "civilian_presence": scene.civilian_presence,
            },
            "llm_mode": "on",
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error_type"] == "missing_api_key"


def test_decide_strict_agent_failure_exposes_structured_details(monkeypatch) -> None:
    class FailingEngine:
        def run(self, scene):
            raise _strict_generation_failure()

    monkeypatch.setattr(api_fastapi, "_build_decision_engine", lambda **_: FailingEngine())

    response = client.post("/api/decide", json=_decision_payload())

    assert response.status_code == 502
    data = response.json()
    assert data["error_type"] == "llm_call_failed"
    assert data["details"]["failures"][0]["agent_name"] == "防御智能体"
    assert data["details"]["failures"][0]["fallback_reason"] == "model_timeout"
    assert data["details"]["failures"][0]["model"] == "qwen3.7-plus"
    assert data["details"]["failures"][0]["duration_ms"] == 123.456


def test_decide_stream_strict_agent_failure_exposes_structured_details(monkeypatch) -> None:
    class FailingStreamEngine:
        def run_stream(self, scene):
            raise _strict_generation_failure()
            yield  # pragma: no cover - keeps this method a generator

    monkeypatch.setattr(api_fastapi, "_build_decision_engine", lambda **_: FailingStreamEngine())

    response = client.post("/api/decide/stream", json=_decision_payload())
    data_line = next(line for line in response.text.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))

    assert response.status_code == 200
    assert "event: error" in response.text
    assert payload["error_type"] == "llm_call_failed"
    assert payload["details"]["failures"][0]["fallback_reason"] == "model_timeout"
