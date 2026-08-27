from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.embeddings import EmbeddingConfig, create_embedding_provider
from rag.retriever import KnowledgeRetriever
from rag.vector_store import ChromaVectorStore, InMemoryVectorStore, SQLiteVectorStore
from settings import get_settings


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()

    documents_dir = Path(args.documents_dir) if args.documents_dir else PROJECT_ROOT / "rag" / "documents"
    if not documents_dir.is_absolute():
        documents_dir = PROJECT_ROOT / documents_dir
    if not documents_dir.exists():
        raise SystemExit(f"documents directory not found: {documents_dir}")

    provider = create_embedding_provider(
        EmbeddingConfig(
            provider=args.embedding_provider or settings.embedding_provider,
            model=args.embedding_model or settings.embedding_model,
            api_key=args.embedding_api_key if args.embedding_api_key is not None else settings.embedding_api_key,
            base_url=args.embedding_base_url or settings.embedding_base_url,
            dimensions=args.embedding_dimensions or settings.embedding_dimensions,
            timeout_sec=args.embedding_timeout or settings.embedding_timeout_sec,
            batch_size=args.embedding_batch_size or settings.embedding_batch_size,
            max_retries=args.embedding_max_retries
            if args.embedding_max_retries is not None
            else settings.embedding_max_retries,
        )
    )

    strict = args.strict or settings.rag_strict_embedding
    health = None if args.skip_health_check else provider.health_check()
    if health is not None and not health.ok and strict:
        raise SystemExit(f"embedding health check failed: {health.error}")

    vector_store = _create_vector_store(
        store_name=args.vector_store or settings.vector_store,
        db_path=Path(args.vector_db_path or settings.vector_db_path),
        collection=args.collection or settings.vector_collection,
        chroma_mode=args.chroma_mode or settings.chroma_mode,
        chroma_host=args.chroma_host or settings.chroma_host,
        chroma_port=args.chroma_port or settings.chroma_port,
        chroma_ssl=args.chroma_ssl if args.chroma_ssl is not None else settings.chroma_ssl,
    )
    ingestion_history_path = Path(args.ingestion_history_db_path or settings.ingestion_history_db_path)
    if not ingestion_history_path.is_absolute():
        ingestion_history_path = PROJECT_ROOT / ingestion_history_path

    retriever = KnowledgeRetriever.from_directory(
        documents_dir,
        embedding_provider=provider,
        vector_store=vector_store,
        dense_enabled=True,
        rrf_k=args.rrf_k or settings.rag_rrf_k,
        strict_dense=strict,
        ingestion_history_db_path=ingestion_history_path,
        collection=args.collection or settings.vector_collection,
        chunk_size=args.chunk_size or settings.rag_chunk_size,
        chunk_overlap=args.chunk_overlap if args.chunk_overlap is not None else settings.rag_chunk_overlap,
    )

    payload: dict[str, Any] = {
        "documents_dir": str(documents_dir),
        "documents_loaded": len(retriever.documents),
        "embedding": {
            "provider": provider.name,
            "model": provider.model,
            "dimensions": provider.dimensions,
            "is_semantic": provider.is_semantic,
        },
        "vector_index": retriever.vector_index_stats,
        "vector_store": retriever.vector_store.stats(),
        "ingestion": retriever.ingestion_result.to_dict() if retriever.ingestion_result else None,
        "health": health.to_dict() if health else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or refresh the local RAG vector index.")
    parser.add_argument("--documents-dir", help="Markdown knowledge directory. Defaults to rag/documents.")
    parser.add_argument("--embedding-provider", help="Embedding provider, e.g. local-hashing or openai-compatible.")
    parser.add_argument("--embedding-model", help="Embedding model name.")
    parser.add_argument("--embedding-api-key", help="Embedding API key. Defaults to settings/env.")
    parser.add_argument("--embedding-base-url", help="OpenAI-compatible base URL.")
    parser.add_argument("--embedding-dimensions", type=int, help="Expected embedding vector dimensions.")
    parser.add_argument("--embedding-timeout", type=int, help="Embedding request timeout in seconds.")
    parser.add_argument("--embedding-batch-size", type=int, help="Embedding batch size.")
    parser.add_argument("--embedding-max-retries", type=int, help="Embedding max retries.")
    parser.add_argument("--vector-store", choices=["sqlite", "in-memory", "chroma"], help="Vector store backend.")
    parser.add_argument("--vector-db-path", help="SQLite database path or Chroma persist directory.")
    parser.add_argument("--collection", help="Vector collection name.")
    parser.add_argument("--chroma-mode", choices=["persistent", "http"], help="Chroma client mode.")
    parser.add_argument("--chroma-host", help="Chroma HTTP server host.")
    parser.add_argument("--chroma-port", type=int, help="Chroma HTTP server port.")
    parser.add_argument(
        "--chroma-ssl",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use HTTPS for the Chroma HTTP connection.",
    )
    parser.add_argument("--ingestion-history-db-path", help="SQLite ingestion history database path.")
    parser.add_argument("--chunk-size", type=int, help="Markdown chunk size in characters.")
    parser.add_argument("--chunk-overlap", type=int, help="Markdown chunk overlap in characters.")
    parser.add_argument("--rrf-k", type=int, help="RRF smoothing constant.")
    parser.add_argument("--strict", action="store_true", help="Fail fast if dense indexing fails.")
    parser.add_argument("--skip-health-check", action="store_true", help="Skip embedding provider health check.")
    return parser.parse_args(argv)


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
    normalized = store_name.strip().lower()
    if normalized in {"", "in-memory", "memory"}:
        return InMemoryVectorStore(collection=collection)
    if normalized in {"sqlite", "sqlite-vector", "local-sqlite"}:
        resolved_path = db_path if db_path.is_absolute() else PROJECT_ROOT / db_path
        return SQLiteVectorStore(db_path=resolved_path, collection=collection)
    if normalized in {"chroma", "chromadb", "chroma-local"}:
        resolved_path = db_path if db_path.is_absolute() else PROJECT_ROOT / db_path
        return ChromaVectorStore(
            persist_directory=resolved_path,
            collection=collection,
            mode=chroma_mode,
            host=chroma_host,
            port=chroma_port,
            ssl=chroma_ssl,
        )
    raise ValueError(f"unsupported vector store: {store_name}")


if __name__ == "__main__":
    raise SystemExit(main())
