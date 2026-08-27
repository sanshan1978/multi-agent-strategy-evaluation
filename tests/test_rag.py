from __future__ import annotations

from pathlib import Path

from main import PRESET_SCENES
from rag import LocalHashingEmbeddingProvider
from rag import KnowledgeRetriever
from rag import retriever as retriever_module
from scripts import build_rag_index


def test_local_hashing_embedding_provider_is_deterministic() -> None:
    provider = LocalHashingEmbeddingProvider(dimensions=32)

    first = provider.embed_query("urban civilian risk")
    second = provider.embed_query("urban civilian risk")

    assert first == second
    assert len(first) == 32
    assert any(value != 0 for value in first)


def test_rag_retriever_returns_scene_related_snippets() -> None:
    retriever = KnowledgeRetriever.default()
    scene = PRESET_SCENES["urban_fast_capture"]

    snippets = retriever.retrieve_for_scene(scene, top_k=3)

    assert snippets
    assert len(snippets) <= 3
    assert snippets[0].score > 0
    assert any("Urban" in item.title or "Urgency" in item.title for item in snippets)


def test_rag_retriever_rewrites_query_and_reranks_candidates() -> None:
    retriever = KnowledgeRetriever.default()
    scene = PRESET_SCENES["urban_fast_capture"]

    result = retriever.retrieve_for_scene_with_trace(scene, top_k=3)

    assert result.snippets
    assert "civilian_dense" in result.query_rewrite.expansions
    assert "high_urgency" in result.query_rewrite.expansions
    assert "low_intel" in result.query_rewrite.expansions
    assert result.candidates_considered >= len(result.snippets)
    assert result.rerank_evidence
    assert {"title", "bm25_score", "rerank_score", "matched_signals"} <= set(result.rerank_evidence[0])
    assert result.fusion_evidence
    assert any(item["stage"] == "fusion" and item["method"] == "rrf" for item in result.retrieval_trace)
    assert any(item["stage"] == "dense_retrieval" for item in result.retrieval_trace)
    assert any(
        contribution["route"] == "scene_signal"
        for item in result.fusion_evidence
        for contribution in item["contributions"]
    )
    assert any(
        contribution["route"] == "embedding_dense"
        for item in result.fusion_evidence
        for contribution in item["contributions"]
    )
    dense_stage = next(item for item in result.retrieval_trace if item["stage"] == "dense_retrieval")
    assert dense_stage["details"]["ingestion"]["chunks_total"] >= len(result.snippets)


def test_rag_retriever_supports_direct_query_trace() -> None:
    retriever = KnowledgeRetriever.default()

    result = retriever.retrieve_query_with_trace("urban civilian collateral damage", top_k=2)

    assert len(result.snippets) <= 2
    assert result.snippets
    assert result.query_rewrite.original_query == "urban civilian collateral damage"
    assert result.query_rewrite.expanded_query == "urban civilian collateral damage"
    assert result.query_rewrite.reasons == ["raw_query"]
    assert result.candidates_considered >= len(result.snippets)
    assert any(item["stage"] == "sparse_retrieval" for item in result.retrieval_trace)
    assert any(item["stage"] == "dense_retrieval" for item in result.retrieval_trace)
    assert any(item["stage"] == "fusion" for item in result.retrieval_trace)
    assert any(item["stage"] == "rerank" and item["method"] == "query_score_boost" for item in result.retrieval_trace)
    assert result.fusion_evidence
    assert result.rerank_evidence


def test_rag_retriever_default_can_use_chroma_vector_store(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MESSAGE_TALK_VECTOR_STORE", "chroma")
    monkeypatch.setenv("MESSAGE_TALK_VECTOR_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("MESSAGE_TALK_CHROMA_MODE", "persistent")
    monkeypatch.setenv("MESSAGE_TALK_INGESTION_HISTORY_DB_PATH", str(tmp_path / "ingestion.db"))

    retriever = KnowledgeRetriever.default()
    result = retriever.retrieve_query_with_trace("urban civilian collateral damage", top_k=2)
    dense_stage = next(item for item in result.retrieval_trace if item["stage"] == "dense_retrieval")

    assert retriever.vector_store.name == "chroma"
    assert result.snippets
    assert dense_stage["details"]["vector_store"] == "chroma"
    assert dense_stage["details"]["vector_store_stats"]["document_count"] >= len(result.snippets)


def test_rag_vector_store_factory_passes_chroma_http_options(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def create_chroma_store(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(retriever_module, "ChromaVectorStore", create_chroma_store)

    retriever_module._create_vector_store(
        store_name="chroma",
        db_path=Path(tmp_path / "unused"),
        collection="test",
        chroma_mode="http",
        chroma_host="localhost",
        chroma_port=8001,
        chroma_ssl=False,
    )

    assert captured["mode"] == "http"
    assert captured["host"] == "localhost"
    assert captured["port"] == 8001
    assert captured["ssl"] is False


def test_build_rag_index_accepts_chroma_http_options() -> None:
    args = build_rag_index._parse_args(
        [
            "--chroma-mode",
            "http",
            "--chroma-host",
            "localhost",
            "--chroma-port",
            "8001",
            "--chroma-ssl",
        ]
    )

    assert args.chroma_mode == "http"
    assert args.chroma_host == "localhost"
    assert args.chroma_port == 8001
    assert args.chroma_ssl is True


def test_rag_scene_query_adds_pressure_tags() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]

    query = KnowledgeRetriever.build_scene_query(scene)

    assert "urban" in query
    assert "civilian_dense" in query
    assert "high_urgency" in query
