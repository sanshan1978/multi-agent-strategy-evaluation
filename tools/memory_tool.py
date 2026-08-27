from __future__ import annotations

import time

from memory import DecisionMemory
from models import BattlefieldScene
from tools.base import ToolResult, ToolSpec, measured_tool_result


class MemoryRecallTool:
    name = "memory_recall"

    def __init__(self, memory: DecisionMemory) -> None:
        self.memory = memory

    def run(self, scene: BattlefieldScene, top_k: int = 3) -> ToolResult:
        started_at = time.perf_counter()
        cases = self.memory.recall(scene, top_k=top_k)
        return measured_tool_result(
            tool_name=self.name,
            started_at=started_at,
            output=cases,
            metadata={
                "top_k": len(cases),
                "record_ids": [item.record_id for item in cases],
            },
        )

    def describe(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description="Recall similar historical decision cases from local SQLite memory.",
            input_schema={
                "type": "object",
                "required": ["scene"],
                "properties": {
                    "scene": {"type": "BattlefieldScene"},
                    "top_k": {"type": "integer", "default": 3, "minimum": 1},
                },
            },
            output_schema={
                "type": "array",
                "items": {
                    "type": "MemoryCase",
                    "fields": [
                        "memory_id",
                        "record_id",
                        "scene_name",
                        "best_agent",
                        "best_strategy",
                        "similarity",
                        "matched_features",
                        "summary",
                        "lessons",
                        "tags",
                        "risk_level",
                        "importance_score",
                    ],
                },
            },
            tags=["agent_memory", "sqlite", "case_recall", "long_term_memory"],
        )
