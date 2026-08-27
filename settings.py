from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-plus"
DEFAULT_SERVICE_NAME = "message_talk"
DEFAULT_VERSION = "0.2.0"
DEFAULT_EMBEDDING_PROVIDER = "local-hashing"
DEFAULT_EMBEDDING_MODEL = "local-hashing-v1"
DEFAULT_EMBEDDING_DIMENSIONS = 128
DEFAULT_EMBEDDING_TIMEOUT = 30
DEFAULT_EMBEDDING_BATCH_SIZE = 8
DEFAULT_EMBEDDING_MAX_RETRIES = 2
DEFAULT_VECTOR_STORE = "sqlite"
DEFAULT_VECTOR_DB_PATH = "data/rag_vectors.db"
DEFAULT_VECTOR_COLLECTION = "tactical_knowledge"
DEFAULT_CHROMA_MODE = "persistent"
DEFAULT_CHROMA_HOST = "localhost"
DEFAULT_CHROMA_PORT = 8000
DEFAULT_CHROMA_SSL = False
DEFAULT_INGESTION_HISTORY_DB_PATH = "data/rag_ingestion.db"
DEFAULT_RAG_CHUNK_SIZE = 900
DEFAULT_RAG_CHUNK_OVERLAP = 120
DEFAULT_AGENT_MAX_WORKERS = 5


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def _read_timeout() -> int:
    raw = _first_env("MESSAGE_TALK_TIMEOUT", "LLM_TIMEOUT", default="60")
    try:
        return max(5, int(raw))
    except ValueError:
        return 60


def _read_positive_int(name: str, default: int, minimum: int = 1) -> int:
    raw = _first_env(name, default=str(default))
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def _read_bool(name: str, default: bool) -> bool:
    raw = _first_env(name, default="true" if default else "false").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class AppSettings:
    service_name: str
    version: str
    api_key: str
    base_url: str
    model: str
    timeout_sec: int
    log_level: str
    database_path: str
    embedding_provider: str
    embedding_model: str
    embedding_api_key: str
    embedding_base_url: str
    embedding_dimensions: int
    embedding_timeout_sec: int
    embedding_batch_size: int
    embedding_max_retries: int
    vector_store: str
    vector_db_path: str
    vector_collection: str
    chroma_mode: str
    chroma_host: str
    chroma_port: int
    chroma_ssl: bool
    ingestion_history_db_path: str
    rag_chunk_size: int
    rag_chunk_overlap: int
    rag_dense_enabled: bool
    rag_strict_embedding: bool
    rag_rrf_k: int
    agent_max_workers: int

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


