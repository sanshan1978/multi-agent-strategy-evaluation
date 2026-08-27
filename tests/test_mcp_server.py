from __future__ import annotations

import asyncio
import pytest

from main import PRESET_SCENES
from mcp_server import (
    build_agent_tool_registry,
    call_agent_tool,
    clamp_top_k,
    create_mcp_server,
    get_retrieval_trace,
    list_knowledge_collections,
    query_knowledge_hub,
    scene_to_payload,
)


def test_call_agent_tool_runs_rag_with_mcp_payload(tmp_path) -> None:
    registry = build_agent_tool_registry(tmp_path / "mcp_records.db")
    scene = scene_to_payload(PRESET_SCENES["urban_fast_capture"])

    result = call_agent_tool(registry, "knowledge_retrieval", scene=scene, top_k=2)

    assert result["tool_name"] == "knowledge_retrieval"
    assert result["status"] == "completed"
    assert len(result["output"]) == 2
    assert "civilian_dense" in result["metadata"]["query_rewrite"]["expansions"]
    assert result["metadata"]["rerank_evidence"]


def test_call_agent_tool_chains_rag_output_into_risk_analysis(tmp_path) -> None:
    registry = build_agent_tool_registry(tmp_path / "mcp_records.db")
    scene = scene_to_payload(PRESET_SCENES["urban_fast_capture"])
    rag_result = call_agent_tool(registry, "knowledge_retrieval", scene=scene, top_k=2)

    risk_result = call_agent_tool(
        registry,
        "risk_analysis",
        scene=scene,
        knowledge_context=rag_result["output"],
    )

    evidence = risk_result["output"]["context_evidence"]
    assert risk_result["tool_name"] == "risk_analysis"
    assert evidence["knowledge_titles"]
    assert evidence["context_adjustment"] > 0


def test_call_agent_tool_validates_scene_payload(tmp_path) -> None:
    registry = build_agent_tool_registry(tmp_path / "mcp_records.db")
    scene = scene_to_payload(PRESET_SCENES["urban_fast_capture"])
    scene.pop("terrain")

    with pytest.raises(ValueError, match="scene missing required fields"):
        call_agent_tool(registry, "knowledge_retrieval", scene=scene)


def test_clamp_top_k_matches_tool_budget_policy() -> None:
    assert clamp_top_k(0) == 1
    assert clamp_top_k("bad") == 1
    assert clamp_top_k(9) == 6


def test_query_knowledge_hub_returns_snippets_with_trace() -> None:
    result = query_knowledge_hub("urban civilian collateral damage", top_k=2)

    assert result["query"] == "urban civilian collateral damage"
    assert result["top_k"] == 2
    assert result["collection"]["name"] == "tactical_knowledge"
    assert len(result["snippets"]) <= 2
    assert result["snippets"]
    assert result["metadata"]["query_rewrite"]["reasons"] == ["raw_query"]
    assert any(item["stage"] == "fusion" for item in result["metadata"]["retrieval_trace"])


def test_list_knowledge_collections_returns_index_and_ingestion_status() -> None:
    result = list_knowledge_collections()

    collection = result["collections"][0]
    assert collection["name"] == "tactical_knowledge"
    assert collection["documents_loaded"] > 0
    assert collection["vector_store"]["collection"] == "tactical_knowledge"
    assert collection["ingestion"]["chunks_total"] >= collection["documents_loaded"]


def test_get_retrieval_trace_returns_route_evidence_without_snippet_body() -> None:
    result = get_retrieval_trace("urban civilian collateral damage", top_k=2)

    assert result["query"] == "urban civilian collateral damage"
    assert result["top_k"] == 2
    assert result["query_rewrite"]["expanded_query"] == "urban civilian collateral damage"
    assert result["candidates_considered"] >= 1
    assert result["fusion_evidence"]
    assert result["rerank_evidence"]
    assert all("content" not in item for item in result["rerank_evidence"])
    assert any(item["stage"] == "dense_retrieval" for item in result["retrieval_trace"])


def test_fastmcp_server_exposes_agent_tools(tmp_path) -> None:
    registry = build_agent_tool_registry(tmp_path / "mcp_records.db")
    server = create_mcp_server(registry=registry)

    async def run_checks() -> None:
        tools = await server.list_tools()
        names = {tool.name for tool in tools}
        assert names == {
            "knowledge_retrieval",
            "memory_recall",
            "risk_analysis",
            "query_knowledge_hub",
            "list_knowledge_collections",
            "get_retrieval_trace",
        }

        scene = scene_to_payload(PRESET_SCENES["urban_fast_capture"])
        _content_blocks, payload = await server.call_tool("knowledge_retrieval", {"scene": scene, "top_k": 1})
        assert payload["tool_name"] == "knowledge_retrieval"
        assert len(payload["output"]) == 1
        assert payload["metadata"]["rerank_evidence"]

        _content_blocks, query_payload = await server.call_tool(
            "query_knowledge_hub",
            {"query": "urban civilian collateral damage", "top_k": 1},
        )
        assert len(query_payload["snippets"]) == 1
        assert query_payload["metadata"]["fusion_evidence"]

        _content_blocks, trace_payload = await server.call_tool(
            "get_retrieval_trace",
            {"query": "urban civilian collateral damage", "top_k": 1},
        )
        assert trace_payload["fusion_evidence"]

    asyncio.run(run_checks())
