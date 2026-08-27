from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
TAGS_RE = re.compile(r"(?im)^tags:\s*(.+)$")


@dataclass(frozen=True)
class DocumentChunk:
    title: str
    content: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    relative_path: str
    text: str
    file_hash: str
    file_size: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class IngestionFileResult:
    path: str
    file_hash: str
    status: str
    chunk_count: int
    unchanged: bool
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "file_hash": self.file_hash,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "unchanged": self.unchanged,
            "error": self.error,
        }


@dataclass(frozen=True)
class IngestionResult:
    chunks: list[DocumentChunk]
    files: list[IngestionFileResult]
    collection: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection": self.collection,
            "files_total": len(self.files),
            "files_processed": sum(1 for item in self.files if item.status == "success" and not item.unchanged),
            "files_unchanged": sum(1 for item in self.files if item.unchanged),
            "files_failed": sum(1 for item in self.files if item.status == "failed"),
            "chunks_total": len(self.chunks),
            "files": [item.to_dict() for item in self.files],
        }


class IngestionHistoryStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
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
                CREATE TABLE IF NOT EXISTS rag_ingestion_history (
                    collection TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection, file_path)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_ingestion_history_collection
                ON rag_ingestion_history(collection)
                """
            )

    def is_unchanged(self, *, collection: str, file_path: str, file_hash: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT file_hash, status
                FROM rag_ingestion_history
                WHERE collection = ? AND file_path = ?
                """,
                (collection, file_path),
            ).fetchone()
        return bool(row and str(row["file_hash"]) == file_hash and str(row["status"]) == "success")

    def save_file_result(
        self,
        *,
        collection: str,
        file_path: str,
        file_hash: str,
        file_size: int,
        status: str,
        chunk_count: int,
        metadata: dict[str, Any],
        error: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rag_ingestion_history (
                    collection,
                    file_path,
                    file_hash,
                    file_size,
                    status,
                    chunk_count,
                    metadata_json,
                    error,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(collection, file_path) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    file_size = excluded.file_size,
                    status = excluded.status,
                    chunk_count = excluded.chunk_count,
                    metadata_json = excluded.metadata_json,
                    error = excluded.error,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    collection,
                    file_path,
                    file_hash,
                    file_size,
                    status,
                    chunk_count,
                    json.dumps(metadata, ensure_ascii=False),
                    error,
                ),
            )

    def stats(self, collection: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS file_count,
                       SUM(chunk_count) AS chunk_count,
                       MAX(updated_at) AS last_updated_at
                FROM rag_ingestion_history
                WHERE collection = ? AND status = 'success'
                """,
                (collection,),
            ).fetchone()
        return {
            "db_path": str(self.db_path),
            "collection": collection,
            "file_count": int(row["file_count"] if row else 0),
            "chunk_count": int(row["chunk_count"] or 0) if row else 0,
            "last_updated_at": str(row["last_updated_at"] or "") if row else "",
        }


class MarkdownIngestionPipeline:
    def __init__(
        self,
        documents_dir: Path | str,
        *,
        history_db_path: Path | str,
        collection: str,
        chunk_size: int = 900,
        chunk_overlap: int = 120,
    ) -> None:
        self.documents_dir = Path(documents_dir)
        self.collection = collection
        self.chunk_size = max(200, chunk_size)
        self.chunk_overlap = min(max(0, chunk_overlap), self.chunk_size // 2)
        self.history = IngestionHistoryStore(history_db_path)

    def run(self) -> IngestionResult:
        chunks: list[DocumentChunk] = []
        files: list[IngestionFileResult] = []

        for path in sorted(self.documents_dir.rglob("*.md")):
            relative_path = path.relative_to(self.documents_dir).as_posix()
            try:
                source = self._load_source(path, relative_path)
                unchanged = self.history.is_unchanged(
                    collection=self.collection,
                    file_path=relative_path,
                    file_hash=source.file_hash,
                )
                file_chunks = self._chunk_source(source)
                chunks.extend(file_chunks)
                self.history.save_file_result(
                    collection=self.collection,
                    file_path=relative_path,
                    file_hash=source.file_hash,
                    file_size=source.file_size,
                    status="success",
                    chunk_count=len(file_chunks),
                    metadata=source.metadata,
                )
                files.append(
                    IngestionFileResult(
                        path=relative_path,
                        file_hash=source.file_hash,
                        status="success",
                        chunk_count=len(file_chunks),
                        unchanged=unchanged,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - ingestion records per-file failures
                file_hash = _hash_file(path) if path.exists() else ""
                file_size = path.stat().st_size if path.exists() else 0
                self.history.save_file_result(
                    collection=self.collection,
                    file_path=relative_path,
                    file_hash=file_hash,
                    file_size=file_size,
                    status="failed",
                    chunk_count=0,
                    metadata={"relative_path": relative_path},
                    error=str(exc),
                )
                files.append(
                    IngestionFileResult(
                        path=relative_path,
                        file_hash=file_hash,
                        status="failed",
                        chunk_count=0,
                        unchanged=False,
                        error=str(exc),
                    )
                )

        return IngestionResult(chunks=chunks, files=files, collection=self.collection)

    def stats(self) -> dict[str, Any]:
        return self.history.stats(self.collection)

    def _load_source(self, path: Path, relative_path: str) -> SourceDocument:
        raw = path.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        metadata = {
            "source_path": relative_path,
            "source_name": path.name,
            "document_title": _document_title(raw, fallback=path.stem),
            "headings": _headings(raw),
            "tags": _tags(raw),
            "file_hash": file_hash,
            "file_size": path.stat().st_size,
        }
        return SourceDocument(
            path=path,
            relative_path=relative_path,
            text=raw,
            file_hash=file_hash,
            file_size=path.stat().st_size,
            metadata=metadata,
        )

    def _chunk_source(self, source: SourceDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        sections = _markdown_sections(source.text, default_title=str(source.metadata["document_title"]))

        for section_index, section in enumerate(sections):
            section_title = section["title"]
            section_text = section["content"].strip()
            if not section_text:
                continue
            parts = _split_text(section_text, chunk_size=self.chunk_size, overlap=self.chunk_overlap)
            for chunk_index, part in enumerate(parts):
                metadata = {
                    **source.metadata,
                    "collection": self.collection,
                    "section_title": section_title,
                    "section_index": section_index,
                    "chunk_index": chunk_index,
                    "chunk_count_in_section": len(parts),
                    "chunk_size": len(part),
                }
                chunks.append(
                    DocumentChunk(
                        title=section_title,
                        content=part,
                        source=source.relative_path,
                        metadata=metadata,
                    )
                )

        return chunks


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _document_title(raw: str, fallback: str) -> str:
    for level, title in HEADING_RE.findall(raw):
        if level == "#":
            return title.strip()
    return fallback


def _headings(raw: str) -> list[dict[str, Any]]:
    return [{"level": len(level), "title": title.strip()} for level, title in HEADING_RE.findall(raw)]


def _tags(raw: str) -> list[str]:
    tags: list[str] = []
    for match in TAGS_RE.findall(raw):
        for token in re.split(r"[\s,，]+", match.strip()):
            token = token.strip()
            if token and token not in tags:
                tags.append(token)
    return tags


def _markdown_sections(raw: str, default_title: str) -> list[dict[str, str]]:
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", raw))
    if not matches:
        body = re.sub(r"(?m)^#\s+.+?$", "", raw).strip()
        return [{"title": default_title, "content": body}]

    sections: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        title = match.group(1).strip()
        content = raw[start:end].strip()
        sections.append({"title": title, "content": content})
    return sections


def _split_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    normalized = "\n\n".join(part.strip() for part in text.split("\n\n") if part.strip())
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        if end < len(normalized):
            boundary = normalized.rfind("\n\n", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        next_start = max(0, end - overlap)
        start = next_start if next_start > start else end
    return chunks
