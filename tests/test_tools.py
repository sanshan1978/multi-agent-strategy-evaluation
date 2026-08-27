from __future__ import annotations

import pytest

from memory import MemoryCase
from main import PRESET_SCENES
from rag import KnowledgeSnippet
from rag import KnowledgeRetriever
from tools import (
    KnowledgeRetrievalTool,
    RiskAnalysisTool,
    ToolExecutionPolicy,
    ToolRegistry,
    ToolResult,
    summarize_tool_results,
)


class FailingTool:
    name = "failing_tool"

    def __init__(self) -> None:
        self.calls = 0

    def run(self) -> ToolResult:
        self.calls += 1
        raise RuntimeError("simulated tool failure")


def test_tool_registry_runs_registered_tool() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    registry = ToolRegistry()
    registry.register(RiskAnalysisTool())

    result = registry.run("risk_analysis", scene=scene)

    assert registry.names() == ["risk_analysis"]
    assert result.tool_name == "risk_analysis"
    assert result.status == "completed"
    assert result.duration_ms >= 0
    assert result.output["risk_level"] in {"low", "medium", "high"}
    assert result.metadata["factor_count"] == len(result.output["factors"])


def test_knowledge_retrieval_tool_exposes_rag_pipeline_metadata() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    tool = KnowledgeRetrievalTool(KnowledgeRetriever.default())

    result = tool.run(scene=scene, top_k=3)

    assert result.output
    assert "query_rewrite" in result.metadata
    assert "civilian_dense" in result.metadata["query_rewrite"]["expansions"]
    assert result.metadata["candidates_considered"] >= len(result.output)
    assert result.metadata["rerank_evidence"]
    assert result.metadata["fusion_evidence"]
    assert any(stage["stage"] == "fusion" for stage in result.metadata["retrieval_trace"])


def test_risk_analysis_uses_knowledge_and_memory_context() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    tool = RiskAnalysisTool()

    result = tool.run(
        scene=scene,
        knowledge_context=[
            KnowledgeSnippet(
                title="Urban Civilian Risk Control",
                content="tags: urban civilian_dense risk_control collateral_damage reconnaissance",
                score=1.2,
                source="test.md",
            )
        ],
        memory_context=[
            MemoryCase(
                record_id=7,
                scene_name="similar urban case",
                decision_mode="local-rules",
                best_agent="risk agent",
                best_strategy="controlled advance",
                similarity=0.88,
                matched_features=["terrain", "civilian_presence"],
                created_at="2026-01-01T00:00:00+00:00",
            )
        ],
    )

    evidence = result.output["context_evidence"]
    assert evidence["context_adjustment"] > 0
    assert "knowledge_civilian_risk" in evidence["signals"]
    assert "memory_similar_case_pressure" in evidence["signals"]
    assert result.metadata["knowledge_evidence_count"] == 1
    assert result.metadata["memory_evidence_count"] == 1


def test_tool_registry_exports_tool_specs() -> None:
    registry = ToolRegistry()
    registry.register(RiskAnalysisTool())

    specs = registry.specs()

    assert len(specs) == 1
    assert specs[0].name == "risk_analysis"
    assert "scene" in specs[0].input_schema["required"]
    assert "knowledge_context" in specs[0].input_schema["properties"]
    assert "memory_context" in specs[0].input_schema["properties"]
    assert "risk" in specs[0].tags
    assert "context_aware" in specs[0].tags
    assert specs[0].to_dict()["output_schema"]["type"] == "object"


def test_tool_registry_rejects_unknown_tool() -> None:
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="Tool not registered"):
        registry.run("missing_tool")


def test_tool_registry_returns_fallback_after_retries() -> None:
    tool = FailingTool()
    registry = ToolRegistry()
    registry.register(tool)

    result = registry.run_with_policy(
        "failing_tool",
        fallback_output={"fallback": True},
        policy=ToolExecutionPolicy(max_attempts=2),
    )

    assert tool.calls == 2
    assert result.status == "failed"
    assert result.output == {"fallback": True}
    assert result.metadata["fallback_used"] is True
    assert result.metadata["attempts"] == 2
    assert "simulated tool failure" in result.metadata["error"]


def test_tool_result_summary_counts_failures_and_fallbacks() -> None:
    results = [
        ToolResult(tool_name="ok", status="completed", output={}, duration_ms=1.2),
        ToolResult(
            tool_name="bad",
            status="failed",
            output={},
            metadata={"fallback_used": True},
            duration_ms=2.3,
        ),
    ]

    summary = summarize_tool_results(results)

    assert summary["total"] == 2
    assert summary["completed"] == 1
    assert summary["failed"] == 1
    assert summary["fallback_used"] == 1
    assert summary["total_duration_ms"] == 3.5
