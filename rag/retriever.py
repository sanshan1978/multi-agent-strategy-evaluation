from __future__ import annotations

import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List

from models import BattlefieldScene
from settings import get_settings

from .embeddings import EmbeddingConfig, EmbeddingProvider, create_embedding_provider
from .ingestion import DocumentChunk, IngestionResult, MarkdownIngestionPipeline
from .vector_store import ChromaVectorStore, InMemoryVectorStore, SQLiteVectorStore


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class KnowledgeSnippet:
    title: str
    content: str
    score: float
    source: str

    def to_dict(self) -> dict[str, str | float]:
        return {
            "title": self.title,
            "content": self.content,
            "score": round(self.score, 4),
            "source": self.source,
        }


@dataclass(frozen=True)
class QueryRewrite:
    original_query: str
    expanded_query: str
    expansions: List[str]
    reasons: List[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "expanded_query": self.expanded_query,
            "expansions": self.expansions,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class RetrievalResult:
    snippets: List[KnowledgeSnippet]
    query_rewrite: QueryRewrite
    candidates_considered: int
    rerank_evidence: List[dict[str, Any]]
    fusion_evidence: List[dict[str, Any]]
    retrieval_trace: List[dict[str, Any]]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "query_rewrite": self.query_rewrite.to_dict(),
            "candidates_considered": self.candidates_considered,
            "rerank_evidence": self.rerank_evidence,
            "fusion_evidence": self.fusion_evidence,
            "retrieval_trace": self.retrieval_trace,
        }


