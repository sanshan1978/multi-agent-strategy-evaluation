from __future__ import annotations

from dataclasses import dataclass

import chromadb
import pytest

from rag import ChromaVectorStore, LocalHashingEmbeddingProvider, SQLiteVectorStore
from rag.embeddings import EmbeddingHealth


@dataclass(frozen=True)
class Doc:
    title: str
    content: str
    source: str
    metadata: dict | None = None


class CountingEmbeddingProvider:
    name = "counting"
    model = "counting-v1"
    dimensions = 3
    is_semantic = True

    def __init__(self) -> None:
        self.embedded_text_count = 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.embedded_text_count += len(texts)
        return [[1.0, 0.0, 0.0] for _text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def health_check(self) -> EmbeddingHealth:
        return EmbeddingHealth(
            provider=self.name,
            model=self.model,
            ok=True,
            dimensions=self.dimensions,
            latency_ms=0.0,
        )


class EmptyChromaCollection:
    def count(self) -> int:
        return 0


class HealthyChromaClient:
    def __init__(self) -> None:
        self.collection = EmptyChromaCollection()

    def heartbeat(self) -> int:
        return 1

    def get_or_create_collection(self, **_kwargs):
        return self.collection


def test_sqlite_vector_store_persists_and_searches(tmp_path) -> None:
    db_path = tmp_path / "rag_vectors.db"
    provider = LocalHashingEmbeddingProvider(dimensions=32)
    docs = [
        Doc(
            title="Urban Safety",
            content="urban civilian risk control",
            source="kb.md",
            metadata={"section_title": "Urban Safety", "tags": ["urban"]},
        ),
        Doc(title="Mountain Delay", content="mountain defense delay", source="kb.md"),
    ]

    store = SQLiteVectorStore(db_path=db_path, collection="test")
    stats = store.upsert_documents(docs, provider)

    assert stats["upserted"] == 2
    assert stats["total"] == 2

    reopened = SQLiteVectorStore(db_path=db_path, collection="test")
    results = reopened.search("urban civilian", provider, top_k=1)

    assert results
    assert results[0].document.title == "Urban Safety"
    assert results[0].document.metadata["section_title"] == "Urban Safety"
    assert "vector_store:sqlite" in results[0].evidence
    assert reopened.stats()["document_count"] == 2


def test_sqlite_vector_store_skips_unchanged_documents(tmp_path) -> None:
    provider = CountingEmbeddingProvider()
    store = SQLiteVectorStore(db_path=tmp_path / "vectors.db", collection="test")
    doc = Doc(title="Urban Safety", content="urban civilian risk control", source="kb.md")

    first = store.upsert_documents([doc], provider)
    second = store.upsert_documents([doc], provider)
    changed = store.upsert_documents(
        [Doc(title="Urban Safety", content="urban civilian evacuation risk control", source="kb.md")],
        provider,
    )

    assert first["upserted"] == 1
    assert second["skipped"] == 1
    assert changed["upserted"] == 1
    assert provider.embedded_text_count == 2


def test_sqlite_vector_store_deletes_stale_documents(tmp_path) -> None:
    provider = LocalHashingEmbeddingProvider(dimensions=32)
    store = SQLiteVectorStore(db_path=tmp_path / "vectors.db", collection="test")
    docs = [
        Doc(title="Urban Safety", content="urban civilian risk control", source="kb.md"),
        Doc(title="Mountain Delay", content="mountain defense delay", source="kb.md"),
    ]

    store.upsert_documents(docs, provider)
    stats = store.upsert_documents(docs[:1], provider, replace_collection=True)

    assert stats["deleted"] == 1
    assert store.stats()["document_count"] == 1


def test_chroma_vector_store_persists_and_searches(tmp_path) -> None:
    provider = LocalHashingEmbeddingProvider(dimensions=32)
    docs = [
        Doc(
            title="Urban Safety",
            content="urban civilian risk control",
            source="kb.md",
            metadata={"section_title": "Urban Safety", "tags": ["urban", "risk"]},
        ),
        Doc(title="Mountain Delay", content="mountain defense delay", source="kb.md"),
    ]

    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection="test")
    stats = store.upsert_documents(docs, provider)

    assert stats["upserted"] == 2
    assert stats["total"] == 2

    reopened = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection="test")
    results = reopened.search("urban civilian", provider, top_k=1)

    assert results
    assert results[0].document.title == "Urban Safety"
    assert results[0].document.metadata["section_title"] == "Urban Safety"
    assert results[0].document.metadata["tags"] == ["urban", "risk"]
    assert "vector_store:chroma" in results[0].evidence
    assert reopened.stats()["document_count"] == 2


def test_chroma_vector_store_skips_unchanged_documents(tmp_path) -> None:
    provider = CountingEmbeddingProvider()
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection="test")
    doc = Doc(title="Urban Safety", content="urban civilian risk control", source="kb.md")

    first = store.upsert_documents([doc], provider)
    second = store.upsert_documents([doc], provider)
    changed = store.upsert_documents(
        [Doc(title="Urban Safety", content="urban civilian evacuation risk control", source="kb.md")],
        provider,
    )

    assert first["upserted"] == 1
    assert second["skipped"] == 1
    assert changed["upserted"] == 1
    assert provider.embedded_text_count == 2


def test_chroma_vector_store_deletes_stale_documents(tmp_path) -> None:
    provider = LocalHashingEmbeddingProvider(dimensions=32)
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection="test")
    docs = [
        Doc(title="Urban Safety", content="urban civilian risk control", source="kb.md"),
        Doc(title="Mountain Delay", content="mountain defense delay", source="kb.md"),
    ]

    store.upsert_documents(docs, provider)
    stats = store.upsert_documents(docs[:1], provider, replace_collection=True)

    assert stats["deleted"] == 1
    assert store.stats()["document_count"] == 1


def test_chroma_vector_store_uses_http_client(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def create_http_client(**kwargs):
        captured.update(kwargs)
        return HealthyChromaClient()

    monkeypatch.setattr(chromadb, "HttpClient", create_http_client)

    store = ChromaVectorStore(
        persist_directory=tmp_path / "unused",
        collection="test",
        mode="http",
        host="localhost",
        port=8001,
        ssl=False,
    )

    assert captured == {"host": "localhost", "port": 8001, "ssl": False}
    assert store.stats()["mode"] == "http"
    assert store.stats()["endpoint"] == "http://localhost:8001"


def test_chroma_vector_store_reports_unreachable_http_endpoint(tmp_path, monkeypatch) -> None:
    class OfflineChromaClient(HealthyChromaClient):
        def heartbeat(self) -> int:
            raise ConnectionError("offline")

    monkeypatch.setattr(chromadb, "HttpClient", lambda **_kwargs: OfflineChromaClient())

    with pytest.raises(RuntimeError, match=r"http://localhost:8001") as exc_info:
        ChromaVectorStore(
            persist_directory=tmp_path / "unused",
            collection="test",
            mode="http",
            host="localhost",
            port=8001,
            ssl=False,
        )

    assert "api_key" not in str(exc_info.value).lower()
