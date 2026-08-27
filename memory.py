from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from models import BattlefieldScene
from storage import DEFAULT_DB_PATH, DecisionRecordStore


NUMERIC_FEATURES = {
    "enemy_strength": 0.12,
    "own_strength": 0.12,
    "supply_level": 0.10,
    "intel_quality": 0.10,
    "urgency": 0.15,
    "civilian_presence": 0.15,
}


@dataclass(frozen=True)
class MemoryCase:
    record_id: int
    scene_name: str
    decision_mode: str
    best_agent: str
    best_strategy: str
    similarity: float
    matched_features: List[str]
    created_at: str
    memory_id: int | None = None
    summary: str = ""
    lessons: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    risk_level: str = ""
    importance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "record_id": self.record_id,
            "scene_name": self.scene_name,
            "decision_mode": self.decision_mode,
            "best_agent": self.best_agent,
            "best_strategy": self.best_strategy,
            "similarity": round(self.similarity, 4),
            "matched_features": self.matched_features,
            "created_at": self.created_at,
            "summary": self.summary,
            "lessons": self.lessons,
            "tags": self.tags,
            "risk_level": self.risk_level,
            "importance_score": round(self.importance_score, 2),
        }


@dataclass(frozen=True)
class MemoryWriteResult:
    written: bool
    record_id: int
    memory_id: int | None
    summary: str
    lessons: List[str]
    tags: List[str]
    importance_score: float
    policy: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "written": self.written,
            "record_id": self.record_id,
            "memory_id": self.memory_id,
            "summary": self.summary,
            "lessons": self.lessons,
            "tags": self.tags,
            "importance_score": round(self.importance_score, 2),
            "policy": self.policy,
            "reason": self.reason,
        }


class DecisionMemory:
    def __init__(self, store: DecisionRecordStore, max_records: int = 50) -> None:
        self.store = store
        self.max_records = max(1, max_records)

    @classmethod
    def default(cls, db_path: Path | str = DEFAULT_DB_PATH) -> "DecisionMemory":
        return cls(DecisionRecordStore(db_path))

    def write_decision(
        self,
        record_id: int,
        scene: Dict[str, Any],
        result: Dict[str, Any],
    ) -> MemoryWriteResult:
        summary = build_memory_summary(scene, result)
        lessons = build_memory_lessons(result)
        tags = build_memory_tags(scene, result)
        importance_score = memory_importance_score(result)
        should_write = should_write_memory(result, importance_score)
        if not should_write:
            return MemoryWriteResult(
                written=False,
                record_id=record_id,
                memory_id=None,
                summary=summary,
                lessons=lessons,
                tags=tags,
                importance_score=importance_score,
                policy="score_and_trace_quality",
                reason="importance_or_trace_quality_below_threshold",
            )

        best = result["best"]["proposal"]
        memory_id = self.store.save_memory_entry(
            record_id=record_id,
            scene=scene,
            summary=summary,
            lessons=lessons,
            tags=tags,
            risk_level=str(result.get("risk_context", {}).get("risk_level", "unknown")),
            best_agent=str(best.get("agent_name", "")),
            best_strategy=str(best.get("strategy_name", "")),
            importance_score=importance_score,
            write_policy="score_and_trace_quality",
        )
        return MemoryWriteResult(
            written=True,
            record_id=record_id,
            memory_id=memory_id,
            summary=summary,
            lessons=lessons,
            tags=tags,
            importance_score=importance_score,
            policy="score_and_trace_quality",
            reason="memory_entry_written",
        )

    def recall(self, scene: BattlefieldScene, top_k: int = 3) -> List[MemoryCase]:
        entries = self.store.list_memory_entries(limit=self.max_records)
        if entries:
            return self._recall_memory_entries(scene, entries, top_k=top_k)
        return self._recall_decision_records(scene, top_k=top_k)

    def _recall_memory_entries(self, scene: BattlefieldScene, entries: List[Any], top_k: int = 3) -> List[MemoryCase]:
        candidates: List[MemoryCase] = []
        for entry in entries:
            similarity, matched_features = scene_similarity(scene, entry.scene)
            if similarity <= 0:
                continue
            candidates.append(
                MemoryCase(
                    memory_id=entry.id,
                    record_id=entry.record_id,
                    scene_name=entry.scene_name,
                    decision_mode="memory-summary",
                    best_agent=entry.best_agent,
                    best_strategy=entry.best_strategy,
                    similarity=similarity,
                    matched_features=matched_features,
                    created_at=entry.created_at,
                    summary=entry.summary,
                    lessons=entry.lessons,
                    tags=entry.tags,
                    risk_level=entry.risk_level,
                    importance_score=entry.importance_score,
                )
            )
        return sorted(
            candidates,
            key=lambda item: (item.similarity, item.importance_score),
            reverse=True,
        )[: max(1, top_k)]

    def _recall_decision_records(self, scene: BattlefieldScene, top_k: int = 3) -> List[MemoryCase]:
        candidates: List[MemoryCase] = []
        for summary in self.store.list_records(limit=self.max_records):
            detail = self.store.get_record(summary.id)
            if detail is None:
                continue

            similarity, matched_features = scene_similarity(scene, detail.scene)
            if similarity <= 0:
                continue

            candidates.append(
                MemoryCase(
                    memory_id=None,
                    record_id=detail.id,
                    scene_name=detail.scene_name,
                    decision_mode=detail.decision_mode,
                    best_agent=detail.best_agent,
                    best_strategy=detail.best_strategy,
                    similarity=similarity,
                    matched_features=matched_features,
                    created_at=detail.created_at,
                )
            )

        return sorted(candidates, key=lambda item: item.similarity, reverse=True)[: max(1, top_k)]


