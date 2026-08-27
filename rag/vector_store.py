from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .embeddings import EmbeddingProvider


@dataclass(frozen=True)
class VectorRecord:
    record_id: str
    document: Any
    vector: list[float]


@dataclass(frozen=True)
class VectorSearchResult:
    document: Any
    score: float
    evidence: list[str]


class InMemoryVectorStore:
    name = "in-memory"

    def __init__(self, collection: str = "tactical_knowledge") -> None:
        self.collection = collection
        self._records: list[VectorRecord] = []

    def upsert_documents(
        self,
        documents: list[Any],
        embedding_provider: EmbeddingProvider,
        replace_collection: bool = True,
    ) -> dict[str, int]:
        texts = [_document_text(document) for document in documents]
        vectors = embedding_provider.embed_texts(texts)
        _validate_vectors(vectors, expected_count=len(documents), expected_dimensions=embedding_provider.dimensions)
        self._records = [
            VectorRecord(
                record_id=_document_key(document),
                document=document,
                vector=vector,
            )
            for document, vector in zip(documents, vectors)
        ]
        return {"upserted": len(documents), "skipped": 0, "deleted": 0, "total": len(self._records)}

    def search(
        self,
        query: str,
        embedding_provider: EmbeddingProvider,
        top_k: int,
    ) -> list[VectorSearchResult]:
        if not query.strip() or not self._records:
            return []

        query_vector = embedding_provider.embed_query(query)
        results: list[VectorSearchResult] = []
        for record in self._records:
            score = _cosine_similarity(query_vector, record.vector)
            if score > 0:
                results.append(
                    VectorSearchResult(
                        document=record.document,
                        score=score,
                        evidence=[
                            f"embedding_provider:{embedding_provider.name}",
                            f"embedding_model:{embedding_provider.model}",
                            f"vector_store:{self.name}",
                            f"collection:{self.collection}",
                        ],
                    )
                )

        return sorted(results, key=lambda item: (-item.score, _document_key(item.document)))[:top_k]

    def stats(self) -> dict[str, Any]:
        return {
            "store": self.name,
            "collection": self.collection,
            "document_count": len(self._records),
        }


