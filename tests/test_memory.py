from __future__ import annotations

from decision_engine import DecisionEngine
from main import PRESET_SCENES
from memory import DecisionMemory, memory_importance_score, scene_similarity
from serializers import result_to_dict, scene_to_dict
from storage import DecisionRecordStore


def test_scene_similarity_scores_matching_scene_features() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    score, matched = scene_similarity(scene, scene_to_dict(scene))

    assert score > 0.95
    assert "terrain" in matched
    assert "urgency" in matched


def test_decision_memory_recalls_similar_history_case(tmp_path) -> None:
    store = DecisionRecordStore(tmp_path / "memory.db")
    scene = PRESET_SCENES["urban_fast_capture"]
    result = DecisionEngine(llm_mode="off", decision_memory=DecisionMemory(store)).run(scene)
    record_id = store.save_decision(scene=scene_to_dict(scene), result=result_to_dict(result))

    memory = DecisionMemory(store)
    cases = memory.recall(scene, top_k=1)

    assert len(cases) == 1
    assert cases[0].record_id == record_id
    assert cases[0].similarity > 0.95
    assert cases[0].best_strategy == result.best.proposal.strategy_name


def test_decision_memory_writes_summary_entry_and_recalls_it_first(tmp_path) -> None:
    store = DecisionRecordStore(tmp_path / "memory.db")
    scene = PRESET_SCENES["urban_fast_capture"]
    result = DecisionEngine(llm_mode="off", decision_memory=DecisionMemory(store)).run(scene)
    scene_data = scene_to_dict(scene)
    result_data = result_to_dict(result)
    record_id = store.save_decision(scene=scene_data, result=result_data)

    write_result = DecisionMemory(store).write_decision(
        record_id=record_id,
        scene=scene_data,
        result=result_data,
    )
    cases = DecisionMemory(store).recall(scene, top_k=1)

    assert write_result.written is True
    assert write_result.memory_id is not None
    assert write_result.importance_score >= 45.0
    assert "tool:knowledge_retrieval" in write_result.tags
    assert cases[0].memory_id == write_result.memory_id
    assert cases[0].record_id == record_id
    assert cases[0].summary
    assert cases[0].lessons
    assert cases[0].importance_score == write_result.importance_score


def test_memory_importance_score_uses_risk_audit_and_tool_metrics(tmp_path) -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    result = result_to_dict(DecisionEngine(llm_mode="off").run(scene))

    score = memory_importance_score(result)

    assert 45.0 <= score <= 100.0
