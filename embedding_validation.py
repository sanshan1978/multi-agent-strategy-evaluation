from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag.embeddings import EmbeddingProvider
from rag.vector_store import InMemoryVectorStore


@dataclass(frozen=True)
class EmbeddingValidationOptions:
    require_semantic: bool = True
    sample_texts: list[str] = field(
        default_factory=lambda: [
            "urban civilian collateral damage risk control",
            "mountain supply route reconnaissance",
            "high urgency command rhythm",
        ]
    )
    dense_probe_query: str = "urban civilian risk"
    expected_dense_title: str = "Urban Civilian Risk Control"


@dataclass(frozen=True)
class EmbeddingValidationReport:
    ok: bool
    provider: str
    model: str
    is_semantic: bool
    dimensions: int
    health: dict[str, Any]
    sample_count: int
    vector_count: int
    dense_probe: dict[str, Any]
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "model": self.model,
            "is_semantic": self.is_semantic,
            "dimensions": self.dimensions,
            "health": self.health,
            "sample_count": self.sample_count,
            "vector_count": self.vector_count,
            "dense_probe": self.dense_probe,
            "issues": self.issues,
        }


@dataclass(frozen=True)
class _ProbeDocument:
    title: str
    content: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


def validate_embedding_provider(
    provider: EmbeddingProvider,
    options: EmbeddingValidationOptions | None = None,
) -> EmbeddingValidationReport:
    active_options = options or EmbeddingValidationOptions()
    issues: list[str] = []
    health = provider.health_check().to_dict()
    if not health.get("ok"):
        issues.append(f"health check failed: {health.get('error', 'unknown error')}")
    if active_options.require_semantic and not provider.is_semantic:
        issues.append(
            f"embedding provider {provider.name} is not semantic; configure openai-compatible for real dense retrieval"
        )

    vectors: list[list[float]] = []
    try:
        vectors = provider.embed_texts(active_options.sample_texts)
        _validate_sample_vectors(vectors, expected_count=len(active_options.sample_texts), dimensions=provider.dimensions)
    except Exception as exc:  # noqa: BLE001 - validation reports provider boundary failures
        issues.append(f"sample embedding failed: {exc}")

    dense_probe = _run_dense_probe(provider, active_options, issues)
    return EmbeddingValidationReport(
        ok=not issues,
        provider=provider.name,
        model=provider.model,
        is_semantic=provider.is_semantic,
        dimensions=provider.dimensions,
        health=health,
        sample_count=len(active_options.sample_texts),
        vector_count=len(vectors),
        dense_probe=dense_probe,
        issues=issues,
    )


def _validate_sample_vectors(vectors: list[list[float]], *, expected_count: int, dimensions: int) -> None:
    if len(vectors) != expected_count:
        raise ValueError(f"sample vector count mismatch: expected {expected_count}, got {len(vectors)}")
    for vector in vectors:
        if not vector:
            raise ValueError("sample embedding vector cannot be empty")
        if len(vector) != dimensions:
            raise ValueError(f"sample vector dimension mismatch: expected {dimensions}, got {len(vector)}")


def _run_dense_probe(
    provider: EmbeddingProvider,
    options: EmbeddingValidationOptions,
    issues: list[str],
) -> dict[str, Any]:
    documents = [
        _ProbeDocument(
            title="Urban Civilian Risk Control",
            content="urban civilian collateral damage risk control",
            source="embedding_validation_probe",
        ),
        _ProbeDocument(
            title="Mountain Supply Route",
            content="mountain supply route reconnaissance resource efficiency",
            source="embedding_validation_probe",
        ),
        _ProbeDocument(
            title="High Urgency Command Rhythm",
            content="high urgency command rhythm rapid response",
            source="embedding_validation_probe",
        ),
    ]
    try:
        store = InMemoryVectorStore(collection="embedding_validation_probe")
        index_stats = store.upsert_documents(documents, provider, replace_collection=True)
        results = store.search(options.dense_probe_query, provider, top_k=1)
    except Exception as exc:  # noqa: BLE001 - dense probe reports provider/vector-store boundary failures
        issues.append(f"dense retrieval probe failed: {exc}")
        return {"ok": False, "top_title": "", "top_score": 0.0, "index": {}}

    top_title = results[0].document.title if results else ""
    top_score = float(results[0].score) if results else 0.0
    probe_ok = bool(results) and top_title == options.expected_dense_title
    if not probe_ok:
        issues.append(
            "dense retrieval probe missed expected title: "
            f"expected={options.expected_dense_title}, actual={top_title or 'none'}"
        )
    return {
        "ok": probe_ok,
        "query": options.dense_probe_query,
        "expected_title": options.expected_dense_title,
        "top_title": top_title,
        "top_score": round(top_score, 4),
        "index": index_stats,
    }