class SQLiteVectorStore:
    name = "sqlite"

    def __init__(self, db_path: Path | str, collection: str = "tactical_knowledge") -> None:
        self.db_path = Path(db_path)
        self.collection = collection
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_vector_documents (
                    collection TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    content_hash TEXT NOT NULL,
                    embedding_provider TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding_dimensions INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection, record_id)
                )
                """
            )
            _ensure_column(conn, "rag_vector_documents", "metadata_json", "TEXT NOT NULL DEFAULT '{}'")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_vector_documents_collection
                ON rag_vector_documents(collection)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_vector_documents_embedding
                ON rag_vector_documents(collection, embedding_provider, embedding_model, embedding_dimensions)
                """
            )

    def upsert_documents(
        self,
        documents: list[Any],
        embedding_provider: EmbeddingProvider,
        replace_collection: bool = True,
    ) -> dict[str, int]:
        specs = [_document_spec(document) for document in documents]
        record_ids = [spec["record_id"] for spec in specs]
        stale_deleted = 0
        upserted = 0
        skipped = 0

        with self._connect() as conn:
            existing = {
                str(row["record_id"]): row
                for row in conn.execute(
                    """
                    SELECT record_id, content_hash, metadata_json, embedding_provider, embedding_model, embedding_dimensions
                    FROM rag_vector_documents
                    WHERE collection = ?
                    """,
                    (self.collection,),
                ).fetchall()
            }

            changed_specs: list[dict[str, str]] = []
            changed_documents: list[Any] = []
            for document, spec in zip(documents, specs):
                row = existing.get(spec["record_id"])
                if row and _same_embedding_row(row, spec, embedding_provider):
                    skipped += 1
                    continue
                changed_specs.append(spec)
                changed_documents.append(document)

            if changed_documents:
                vectors = embedding_provider.embed_texts([spec["text"] for spec in changed_specs])
                _validate_vectors(
                    vectors,
                    expected_count=len(changed_documents),
                    expected_dimensions=embedding_provider.dimensions,
                )
                for spec, vector in zip(changed_specs, vectors):
                    conn.execute(
                        """
                        INSERT INTO rag_vector_documents (
                            collection,
                            record_id,
                            source,
                            title,
                            content,
                            metadata_json,
                            content_hash,
                            embedding_provider,
                            embedding_model,
                            embedding_dimensions,
                            vector_json,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(collection, record_id) DO UPDATE SET
                            source = excluded.source,
                            title = excluded.title,
                            content = excluded.content,
                            metadata_json = excluded.metadata_json,
                            content_hash = excluded.content_hash,
                            embedding_provider = excluded.embedding_provider,
                            embedding_model = excluded.embedding_model,
                            embedding_dimensions = excluded.embedding_dimensions,
                            vector_json = excluded.vector_json,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            self.collection,
                            spec["record_id"],
                            spec["source"],
                            spec["title"],
                            spec["content"],
                            spec["metadata_json"],
                            spec["content_hash"],
                            embedding_provider.name,
                            embedding_provider.model,
                            embedding_provider.dimensions,
                            json.dumps(vector),
                        ),
                    )
                    upserted += 1

            if replace_collection:
                if record_ids:
                    placeholders = ",".join("?" for _item in record_ids)
                    cursor = conn.execute(
                        f"""
                        DELETE FROM rag_vector_documents
                        WHERE collection = ?
                        AND record_id NOT IN ({placeholders})
                        """,
                        (self.collection, *record_ids),
                    )
                else:
                    cursor = conn.execute(
                        "DELETE FROM rag_vector_documents WHERE collection = ?",
                        (self.collection,),
                    )
                stale_deleted = int(cursor.rowcount if cursor.rowcount is not None else 0)

        return {
            "upserted": upserted,
            "skipped": skipped,
            "deleted": stale_deleted,
            "total": self.stats()["document_count"],
        }

    def search(
        self,
        query: str,
        embedding_provider: EmbeddingProvider,
        top_k: int,
    ) -> list[VectorSearchResult]:
        if not query.strip():
            return []

        query_vector = embedding_provider.embed_query(query)
        rows = self._load_rows(embedding_provider)
        results: list[VectorSearchResult] = []
        for row in rows:
            vector = [float(value) for value in json.loads(str(row["vector_json"]))]
            score = _cosine_similarity(query_vector, vector)
            if score > 0:
                results.append(
                    VectorSearchResult(
                        document=_StoredVectorDocument(
                            title=str(row["title"]),
                            content=str(row["content"]),
                            source=str(row["source"]),
                            metadata=json.loads(str(row["metadata_json"] or "{}")),
                        ),
                        score=score,
                        evidence=[
                            f"embedding_provider:{embedding_provider.name}",
                            f"embedding_model:{embedding_provider.model}",
                            f"vector_store:{self.name}",
                            f"collection:{self.collection}",
                            f"db_path:{self.db_path}",
                        ],
                    )
                )

        return sorted(results, key=lambda item: (-item.score, _document_key(item.document)))[:top_k]

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS document_count,
                       COUNT(DISTINCT source) AS source_count,
                       MAX(updated_at) AS last_updated_at
                FROM rag_vector_documents
                WHERE collection = ?
                """,
                (self.collection,),
            ).fetchone()
        return {
            "store": self.name,
            "collection": self.collection,
            "db_path": str(self.db_path),
            "document_count": int(row["document_count"] if row else 0),
            "source_count": int(row["source_count"] if row else 0),
            "last_updated_at": str(row["last_updated_at"] or "") if row else "",
        }

    def _load_rows(self, embedding_provider: EmbeddingProvider) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT source, title, content, metadata_json, vector_json
                FROM rag_vector_documents
                WHERE collection = ?
                  AND embedding_provider = ?
                  AND embedding_model = ?
                  AND embedding_dimensions = ?
                """,
                (
                    self.collection,
                    embedding_provider.name,
                    embedding_provider.model,
                    embedding_provider.dimensions,
                ),
            ).fetchall()


class ChromaVectorStore:
    name = "chroma"

    def __init__(
        self,
        persist_directory: Path | str,
        collection: str = "tactical_knowledge",
        *,
        mode: str = "persistent",
        host: str = "localhost",
        port: int = 8000,
        ssl: bool = False,
    ) -> None:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"persistent", "http"}:
            raise ValueError(f"unsupported Chroma mode: {mode}")

        self.mode = normalized_mode
        self.persist_directory = Path(persist_directory)
        self.collection = collection
        self.host = host.strip() or "localhost"
        self.port = port
        self.ssl = ssl
        self.endpoint = f"{'https' if ssl else 'http'}://{self.host}:{self.port}"

        if self.mode == "persistent":
            self.persist_directory.mkdir(parents=True, exist_ok=True)

        target = str(self.persist_directory) if self.mode == "persistent" else self.endpoint
        try:
            self._client = _create_chroma_client(
                persist_directory=self.persist_directory,
                mode=self.mode,
                host=self.host,
                port=self.port,
                ssl=self.ssl,
            )
            self._client.heartbeat()
            self._collection = self._client.get_or_create_collection(
                name=collection,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise RuntimeError(
                f"Chroma {self.mode} initialization failed for {target}: {exc}"
            ) from exc

    def upsert_documents(
        self,
        documents: list[Any],
        embedding_provider: EmbeddingProvider,
        replace_collection: bool = True,
    ) -> dict[str, int]:
        specs = [_document_spec(document) for document in documents]
        record_ids = [spec["record_id"] for spec in specs]
        stale_deleted = 0
        upserted = 0
        skipped = 0

        existing = self._collection.get(include=["metadatas"])
        existing_metadata = {
            str(record_id): metadata or {}
            for record_id, metadata in zip(existing.get("ids", []), existing.get("metadatas", []))
        }

        changed_specs: list[dict[str, str]] = []
        for spec in specs:
            metadata = existing_metadata.get(spec["record_id"])
            if metadata and _same_chroma_metadata(metadata, spec, embedding_provider):
                skipped += 1
                continue
            changed_specs.append(spec)

        if changed_specs:
            vectors = embedding_provider.embed_texts([spec["text"] for spec in changed_specs])
            _validate_vectors(
                vectors,
                expected_count=len(changed_specs),
                expected_dimensions=embedding_provider.dimensions,
            )
            self._collection.upsert(
                ids=[spec["record_id"] for spec in changed_specs],
                embeddings=vectors,
                documents=[spec["content"] for spec in changed_specs],
                metadatas=[
                    _chroma_metadata(spec, embedding_provider)
                    for spec in changed_specs
                ],
            )
            upserted = len(changed_specs)

        if replace_collection:
            stale_ids = [
                record_id
                for record_id in existing_metadata
                if record_id not in set(record_ids)
            ]
            if stale_ids:
                self._collection.delete(ids=stale_ids)
                stale_deleted = len(stale_ids)

        return {
            "upserted": upserted,
            "skipped": skipped,
            "deleted": stale_deleted,
            "total": self.stats()["document_count"],
        }

    def search(
        self,
        query: str,
        embedding_provider: EmbeddingProvider,
        top_k: int,
    ) -> list[VectorSearchResult]:
        if not query.strip() or self._collection.count() == 0:
            return []

        query_vector = embedding_provider.embed_query(query)
        result = self._collection.query(
            query_embeddings=[query_vector],
            n_results=max(1, top_k),
            where={
                "$and": [
                    {"embedding_provider": {"$eq": embedding_provider.name}},
                    {"embedding_model": {"$eq": embedding_provider.model}},
                    {"embedding_dimensions": {"$eq": embedding_provider.dimensions}},
                ]
            },
            include=["documents", "metadatas", "distances"],
        )

        ids = result.get("ids", [[]])[0] if result.get("ids") else []
        documents = result.get("documents", [[]])[0] if result.get("documents") else []
        metadatas = result.get("metadatas", [[]])[0] if result.get("metadatas") else []
        distances = result.get("distances", [[]])[0] if result.get("distances") else []

        results: list[VectorSearchResult] = []
        for record_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
            meta = metadata or {}
            score = _chroma_distance_to_score(float(distance))
            if score <= 0:
                continue
            results.append(
                VectorSearchResult(
                    document=_StoredVectorDocument(
                        title=str(meta.get("title", "")),
                        content=str(content or ""),
                        source=str(meta.get("source", "")),
                        metadata=_metadata_from_json(str(meta.get("metadata_json", "{}"))),
                    ),
                    score=score,
                    evidence=[
                        f"embedding_provider:{embedding_provider.name}",
                        f"embedding_model:{embedding_provider.model}",
                        f"vector_store:{self.name}",
                        f"collection:{self.collection}",
                        f"chroma_mode:{self.mode}",
                        (
                            f"persist_directory:{self.persist_directory}"
                            if self.mode == "persistent"
                            else f"endpoint:{self.endpoint}"
                        ),
                        f"record_id:{record_id}",
                    ],
                )
            )

        return sorted(results, key=lambda item: (-item.score, _document_key(item.document)))[:top_k]

    def stats(self) -> dict[str, Any]:
        result = {
            "store": self.name,
            "collection": self.collection,
            "mode": self.mode,
            "document_count": int(self._collection.count()),
        }
        if self.mode == "persistent":
            result["persist_directory"] = str(self.persist_directory)
        else:
            result["endpoint"] = self.endpoint
        return result


@dataclass(frozen=True)
class _StoredVectorDocument:
    title: str
    content: str
    source: str
    metadata: dict[str, Any] = None


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _validate_vectors(vectors: list[list[float]], expected_count: int, expected_dimensions: int) -> None:
    if len(vectors) != expected_count:
        raise ValueError(f"vector count mismatch: expected {expected_count}, got {len(vectors)}")
    for vector in vectors:
        if not vector:
            raise ValueError("vector store cannot upsert empty embedding vector")
        if len(vector) != expected_dimensions:
            raise ValueError(
                "vector dimension mismatch: "
                f"expected {expected_dimensions}, got {len(vector)}"
            )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _document_text(document: Any) -> str:
    title = str(getattr(document, "title", "")).strip()
    content = str(getattr(document, "content", "")).strip()
    return f"{title}\n{content}".strip()


def _document_key(document: Any) -> str:
    source = str(getattr(document, "source", "")).strip()
    title = str(getattr(document, "title", "")).strip()
    return f"{source}::{title}"


def _document_spec(document: Any) -> dict[str, str]:
    source = str(getattr(document, "source", "")).strip()
    title = str(getattr(document, "title", "")).strip()
    content = str(getattr(document, "content", "")).strip()
    metadata = getattr(document, "metadata", {}) or {}
    text = f"{title}\n{content}".strip()
    return {
        "record_id": _document_key(document),
        "source": source,
        "title": title,
        "content": content,
        "metadata_json": json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        "text": text,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def _same_embedding_row(row: sqlite3.Row, spec: dict[str, str], embedding_provider: EmbeddingProvider) -> bool:
    return (
        str(row["content_hash"]) == spec["content_hash"]
        and str(row["metadata_json"]) == spec["metadata_json"]
        and str(row["embedding_provider"]) == embedding_provider.name
        and str(row["embedding_model"]) == embedding_provider.model
        and int(row["embedding_dimensions"]) == embedding_provider.dimensions
    )


def _create_chroma_client(
    *,
    persist_directory: Path,
    mode: str,
    host: str,
    port: int,
    ssl: bool,
):
    try:
        import chromadb
    except ImportError as exc:  # pragma: no cover - depends on optional deployment dependency
        raise RuntimeError("chromadb is required when MESSAGE_TALK_VECTOR_STORE=chroma") from exc
    if mode == "http":
        return chromadb.HttpClient(host=host, port=port, ssl=ssl)
    return chromadb.PersistentClient(path=str(persist_directory))


def _chroma_metadata(spec: dict[str, str], embedding_provider: EmbeddingProvider) -> dict[str, str | int]:
    return {
        "source": spec["source"],
        "title": spec["title"],
        "content_hash": spec["content_hash"],
        "metadata_json": spec["metadata_json"],
        "embedding_provider": embedding_provider.name,
        "embedding_model": embedding_provider.model,
        "embedding_dimensions": embedding_provider.dimensions,
    }


def _same_chroma_metadata(
    metadata: dict[str, Any],
    spec: dict[str, str],
    embedding_provider: EmbeddingProvider,
) -> bool:
    return (
        str(metadata.get("content_hash", "")) == spec["content_hash"]
        and str(metadata.get("metadata_json", "{}")) == spec["metadata_json"]
        and str(metadata.get("embedding_provider", "")) == embedding_provider.name
        and str(metadata.get("embedding_model", "")) == embedding_provider.model
        and int(metadata.get("embedding_dimensions", 0)) == embedding_provider.dimensions
    )


def _metadata_from_json(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _chroma_distance_to_score(distance: float) -> float:
    return max(0.0, 1.0 - distance)
