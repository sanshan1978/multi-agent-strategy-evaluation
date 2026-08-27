from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Protocol


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    status: str
    output: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "output": _serialize_value(self.output),
            "metadata": _serialize_value(self.metadata),
            "duration_ms": round(self.duration_ms, 3),
        }


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "tags": self.tags,
        }


@dataclass(frozen=True)
class ToolExecutionPolicy:
    max_attempts: int = 2
    slow_threshold_ms: float = 500.0


class AgentTool(Protocol):
    name: str

    def run(self, **kwargs: Any) -> ToolResult:
        ...


def measured_tool_result(
    tool_name: str,
    started_at: float,
    output: Any,
    metadata: Dict[str, Any] | None = None,
    status: str = "completed",
) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status=status,
        output=output,
        metadata=metadata or {},
        duration_ms=(time.perf_counter() - started_at) * 1000,
    )


def summarize_tool_results(results: list[ToolResult]) -> Dict[str, Any]:
    return {
        "total": len(results),
        "completed": sum(1 for item in results if item.status == "completed"),
        "failed": sum(1 for item in results if item.status == "failed"),
        "fallback_used": sum(1 for item in results if item.metadata.get("fallback_used") is True),
        "slow_calls": sum(1 for item in results if item.metadata.get("slow_call") is True),
        "total_duration_ms": round(sum(item.duration_ms for item in results), 3),
    }


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    return value
