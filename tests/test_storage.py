from __future__ import annotations

from decision_engine import DecisionEngine
from main import PRESET_SCENES
from serializers import result_to_dict, scene_to_dict
from storage import DecisionRecordStore


def test_decision_record_store_saves_and_reads_detail(tmp_path) -> None:
    store = DecisionRecordStore(tmp_path / "records.db")
    scene = PRESET_SCENES["urban_fast_capture"]
    result = DecisionEngine(llm_mode="off").run(scene)

    record_id = store.save_decision(scene=scene_to_dict(scene), result=result_to_dict(result))

    records = store.list_records()
    detail = store.get_record(record_id)

    assert len(records) == 1
    assert records[0].id == record_id
    assert records[0].scene_name == "城市快速夺控"
    assert detail is not None
    assert detail.scene["name"] == "城市快速夺控"
    assert detail.result["best"]["proposal"]["agent_name"] == result.best.proposal.agent_name


def test_decision_record_store_saves_and_lists_memory_entries(tmp_path) -> None:
    store = DecisionRecordStore(tmp_path / "records.db")
    scene = PRESET_SCENES["urban_fast_capture"]
    scene_data = scene_to_dict(scene)
    result_data = result_to_dict(DecisionEngine(llm_mode="off").run(scene))
    record_id = store.save_decision(scene=scene_data, result=result_data)

    memory_id = store.save_memory_entry(
        record_id=record_id,
        scene=scene_data,
        summary="summary",
        lessons=["lesson"],
        tags=["terrain:urban", "tool:knowledge_retrieval"],
        risk_level="medium",
        best_agent=result_data["best"]["proposal"]["agent_name"],
        best_strategy=result_data["best"]["proposal"]["strategy_name"],
        importance_score=77.5,
        write_policy="test_policy",
    )
    entries = store.list_memory_entries()

    assert memory_id >= 1
    assert len(entries) == 1
    assert entries[0].record_id == record_id
    assert entries[0].summary == "summary"
    assert entries[0].lessons == ["lesson"]
    assert "terrain:urban" in entries[0].tags
    assert entries[0].importance_score == 77.5


def test_decision_record_store_saves_and_reads_evaluation_reports(tmp_path) -> None:
    store = DecisionRecordStore(tmp_path / "records.db")
    summary = {
        "total_cases": 3,
        "passed_cases": 3,
        "pass_rate": 1.0,
        "average_score": 100.0,
        "results": [{"case_id": "urban_high_pressure", "passed": True}],
    }

    report_id = store.save_evaluation_report(report_type="agent", summary=summary)
    reports = store.list_evaluation_reports()
    detail = store.get_evaluation_report(report_id)

    assert report_id >= 1
    assert len(reports) == 1
    assert reports[0].id == report_id
    assert reports[0].report_type == "agent"
    assert reports[0].total_cases == 3
    assert reports[0].passed_cases == 3
    assert reports[0].pass_rate == 1.0
    assert detail is not None
    assert detail.summary["average_score"] == 100.0
    assert detail.summary["results"][0]["case_id"] == "urban_high_pressure"


def test_decision_record_store_returns_none_for_missing_record(tmp_path) -> None:
    store = DecisionRecordStore(tmp_path / "records.db")

    assert store.get_record(999) is None
    assert store.get_evaluation_report(999) is None
