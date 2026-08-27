from __future__ import annotations

import time

from models import BattlefieldScene
from rag import KnowledgeRetriever
from tools.base import ToolResult, ToolSpec, measured_tool_result


class KnowledgeRetrievalTool:
    name = "knowledge_retrieval"

    def __init__(self, retriever: KnowledgeRetriever) -> None:
        self.retriever = retriever

    def run(self, scene: BattlefieldScene, top_k: int = 3) -> ToolResult:
        started_at = time.perf_counter()
        result = self.retriever.retrieve_for_scene_with_trace(scene, top_k=top_k)
        snippets = result.snippets
        retrieval_metadata = result.to_metadata()
        return measured_tool_result(
            tool_name=self.name,
            started_at=started_at,
            output=snippets,
            metadata={
                "top_k": len(snippets),
                "titles": [item.title for item in snippets],
                **retrieval_metadata,
            },
        )

    def describe(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description="Retrieve tactical knowledge snippets for the current battlefield scene.",
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
                    "type": "KnowledgeSnippet",
                    "fields": ["title", "content", "score", "source"],
                },
            },
            tags=["rag", "knowledge", "retrieval", "query_rewrite", "rerank"],
        )