def get_settings(model_override: str | None = None) -> AppSettings:
    api_key = _first_env(
        "MESSAGE_TALK_API_KEY",
        "SAFETY_AGENT_API_KEY",
        "DASHSCOPE_API_KEY",
        "API_KEY",
        "OPENAI_API_KEY",
    )
    base_url = _first_env(
        "MESSAGE_TALK_BASE_URL",
        "SAFETY_AGENT_BASE_URL",
        "DASHSCOPE_BASE_URL",
        "OPENAI_BASE_URL",
        default=DEFAULT_BASE_URL,
    )
    embedding_api_key = _first_env(
        "MESSAGE_TALK_EMBEDDING_API_KEY",
        "EMBEDDING_API_KEY",
        default=api_key,
    )
    embedding_base_url = _first_env(
        "MESSAGE_TALK_EMBEDDING_BASE_URL",
        "EMBEDDING_BASE_URL",
        default=base_url,
    )
    return AppSettings(
        service_name=_first_env("MESSAGE_TALK_SERVICE_NAME", default=DEFAULT_SERVICE_NAME),
        version=_first_env("MESSAGE_TALK_VERSION", default=DEFAULT_VERSION),
        api_key=api_key,
        base_url=base_url,
        model=(
            model_override
            or _first_env(
                "MESSAGE_TALK_MODEL",
                "SAFETY_AGENT_MODEL",
                "DASHSCOPE_MODEL",
                "OPENAI_MODEL",
                default=DEFAULT_MODEL,
            )
        ).strip(),
        timeout_sec=_read_timeout(),
        log_level=_first_env("MESSAGE_TALK_LOG_LEVEL", "LOG_LEVEL", default="INFO").upper(),
        database_path=_first_env("MESSAGE_TALK_DB_PATH", default="data/decision_records.db"),
        embedding_provider=_first_env(
            "MESSAGE_TALK_EMBEDDING_PROVIDER",
            default=DEFAULT_EMBEDDING_PROVIDER,
        ),
        embedding_model=_first_env(
            "MESSAGE_TALK_EMBEDDING_MODEL",
            "EMBEDDING_MODEL",
            default=DEFAULT_EMBEDDING_MODEL,
        ),
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        embedding_dimensions=_read_positive_int(
            "MESSAGE_TALK_EMBEDDING_DIMENSIONS",
            DEFAULT_EMBEDDING_DIMENSIONS,
            minimum=16,
        ),
        embedding_timeout_sec=_read_positive_int(
            "MESSAGE_TALK_EMBEDDING_TIMEOUT",
            DEFAULT_EMBEDDING_TIMEOUT,
            minimum=1,
        ),
        embedding_batch_size=_read_positive_int(
            "MESSAGE_TALK_EMBEDDING_BATCH_SIZE",
            DEFAULT_EMBEDDING_BATCH_SIZE,
            minimum=1,
        ),
        embedding_max_retries=_read_positive_int(
            "MESSAGE_TALK_EMBEDDING_MAX_RETRIES",
            DEFAULT_EMBEDDING_MAX_RETRIES,
            minimum=0,
        ),
        vector_store=_first_env("MESSAGE_TALK_VECTOR_STORE", default=DEFAULT_VECTOR_STORE),
        vector_db_path=_first_env("MESSAGE_TALK_VECTOR_DB_PATH", default=DEFAULT_VECTOR_DB_PATH),
        vector_collection=_first_env("MESSAGE_TALK_VECTOR_COLLECTION", default=DEFAULT_VECTOR_COLLECTION),
        chroma_mode=_first_env("MESSAGE_TALK_CHROMA_MODE", default=DEFAULT_CHROMA_MODE),
        chroma_host=_first_env("MESSAGE_TALK_CHROMA_HOST", default=DEFAULT_CHROMA_HOST),
        chroma_port=_read_positive_int(
            "MESSAGE_TALK_CHROMA_PORT",
            DEFAULT_CHROMA_PORT,
            minimum=1,
        ),
        chroma_ssl=_read_bool("MESSAGE_TALK_CHROMA_SSL", default=DEFAULT_CHROMA_SSL),
        ingestion_history_db_path=_first_env(
            "MESSAGE_TALK_INGESTION_HISTORY_DB_PATH",
            default=DEFAULT_INGESTION_HISTORY_DB_PATH,
        ),
        rag_chunk_size=_read_positive_int(
            "MESSAGE_TALK_RAG_CHUNK_SIZE",
            DEFAULT_RAG_CHUNK_SIZE,
            minimum=200,
        ),
        rag_chunk_overlap=_read_positive_int(
            "MESSAGE_TALK_RAG_CHUNK_OVERLAP",
            DEFAULT_RAG_CHUNK_OVERLAP,
            minimum=0,
        ),
        rag_dense_enabled=_read_bool("MESSAGE_TALK_RAG_DENSE_ENABLED", default=True),
        rag_strict_embedding=_read_bool("MESSAGE_TALK_RAG_STRICT_EMBEDDING", default=False),
        rag_rrf_k=_read_positive_int("MESSAGE_TALK_RAG_RRF_K", 60, minimum=1),
        agent_max_workers=min(
            5,
            _read_positive_int(
                "MESSAGE_TALK_AGENT_MAX_WORKERS",
                DEFAULT_AGENT_MAX_WORKERS,
                minimum=1,
            ),
        ),
    )
