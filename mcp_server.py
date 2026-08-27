from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from mcp.server.fastmcp import FastMCP

from memory import DecisionMemory, MemoryCase
from models import BattlefieldScene
from rag import KnowledgeRetriever, KnowledgeSnippet
from serializers import scene_to_dict
from settings import get_settings
from storage import DEFAULT_DB_PATH, ROOT
from tools import KnowledgeRetrievalTool, MemoryRecallTool, RiskAnalysisTool, ToolRegistry


SCENE_FIELDS = [
    "name",
    "objective",
    "terrain",
    "weather",
    "enemy_strength",
    "own_strength",
    "supply_level",
    "intel_quality",
    "urgency",
    "civilian_presence",
]

NUMERIC_SCENE_FIELDS = {
    "enemy_strength",
    "own_strength",
    "supply_level",
    "intel_quality",
    "urgency",
    "civilian_presence",
}


def build_agent_tool_registry(db_path: Path | str | None = None) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(KnowledgeRetrievalTool(KnowledgeRetriever.default()))
    registry.register(MemoryRecallTool(DecisionMemory.default(db_path or _settings_db_path())))
    registry.register(RiskAnalysisTool())
    return registry


def call_agent_tool(
    registry: ToolRegistry,
    tool_name: str,
    scene: Mapping[str, Any],
    top_k: int = 3,
    knowledge_context: list[Mapping[str, Any]] | None = None,
    memory_context: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    scene_obj = scene_from_payload(scene)
    bounded_top_k = clamp_top_k(top_k)

    if tool_name == "knowledge_retrieval":
        result = registry.run(tool_name, scene=scene_obj, top_k=bounded_top_k)
    elif tool_name == "memory_recall":
        result = registry.run(tool_name, scene=scene_obj, top_k=bounded_top_k)
    elif tool_name == "risk_analysis":
        result = registry.run(
            tool_name,
            scene=scene_obj,
            knowledge_context=knowledge_from_payload(knowledge_context or []),
            memory_context=memory_from_payload(memory_context or []),
        )
    else:
        raise ValueError(f"Unsupported MCP tool: {tool_name}")

    return result.to_dict()


def query_knowledge_hub(
    query: str,
    top_k: int = 3,
    retriever: KnowledgeRetriever | None = None,
) -> dict[str, Any]:
    cleaned_query = str(query or "").strip()
    if not cleaned_query:
        raise ValueError("query cannot be empty")

    active_retriever = retriever or KnowledgeRetriever.default()
    bounded_top_k = clamp_top_k(top_k)
    result = active_retriever.retrieve_query_with_trace(cleaned_query, top_k=bounded_top_k)
    return {
        "query": cleaned_query,
        "top_k": bounded_top_k,
        "collection": _knowledge_collection_payload(active_retriever),
        "snippets": [snippet.to_dict() for snippet in result.snippets],
        "metadata": result.to_metadata(),
    }


def list_knowledge_collections(
    retriever: KnowledgeRetriever | None = None,
) -> dict[str, Any]:
    active_retriever = retriever or KnowledgeRetriever.default()
    return {
        "collections": [_knowledge_collection_payload(active_retriever)],
    }


def get_retrieval_trace(
    query: str,
    top_k: int = 3,
    retriever: KnowledgeRetriever | None = None,
) -> dict[str, Any]:
    cleaned_query = str(query or "").strip()
    if not cleaned_query:
        raise ValueError("query cannot be empty")

    active_retriever = retriever or KnowledgeRetriever.default()
    bounded_top_k = clamp_top_k(top_k)
    result = active_retriever.retrieve_query_with_trace(cleaned_query, top_k=bounded_top_k)
    metadata = result.to_metadata()
    return {
        "query": cleaned_query,
        "top_k": bounded_top_k,
        "collection": _knowledge_collection_payload(active_retriever),
        "query_rewrite": metadata["query_rewrite"],
        "candidates_considered": metadata["candidates_considered"],
        "fusion_evidence": metadata["fusion_evidence"],
        "rerank_evidence": metadata["rerank_evidence"],
        "retrieval_trace": metadata["retrieval_trace"],
    }


def create_mcp_server(
    registry: ToolRegistry | None = None,
    host: str = "127.0.0.1",
    port: int = 8001,
) -> FastMCP:
    active_registry = registry or build_agent_tool_registry()
    active_knowledge_retriever = _knowledge_retriever_from_registry(active_registry)
    server = FastMCP(
        "message-talk-agent-tools",
        instructions=(
            "Expose the battlefield multi-agent decision tools as MCP tools. "
            "Use knowledge_retrieval before risk_analysis when battlefield scene evidence is needed. "
            "Use query_knowledge_hub and get_retrieval_trace for direct RAG knowledge-base inspection."
        ),
        host=host,
        port=port,
        json_response=True,
    )

    @server.tool(
        name="knowledge_retrieval",
        description="Retrieve RAG knowledge snippets for a battlefield scene with query rewrite and rerank evidence.",
        structured_output=True,
    )
    def mcp_knowledge_retrieval(scene: dict[str, Any], top_k: int = 3) -> dict[str, Any]:
        return call_agent_tool(active_registry, "knowledge_retrieval", scene=scene, top_k=top_k)

    @server.tool(
        name="memory_recall",
        description="Recall similar historical decision cases from local SQLite agent memory.",
        structured_output=True,
    )
    def mcp_memory_recall(scene: dict[str, Any], top_k: int = 3) -> dict[str, Any]:
        return call_agent_tool(active_registry, "memory_recall", scene=scene, top_k=top_k)

    @server.tool(
        name="risk_analysis",
        description="Analyze scene risk and optionally use RAG or memory context as upstream evidence.",
        structured_output=True,
    )
    def mcp_risk_analysis(
        scene: dict[str, Any],
        knowledge_context: list[dict[str, Any]] | None = None,
        memory_context: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return call_agent_tool(
            active_registry,
            "risk_analysis",
            scene=scene,
            knowledge_context=knowledge_context or [],
            memory_context=memory_context or [],
        )

    @server.tool(
        name="query_knowledge_hub",
        description="Directly query the local RAG knowledge base with hybrid retrieval and return snippets plus trace metadata.",
        structured_output=True,
    )
    def mcp_query_knowledge_hub(query: str, top_k: int = 3) -> dict[str, Any]:
        return query_knowledge_hub(
            query=query,
            top_k=top_k,
            retriever=active_knowledge_retriever,
        )

    @server.tool(
        name="list_knowledge_collections",
        description="List local RAG knowledge collections and expose vector index plus ingestion status.",
        structured_output=True,
    )
    def mcp_list_knowledge_collections() -> dict[str, Any]:
        return list_knowledge_collections(retriever=active_knowledge_retriever)

    @server.tool(
        name="get_retrieval_trace",
        description="Run a direct RAG query and return query rewrite, route fusion, rerank, and stage trace evidence.",
        structured_output=True,
    )
    def mcp_get_retrieval_trace(query: str, top_k: int = 3) -> dict[str, Any]:
        return get_retrieval_trace(
            query=query,
            top_k=top_k,
            retriever=active_knowledge_retriever,
        )

    @server.resource(
        "agent-tools://catalog",
        name="agent_tool_catalog",
        description="Tool catalog exported from the local Agent ToolRegistry.",
        mime_type="application/json",
    )
    def mcp_tool_catalog() -> str:
        return json.dumps([spec.to_dict() for spec in active_registry.specs()], ensure_ascii=False)

    @server.resource(
        "knowledge-hub://collections",
        name="knowledge_collection_status",
        description="Knowledge collection status exported from the local RAG retriever.",
        mime_type="application/json",
    )
    def mcp_knowledge_collections() -> str:
        return json.dumps(
            list_knowledge_collections(retriever=active_knowledge_retriever),
            ensure_ascii=False,
        )

    return server


def scene_from_payload(payload: Mapping[str, Any]) -> BattlefieldScene:
    if not isinstance(payload, Mapping):
        raise ValueError("scene must be an object")

    missing = [field for field in SCENE_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"scene missing required fields: {', '.join(missing)}")

    data: dict[str, Any] = {}
    for field in SCENE_FIELDS:
        value = payload[field]
        if field in NUMERIC_SCENE_FIELDS:
            data[field] = _bounded_int(field, value)
        else:
            text = str(value).strip()
            if not text:
                raise ValueError(f"scene field cannot be empty: {field}")
            data[field] = text
    return BattlefieldScene(**data)


def scene_to_payload(scene: BattlefieldScene) -> dict[str, Any]:
    return scene_to_dict(scene)


def clamp_top_k(value: Any, minimum: int = 1, maximum: int = 6) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def knowledge_from_payload(items: list[Mapping[str, Any]]) -> list[KnowledgeSnippet]:
    snippets: list[KnowledgeSnippet] = []
    for item in items:
        snippets.append(
            KnowledgeSnippet(
                title=str(item.get("title", "")).strip(),
                content=str(item.get("content", "")).strip(),
                score=float(item.get("score", 0.0)),
                source=str(item.get("source", "")).strip(),
            )
        )
    return snippets


def memory_from_payload(items: list[Mapping[str, Any]]) -> list[MemoryCase]:
    cases: list[MemoryCase] = []
    for item in items:
        matched_features = item.get("matched_features", [])
        if not isinstance(matched_features, list):
            matched_features = []
        cases.append(
            MemoryCase(
                record_id=int(item.get("record_id", 0)),
                scene_name=str(item.get("scene_name", "")).strip(),
                decision_mode=str(item.get("decision_mode", "")).strip(),
                best_agent=str(item.get("best_agent", "")).strip(),
                best_strategy=str(item.get("best_strategy", "")).strip(),
                similarity=float(item.get("similarity", 0.0)),
                matched_features=[str(value) for value in matched_features],
                created_at=str(item.get("created_at", "")).strip(),
            )
        )
    return cases


def _knowledge_retriever_from_registry(registry: ToolRegistry) -> KnowledgeRetriever:
    try:
        tool = registry.get("knowledge_retrieval")
    except KeyError:
        return KnowledgeRetriever.default()

    retriever = getattr(tool, "retriever", None)
    if hasattr(retriever, "retrieve_query_with_trace"):
        return retriever
    return KnowledgeRetriever.default()


def _knowledge_collection_payload(retriever: KnowledgeRetriever) -> dict[str, Any]:
    vector_store_stats = retriever.vector_store.stats()
    collection_name = str(
        vector_store_stats.get("collection")
        or getattr(retriever.vector_store, "collection", "tactical_knowledge")
    )
    embedding_payload: dict[str, Any] = {}
    if retriever.embedding_provider is not None:
        embedding_payload = {
            "provider": retriever.embedding_provider.name,
            "model": retriever.embedding_provider.model,
            "dimensions": retriever.embedding_provider.dimensions,
            "is_semantic": retriever.embedding_provider.is_semantic,
        }

    return {
        "name": collection_name,
        "documents_loaded": len(retriever.documents),
        "dense_enabled": retriever.dense_enabled,
        "embedding": embedding_payload,
        "vector_store": vector_store_stats,
        "vector_index": retriever.vector_index_stats,
        "ingestion": retriever.ingestion_result.to_dict() if retriever.ingestion_result else {},
    }


def _bounded_int(field: str, value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"scene field must be an integer: {field}") from exc
    if number < 0 or number > 100:
        raise ValueError(f"scene field must be between 0 and 100: {field}")
    return number


def _settings_db_path() -> Path:
    settings = get_settings()
    if settings.database_path:
        return ROOT / settings.database_path
    return DEFAULT_DB_PATH


mcp = create_mcp_server()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