@dataclass(frozen=True)
class KnowledgeDocument:
    title: str
    content: str
    source: str
    tokens: Counter[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteCandidate:
    document: KnowledgeDocument
    route: str
    score: float
    evidence: List[str]


@dataclass(frozen=True)
class FusedCandidate:
    document: KnowledgeDocument
    rrf_score: float
    route_scores: dict[str, float]
    contributions: List[dict[str, Any]]


class KnowledgeRetriever:
    def __init__(
        self,
        documents: List[KnowledgeDocument],
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: InMemoryVectorStore | SQLiteVectorStore | ChromaVectorStore | None = None,
        dense_enabled: bool = True,
        rrf_k: int = 60,
        strict_dense: bool = False,
        dense_initialization_error: str | None = None,
        ingestion_result: IngestionResult | None = None,
    ) -> None:
        self.documents = documents
        self.doc_count = len(documents)
        self.avg_doc_len = (
            sum(sum(doc.tokens.values()) for doc in documents) / max(len(documents), 1)
        )
        self.doc_frequency = self._build_doc_frequency(documents)
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store or InMemoryVectorStore()
        self.dense_enabled = dense_enabled and embedding_provider is not None
        self.rrf_k = rrf_k
        self.strict_dense = strict_dense
        self.ingestion_result = ingestion_result
        self.dense_initialization_error = dense_initialization_error
        if self.dense_enabled and self.embedding_provider is not None:
            try:
                self.vector_index_stats = self.vector_store.upsert_documents(
                    self.documents,
                    self.embedding_provider,
                    replace_collection=True,
                )
            except Exception as exc:  # noqa: BLE001 - dense retrieval is optional
                if self.strict_dense:
                    raise RuntimeError(f"dense retrieval initialization failed: {exc}") from exc
                self.dense_enabled = False
                self.dense_initialization_error = str(exc)
                self.vector_index_stats = {"upserted": 0, "skipped": 0, "deleted": 0, "total": 0}
        else:
            self.vector_index_stats = {"upserted": 0, "skipped": 0, "deleted": 0, "total": 0}

    @classmethod
    def from_directory(
        cls,
        directory: Path,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: InMemoryVectorStore | SQLiteVectorStore | ChromaVectorStore | None = None,
        dense_enabled: bool = True,
        rrf_k: int = 60,
        strict_dense: bool = False,
        dense_initialization_error: str | None = None,
        ingestion_history_db_path: Path | str | None = None,
        collection: str = "tactical_knowledge",
        chunk_size: int = 900,
        chunk_overlap: int = 120,
    ) -> "KnowledgeRetriever":
        history_path = ingestion_history_db_path or Path(__file__).resolve().parent.parent / "data" / "rag_ingestion.db"
        pipeline = MarkdownIngestionPipeline(
            directory,
            history_db_path=history_path,
            collection=collection,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        ingestion_result = pipeline.run()
        documents = [_document_from_chunk(chunk) for chunk in ingestion_result.chunks]
        return cls(
            documents,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            dense_enabled=dense_enabled,
            rrf_k=rrf_k,
            strict_dense=strict_dense,
            dense_initialization_error=dense_initialization_error,
            ingestion_result=ingestion_result,
        )

    @classmethod
    def default(cls) -> "KnowledgeRetriever":
        settings = get_settings()
        embedding_provider: EmbeddingProvider | None = None
        dense_initialization_error: str | None = None

        if settings.rag_dense_enabled:
            try:
                embedding_provider = create_embedding_provider(
                    EmbeddingConfig(
                        provider=settings.embedding_provider,
                        model=settings.embedding_model,
                        api_key=settings.embedding_api_key,
                        base_url=settings.embedding_base_url,
                        dimensions=settings.embedding_dimensions,
                        timeout_sec=settings.embedding_timeout_sec,
                        batch_size=settings.embedding_batch_size,
                        max_retries=settings.embedding_max_retries,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - RAG falls back to sparse retrieval
                if settings.rag_strict_embedding:
                    raise
                dense_initialization_error = str(exc)

        vector_store = _create_vector_store(
            store_name=settings.vector_store,
            db_path=Path(settings.vector_db_path),
            collection=settings.vector_collection,
            chroma_mode=settings.chroma_mode,
            chroma_host=settings.chroma_host,
            chroma_port=settings.chroma_port,
            chroma_ssl=settings.chroma_ssl,
        )

        return cls.from_directory(
            Path(__file__).resolve().parent / "documents",
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            dense_enabled=settings.rag_dense_enabled,
            rrf_k=settings.rag_rrf_k,
            strict_dense=settings.rag_strict_embedding,
            dense_initialization_error=dense_initialization_error,
            ingestion_history_db_path=_resolve_project_path(Path(settings.ingestion_history_db_path)),
            collection=settings.vector_collection,
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )

    def retrieve_for_scene(self, scene: BattlefieldScene, top_k: int = 3) -> List[KnowledgeSnippet]:
        return self.retrieve_for_scene_with_trace(scene=scene, top_k=top_k).snippets

    def retrieve_for_scene_with_trace(self, scene: BattlefieldScene, top_k: int = 3) -> RetrievalResult:
        started_at = time.perf_counter()
        query_rewrite = self.rewrite_scene_query(scene)
        return self._retrieve_with_trace(
            query_rewrite=query_rewrite,
            top_k=top_k,
            scene=scene,
            query_processing_trace=_stage_trace(
                stage="query_processing",
                method="scene_query_rewrite",
                started_at=started_at,
                input_count=1,
                output_count=1,
                details=query_rewrite.to_dict(),
            ),
        )

    def retrieve_query_with_trace(self, query: str, top_k: int = 3) -> RetrievalResult:
        started_at = time.perf_counter()
        cleaned_query = str(query or "").strip()
        query_rewrite = QueryRewrite(
            original_query=cleaned_query,
            expanded_query=cleaned_query,
            expansions=[],
            reasons=["raw_query"] if cleaned_query else ["empty_query"],
        )
        return self._retrieve_with_trace(
            query_rewrite=query_rewrite,
            top_k=top_k,
            scene=None,
            query_processing_trace=_stage_trace(
                stage="query_processing",
                method="raw_query",
                started_at=started_at,
                input_count=1 if cleaned_query else 0,
                output_count=1 if cleaned_query else 0,
                details=query_rewrite.to_dict(),
            ),
        )

    def _retrieve_with_trace(
        self,
        *,
        query_rewrite: QueryRewrite,
        top_k: int,
        scene: BattlefieldScene | None,
        query_processing_trace: dict[str, Any],
    ) -> RetrievalResult:
        result_limit = max(1, int(top_k))
        retrieval_trace: List[dict[str, Any]] = [query_processing_trace]

        candidate_limit = max(result_limit * 3, result_limit, 6)
        started_at = time.perf_counter()
        bm25_candidates = self._retrieve_route_bm25(
            query=query_rewrite.expanded_query,
            top_k=candidate_limit,
        )
        retrieval_trace.append(
            _stage_trace(
                stage="sparse_retrieval",
                method="bm25",
                started_at=started_at,
                input_count=len(_tokenize(query_rewrite.expanded_query)),
                output_count=len(bm25_candidates),
                details={
                    "top_k": candidate_limit,
                    "titles": [candidate.document.title for candidate in bm25_candidates],
                },
            )
        )

        started_at = time.perf_counter()
        dense_candidates = self._retrieve_route_dense(
            query=query_rewrite.expanded_query,
            top_k=candidate_limit,
        )
        dense_details: dict[str, Any] = {
            "top_k": candidate_limit,
            "enabled": self.dense_enabled,
            "titles": [candidate.document.title for candidate in dense_candidates],
        }
        if self.embedding_provider is not None:
            dense_details.update(
                {
                    "provider": self.embedding_provider.name,
                    "model": self.embedding_provider.model,
                    "dimensions": self.embedding_provider.dimensions,
                    "is_semantic": self.embedding_provider.is_semantic,
                    "batch_size": getattr(self.embedding_provider, "batch_size", 1),
                    "max_retries": getattr(self.embedding_provider, "max_retries", 0),
                    "vector_store": self.vector_store.name,
                    "vector_collection": self.vector_store.collection,
                    "vector_index": self.vector_index_stats,
                    "vector_store_stats": self.vector_store.stats(),
                    "ingestion": self.ingestion_result.to_dict() if self.ingestion_result else {},
                }
            )
        if self.dense_initialization_error:
            dense_details["fallback_reason"] = self.dense_initialization_error
        retrieval_trace.append(
            _stage_trace(
                stage="dense_retrieval",
                method=self.embedding_provider.name if self.embedding_provider else "disabled",
                started_at=started_at,
                input_count=1,
                output_count=len(dense_candidates),
                details=dense_details,
            )
        )

        started_at = time.perf_counter()
        signal_candidates = (
            self._retrieve_route_scene_signals(scene, top_k=candidate_limit)
            if scene is not None
            else []
        )
        retrieval_trace.append(
            _stage_trace(
                stage="scene_signal_retrieval",
                method="rule_signal_match" if scene is not None else "not_applicable",
                started_at=started_at,
                input_count=len(self._scene_rerank_signals(scene)) if scene is not None else 0,
                output_count=len(signal_candidates),
                details={
                    "top_k": candidate_limit,
                    "titles": [candidate.document.title for candidate in signal_candidates],
                },
            )
        )

        started_at = time.perf_counter()
        fused = self._fuse_route_candidates(
            routes=[bm25_candidates, dense_candidates, signal_candidates],
            top_k=candidate_limit,
            rrf_k=self.rrf_k,
        )
        fusion_evidence = [
            {
                "title": candidate.document.title,
                "rrf_score": round(candidate.rrf_score, 6),
                "route_scores": {
                    route: round(score, 4) for route, score in candidate.route_scores.items()
                },
                "contributions": candidate.contributions,
            }
            for candidate in fused
        ]
        retrieval_trace.append(
            _stage_trace(
                stage="fusion",
                method="rrf",
                started_at=started_at,
                input_count=len(bm25_candidates) + len(dense_candidates) + len(signal_candidates),
                output_count=len(fused),
                details={
                    "route_count": sum(
                        1 for route in [bm25_candidates, dense_candidates, signal_candidates] if route
                    ),
                    "rrf_k": self.rrf_k,
                    "titles": [candidate.document.title for candidate in fused],
                },
            )
        )

        started_at = time.perf_counter()
        reranked = self._rerank_fused_candidates(scene, fused)
        retrieval_trace.append(
            _stage_trace(
                stage="rerank",
                method="scene_signal_boost" if scene is not None else "query_score_boost",
                started_at=started_at,
                input_count=len(fused),
                output_count=len(reranked),
                details={
                    "titles": [candidate[0].document.title for candidate in reranked[:result_limit]],
                },
            )
        )

        selected = reranked[:result_limit]
        snippets = [
            KnowledgeSnippet(
                title=candidate.document.title,
                content=candidate.document.content,
                score=final_score,
                source=candidate.document.source,
            )
            for candidate, final_score, _signal_boost, _signals in selected
        ]
        return RetrievalResult(
            snippets=snippets,
            query_rewrite=query_rewrite,
            candidates_considered=len({_document_key(candidate.document) for candidate in fused}),
            rerank_evidence=[
                {
                    "title": candidate.document.title,
                    "bm25_score": round(candidate.route_scores.get("bm25", 0.0), 4),
                    "dense_score": round(candidate.route_scores.get("embedding_dense", 0.0), 4),
                    "scene_signal_score": round(candidate.route_scores.get("scene_signal", 0.0), 4),
                    "rrf_score": round(candidate.rrf_score, 6),
                    "signal_boost": round(signal_boost, 4),
                    "rerank_score": round(final_score, 4),
                    "matched_signals": signals,
                }
                for candidate, final_score, signal_boost, signals in selected
            ],
            fusion_evidence=fusion_evidence,
            retrieval_trace=retrieval_trace,
        )

    def retrieve(self, query: str, top_k: int = 3) -> List[KnowledgeSnippet]:
        return self.retrieve_query_with_trace(query=query, top_k=top_k).snippets

    def _retrieve_documents(self, query: str, top_k: int) -> List[tuple[KnowledgeDocument, float]]:
        return [
            (candidate.document, candidate.score)
            for candidate in self._retrieve_route_bm25(query=query, top_k=top_k)
        ]

    def _retrieve_route_bm25(self, query: str, top_k: int) -> List[RouteCandidate]:
        query_tokens = Counter(_tokenize(query))
        if not query_tokens or not self.documents:
            return []

        scored: List[RouteCandidate] = []
        for doc in self.documents:
            score = self._bm25_score(query_tokens, doc)
            if score > 0:
                matched_terms = [
                    token for token in query_tokens if doc.tokens.get(token, 0) > 0
                ][:8]
                scored.append(
                    RouteCandidate(
                        document=doc,
                        route="bm25",
                        score=score,
                        evidence=matched_terms,
                    )
                )

        return sorted(scored, key=lambda item: (-item.score, item.document.title))[:top_k]

    def _retrieve_route_dense(self, query: str, top_k: int) -> List[RouteCandidate]:
        if not self.dense_enabled or self.embedding_provider is None:
            return []

        results = self.vector_store.search(
            query=query,
            embedding_provider=self.embedding_provider,
            top_k=top_k,
        )
        return [
            RouteCandidate(
                document=result.document,
                route="embedding_dense",
                score=result.score,
                evidence=result.evidence,
            )
            for result in results
        ]

    def _retrieve_route_scene_signals(
        self,
        scene: BattlefieldScene,
        top_k: int,
    ) -> List[RouteCandidate]:
        signals = self._scene_rerank_signals(scene)
        if not signals or not self.documents:
            return []

        candidates: List[RouteCandidate] = []
        for doc in self.documents:
            text = f"{doc.title}\n{doc.content}".lower()
            matched = [signal for signal, _weight in signals if signal in text]
            score = sum(weight for signal, weight in signals if signal in text)
            if score > 0:
                candidates.append(
                    RouteCandidate(
                        document=doc,
                        route="scene_signal",
                        score=score,
                        evidence=matched,
                    )
                )

        return sorted(candidates, key=lambda item: (-item.score, item.document.title))[:top_k]

    @staticmethod
    def _fuse_route_candidates(
        routes: List[List[RouteCandidate]],
        top_k: int,
        rrf_k: int = 60,
    ) -> List[FusedCandidate]:
        fused_scores: dict[str, float] = {}
        documents: dict[str, KnowledgeDocument] = {}
        route_scores: dict[str, dict[str, float]] = {}
        contributions: dict[str, List[dict[str, Any]]] = {}

        for route_candidates in routes:
            for rank, candidate in enumerate(route_candidates, start=1):
                key = _document_key(candidate.document)
                rrf_contribution = 1.0 / (rrf_k + rank)
                fused_scores[key] = fused_scores.get(key, 0.0) + rrf_contribution
                documents.setdefault(key, candidate.document)
                route_scores.setdefault(key, {})[candidate.route] = candidate.score
                contributions.setdefault(key, []).append(
                    {
                        "route": candidate.route,
                        "rank": rank,
                        "raw_score": round(candidate.score, 4),
                        "rrf": round(rrf_contribution, 6),
                        "evidence": candidate.evidence,
                    }
                )

        fused = [
            FusedCandidate(
                document=documents[key],
                rrf_score=fused_score,
                route_scores=route_scores.get(key, {}),
                contributions=contributions.get(key, []),
            )
            for key, fused_score in fused_scores.items()
        ]
        return sorted(fused, key=lambda item: (-item.rrf_score, item.document.title))[:top_k]

    @staticmethod
    def build_scene_query(scene: BattlefieldScene) -> str:
        pressure_tags: List[str] = []
        if scene.enemy_strength > scene.own_strength:
            pressure_tags.append("enemy_stronger risk_control")
        if scene.civilian_presence >= 70:
            pressure_tags.append("civilian_dense collateral_damage")
        if scene.urgency >= 80:
            pressure_tags.append("high_urgency rapid_response")
        if scene.intel_quality < 60:
            pressure_tags.append("low_intel reconnaissance")
        if scene.supply_level < 60:
            pressure_tags.append("low_supply resource_efficiency")

        return " ".join(
            [
                scene.name,
                scene.objective,
                scene.terrain,
                scene.weather,
                *pressure_tags,
            ]
        )

    @classmethod
    def rewrite_scene_query(cls, scene: BattlefieldScene) -> QueryRewrite:
        original_query = cls.build_scene_query(scene)
        expansions: List[str] = []
        reasons: List[str] = []

        def add(tokens: List[str], reason: str) -> None:
            for token in tokens:
                if token not in expansions:
                    expansions.append(token)
            reasons.append(reason)

        terrain = scene.terrain.lower()
        if terrain:
            add([terrain, "terrain_control"], "terrain_context")
        if scene.civilian_presence >= 70:
            add(["civilian_dense", "collateral_damage", "evacuation", "risk_control"], "civilian_pressure")
        if scene.urgency >= 80:
            add(["high_urgency", "rapid_response", "command_control", "response_speed"], "time_pressure")
        if scene.intel_quality < 60:
            add(["low_intel", "reconnaissance", "deception", "intel_alignment"], "intel_gap")
        if scene.supply_level < 60:
            add(["low_supply", "resource_efficiency", "supply_line"], "supply_pressure")
        if scene.enemy_strength > scene.own_strength:
            add(["enemy_stronger", "defense", "delay", "risk_control"], "enemy_pressure")

        expanded_query = " ".join([original_query, *expansions]).strip()
        return QueryRewrite(
            original_query=original_query,
            expanded_query=expanded_query,
            expansions=expansions,
            reasons=reasons,
        )

    @staticmethod
    def _build_doc_frequency(documents: Iterable[KnowledgeDocument]) -> Counter[str]:
        frequency: Counter[str] = Counter()
        for doc in documents:
            frequency.update(doc.tokens.keys())
        return frequency

    def _bm25_score(self, query_tokens: Counter[str], doc: KnowledgeDocument) -> float:
        score = 0.0
        doc_len = sum(doc.tokens.values())
        k1 = 1.5
        b = 0.75

        for token, query_count in query_tokens.items():
            freq = doc.tokens.get(token, 0)
            if freq == 0:
                continue

            df = self.doc_frequency.get(token, 0)
            idf = math.log(1 + (self.doc_count - df + 0.5) / (df + 0.5))
            numerator = freq * (k1 + 1)
            denominator = freq + k1 * (1 - b + b * doc_len / max(self.avg_doc_len, 1))
            score += idf * numerator / denominator * query_count

        return score

    def _rerank_candidates(
        self,
        scene: BattlefieldScene,
        candidates: List[tuple[KnowledgeDocument, float]],
    ) -> List[tuple[KnowledgeDocument, float, float, List[str]]]:
        signals = self._scene_rerank_signals(scene)
        reranked: List[tuple[KnowledgeDocument, float, float, List[str]]] = []
        for doc, bm25_score in candidates:
            text = f"{doc.title}\n{doc.content}".lower()
            matched = [signal for signal, _weight in signals if signal in text]
            boost = sum(weight for signal, weight in signals if signal in text)
            reranked.append((doc, bm25_score, bm25_score + boost, matched))
        return sorted(reranked, key=lambda item: item[2], reverse=True)

    def _rerank_fused_candidates(
        self,
        scene: BattlefieldScene | None,
        candidates: List[FusedCandidate],
    ) -> List[tuple[FusedCandidate, float, float, List[str]]]:
        signals = self._scene_rerank_signals(scene) if scene is not None else []
        reranked: List[tuple[FusedCandidate, float, float, List[str]]] = []
        for candidate in candidates:
            text = f"{candidate.document.title}\n{candidate.document.content}".lower()
            matched = [signal for signal, _weight in signals if signal in text]
            signal_boost = sum(weight for signal, weight in signals if signal in text)
            bm25_score = candidate.route_scores.get("bm25", 0.0)
            dense_score = candidate.route_scores.get("embedding_dense", 0.0)
            final_score = (
                candidate.rrf_score
                + signal_boost
                + min(bm25_score, 20.0) * 0.01
                + max(0.0, dense_score) * 0.5
            )
            reranked.append((candidate, final_score, signal_boost, matched))
        return sorted(reranked, key=lambda item: (-item[1], item[0].document.title))

    @staticmethod
    def _scene_rerank_signals(scene: BattlefieldScene) -> List[tuple[str, float]]:
        signals: List[tuple[str, float]] = []

        def add(signal: str, weight: float) -> None:
            if not any(existing == signal for existing, _ in signals):
                signals.append((signal, weight))

        terrain = scene.terrain.lower()
        if terrain:
            add(terrain, 0.8)
        if scene.civilian_presence >= 70:
            add("civilian_dense", 1.6)
            add("collateral_damage", 1.4)
            add("risk_control", 1.0)
        if scene.urgency >= 80:
            add("high_urgency", 1.4)
            add("rapid_response", 1.2)
            add("response_speed", 0.8)
        if scene.intel_quality < 60:
            add("low_intel", 1.4)
            add("reconnaissance", 1.2)
            add("intel_alignment", 0.8)
        if scene.supply_level < 60:
            add("low_supply", 1.2)
            add("resource_efficiency", 0.8)
        if scene.enemy_strength > scene.own_strength:
            add("enemy_stronger", 1.5)
            add("defense", 1.0)
            add("delay", 0.8)
        return signals


def _document_from_chunk(chunk: DocumentChunk) -> KnowledgeDocument:
    full_text = f"{chunk.title}\n{chunk.content}"
    return KnowledgeDocument(
        title=chunk.title,
        content=chunk.content,
        source=chunk.source,
        tokens=Counter(_tokenize(full_text)),
        metadata=chunk.metadata,
    )


def _document_key(doc: KnowledgeDocument) -> str:
    return f"{doc.source}::{doc.title}"


def _create_vector_store(
    *,
    store_name: str,
    db_path: Path,
    collection: str,
    chroma_mode: str = "persistent",
    chroma_host: str = "localhost",
    chroma_port: int = 8000,
    chroma_ssl: bool = False,
) -> InMemoryVectorStore | SQLiteVectorStore | ChromaVectorStore:
    store = store_name.strip().lower()
    if store in {"", "in-memory", "memory"}:
        return InMemoryVectorStore(collection=collection)
    if store in {"sqlite", "sqlite-vector", "local-sqlite"}:
        resolved_path = db_path if db_path.is_absolute() else Path(__file__).resolve().parent.parent / db_path
        return SQLiteVectorStore(db_path=resolved_path, collection=collection)
    if store in {"chroma", "chromadb", "chroma-local"}:
        resolved_path = db_path if db_path.is_absolute() else Path(__file__).resolve().parent.parent / db_path
        return ChromaVectorStore(
            persist_directory=resolved_path,
            collection=collection,
            mode=chroma_mode,
            host=chroma_host,
            port=chroma_port,
            ssl=chroma_ssl,
        )
    raise ValueError(f"unsupported vector store: {store_name}")


def _resolve_project_path(path: Path) -> Path:
    return path if path.is_absolute() else Path(__file__).resolve().parent.parent / path


def _stage_trace(
    *,
    stage: str,
    method: str,
    started_at: float,
    input_count: int,
    output_count: int,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "method": method,
        "input_count": input_count,
        "output_count": output_count,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "details": details or {},
    }


def _tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    for match in TOKEN_RE.findall(text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", match):
            tokens.extend(_char_ngrams(match, size=2))
            tokens.append(match)
        else:
            tokens.append(match)
    return tokens


def _char_ngrams(text: str, size: int) -> List[str]:
    if len(text) <= size:
        return [text]
    return [text[index : index + size] for index in range(len(text) - size + 1)]