def build_memory_summary(scene: Dict[str, Any], result: Dict[str, Any]) -> str:
    best = result["best"]["proposal"]
    risk_context = result.get("risk_context", {})
    audit = result.get("decision_audit", {})
    return (
        f"Scene={scene.get('name')} terrain={scene.get('terrain')} objective={scene.get('objective')}; "
        f"best={best.get('agent_name')}:{best.get('strategy_name')}; "
        f"risk={risk_context.get('risk_level', 'unknown')}({risk_context.get('risk_score', 'n/a')}); "
        f"audit={audit.get('overall_status', 'unknown')}."
    )


def build_memory_lessons(result: Dict[str, Any]) -> List[str]:
    lessons: List[str] = []
    best = result["best"]["proposal"]
    risk_context = result.get("risk_context", {})
    audit = result.get("decision_audit", {})
    tool_plan = result.get("tool_plan", {})
    tool_names = [step.get("tool_name") for step in tool_plan.get("steps", [])]

    lessons.append(f"Preferred strategy: {best.get('strategy_name')} by {best.get('agent_name')}.")
    risk_level = risk_context.get("risk_level", "unknown")
    lessons.append(f"Risk posture: {risk_level}; factors={','.join(risk_context.get('factors', []))}.")
    if "knowledge_retrieval" in tool_names:
        lessons.append("RAG context was useful before strategy generation.")
    if "memory_recall" in tool_names:
        lessons.append("Similar historical cases should be checked for this pressure pattern.")
    if audit.get("overall_status") == "review_recommended":
        lessons.append("Keep critic review findings visible before final execution.")
    return lessons


def build_memory_tags(scene: Dict[str, Any], result: Dict[str, Any]) -> List[str]:
    tags = [
        f"terrain:{scene.get('terrain', 'unknown')}",
        f"risk:{result.get('risk_context', {}).get('risk_level', 'unknown')}",
        f"audit:{result.get('decision_audit', {}).get('overall_status', 'unknown')}",
    ]
    tool_plan = result.get("tool_plan", {})
    for step in tool_plan.get("steps", []):
        tool_name = step.get("tool_name")
        if tool_name:
            tags.append(f"tool:{tool_name}")
    return _unique(tags)


def memory_importance_score(result: Dict[str, Any]) -> float:
    final_score = float(result.get("best", {}).get("finalScore", 0.0))
    risk_score = float(result.get("risk_context", {}).get("risk_score", 0.0))
    finding_count = float(result.get("decision_audit", {}).get("finding_count", 0.0))
    tool_total = float(result.get("tool_metrics", {}).get("total", 0.0))
    return min(100.0, final_score * 0.45 + risk_score * 0.35 + finding_count * 5.0 + tool_total * 3.0)


def should_write_memory(result: Dict[str, Any], importance_score: float) -> bool:
    trace = result.get("trace", [])
    final_score = float(result.get("best", {}).get("finalScore", 0.0))
    return importance_score >= 45.0 and final_score >= 60.0 and len(trace) >= 8


def scene_similarity(scene: BattlefieldScene, stored_scene: Dict[str, Any]) -> tuple[float, List[str]]:
    score = 0.0
    matched_features: List[str] = []

    if _text(stored_scene.get("terrain")) == scene.terrain.lower():
        score += 0.18
        matched_features.append("terrain")

    if _text(stored_scene.get("weather")) == scene.weather.lower():
        score += 0.08
        matched_features.append("weather")

    for feature, weight in NUMERIC_FEATURES.items():
        current_value = float(getattr(scene, feature))
        stored_value = _number(stored_scene.get(feature), default=current_value)
        closeness = max(0.0, 1.0 - abs(current_value - stored_value) / 100.0)
        score += weight * closeness
        if closeness >= 0.85:
            matched_features.append(feature)

    return min(score, 1.0), matched_features


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _unique(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
