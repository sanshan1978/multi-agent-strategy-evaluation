from __future__ import annotations

import time
from typing import Any, Dict

from tools.base import AgentTool, ToolExecutionPolicy, ToolResult, ToolSpec


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool not registered: {name}") from exc

    def run(self, name: str, **kwargs: Any) -> ToolResult:
        return self.get(name).run(**kwargs)

    def run_with_policy(
        self,
        name: str,
        fallback_output: Any = None,
        policy: ToolExecutionPolicy | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        tool = self.get(name)
        execution_policy = policy or ToolExecutionPolicy()
        started_at = time.perf_counter()
        last_error: Exception | None = None
        attempts = max(1, execution_policy.max_attempts)

        for attempt in range(1, attempts + 1):
            try:
                result = tool.run(**kwargs)
                metadata = {
                    **result.metadata,
                    "attempts": attempt,
                    "max_attempts": attempts,
                    "fallback_used": False,
                    "slow_call": result.duration_ms >= execution_policy.slow_threshold_ms,
                }
                return ToolResult(
                    tool_name=result.tool_name,
                    status=result.status,
                    output=result.output,
                    metadata=metadata,
                    duration_ms=result.duration_ms,
                )
            except Exception as exc:  # noqa: BLE001 - tools are isolated boundaries
                last_error = exc

        return ToolResult(
            tool_name=name,
            status="failed",
            output=fallback_output,
            metadata={
                "error": str(last_error) if last_error else "unknown tool error",
                "attempts": attempts,
                "max_attempts": attempts,
                "fallback_used": True,
                "slow_call": ((time.perf_counter() - started_at) * 1000) >= execution_policy.slow_threshold_ms,
            },
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        for name in self.names():
            tool = self._tools[name]
            describe = getattr(tool, "describe", None)
            if callable(describe):
                specs.append(describe())
                continue
            specs.append(
                ToolSpec(
                    name=name,
                    description="Registered agent tool",
                    input_schema={"type": "object", "properties": {}},
                    output_schema={"type": "object"},
                    tags=["agent_tool"],
                )
            )
        return specs
