from __future__ import annotations

from settings import DEFAULT_BASE_URL, DEFAULT_MODEL, get_settings


def test_default_llm_model_uses_qwen37_plus() -> None:
    assert DEFAULT_MODEL == "qwen3.7-plus"


def test_test_suite_uses_local_rag_profile() -> None:
    settings = get_settings()

    assert settings.embedding_provider == "local-hashing"
    assert settings.embedding_model == "local-hashing-v1"
    assert settings.vector_store == "sqlite"
    assert settings.rag_strict_embedding is False


def test_settings_use_defaults_without_env(monkeypatch) -> None:
    for key in [
        "MESSAGE_TALK_API_KEY",
        "SAFETY_AGENT_API_KEY",
        "DASHSCOPE_API_KEY",
        "API_KEY",
        "OPENAI_API_KEY",
        "MESSAGE_TALK_BASE_URL",
        "MESSAGE_TALK_MODEL",
        "MESSAGE_TALK_TIMEOUT",
        "MESSAGE_TALK_EMBEDDING_PROVIDER",
        "MESSAGE_TALK_EMBEDDING_MODEL",
        "MESSAGE_TALK_EMBEDDING_API_KEY",
        "MESSAGE_TALK_EMBEDDING_BASE_URL",
        "MESSAGE_TALK_EMBEDDING_DIMENSIONS",
        "MESSAGE_TALK_EMBEDDING_TIMEOUT",
        "MESSAGE_TALK_EMBEDDING_BATCH_SIZE",
        "MESSAGE_TALK_EMBEDDING_MAX_RETRIES",
        "MESSAGE_TALK_VECTOR_STORE",
        "MESSAGE_TALK_VECTOR_DB_PATH",
        "MESSAGE_TALK_VECTOR_COLLECTION",
        "MESSAGE_TALK_CHROMA_MODE",
        "MESSAGE_TALK_CHROMA_HOST",
        "MESSAGE_TALK_CHROMA_PORT",
        "MESSAGE_TALK_CHROMA_SSL",
        "MESSAGE_TALK_INGESTION_HISTORY_DB_PATH",
        "MESSAGE_TALK_RAG_CHUNK_SIZE",
        "MESSAGE_TALK_RAG_CHUNK_OVERLAP",
        "MESSAGE_TALK_RAG_DENSE_ENABLED",
        "MESSAGE_TALK_RAG_STRICT_EMBEDDING",
        "MESSAGE_TALK_RAG_RRF_K",
        "MESSAGE_TALK_AGENT_MAX_WORKERS",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = get_settings()

    assert settings.api_key == ""
    assert settings.has_api_key is False
    assert settings.base_url == DEFAULT_BASE_URL
    assert settings.model == DEFAULT_MODEL
    assert settings.timeout_sec == 60
    assert settings.embedding_provider == "local-hashing"
    assert settings.embedding_model == "local-hashing-v1"
    assert settings.embedding_dimensions == 128
    assert settings.embedding_timeout_sec == 30
    assert settings.embedding_batch_size == 8
    assert settings.embedding_max_retries == 2
    assert settings.vector_store == "sqlite"
    assert settings.vector_db_path == "data/rag_vectors.db"
    assert settings.vector_collection == "tactical_knowledge"
    assert settings.chroma_mode == "persistent"
    assert settings.chroma_host == "localhost"
    assert settings.chroma_port == 8000
    assert settings.chroma_ssl is False
    assert settings.ingestion_history_db_path == "data/rag_ingestion.db"
    assert settings.rag_chunk_size == 900
    assert settings.rag_chunk_overlap == 120
    assert settings.rag_dense_enabled is True
    assert settings.rag_strict_embedding is False
    assert settings.rag_rrf_k == 60
    assert settings.agent_max_workers == 5


def test_agent_max_workers_is_bounded(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGE_TALK_AGENT_MAX_WORKERS", "99")
    assert get_settings().agent_max_workers == 5

    monkeypatch.setenv("MESSAGE_TALK_AGENT_MAX_WORKERS", "0")
    assert get_settings().agent_max_workers == 1


def test_settings_support_embedding_runtime_options(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGE_TALK_EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("MESSAGE_TALK_EMBEDDING_MODEL", "qwen3.7-text-embedding")
    monkeypatch.setenv("MESSAGE_TALK_EMBEDDING_TIMEOUT", "12")
    monkeypatch.setenv("MESSAGE_TALK_EMBEDDING_BATCH_SIZE", "8")
    monkeypatch.setenv("MESSAGE_TALK_EMBEDDING_MAX_RETRIES", "4")
    monkeypatch.setenv("MESSAGE_TALK_RAG_STRICT_EMBEDDING", "true")

    settings = get_settings()

    assert settings.embedding_provider == "openai-compatible"
    assert settings.embedding_model == "qwen3.7-text-embedding"
    assert settings.embedding_timeout_sec == 12
    assert settings.embedding_batch_size == 8
    assert settings.embedding_max_retries == 4
    assert settings.rag_strict_embedding is True


def test_settings_support_chroma_http_options(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGE_TALK_CHROMA_MODE", "http")
    monkeypatch.setenv("MESSAGE_TALK_CHROMA_HOST", "localhost")
    monkeypatch.setenv("MESSAGE_TALK_CHROMA_PORT", "8001")
    monkeypatch.setenv("MESSAGE_TALK_CHROMA_SSL", "true")

    settings = get_settings()

    assert settings.chroma_mode == "http"
    assert settings.chroma_host == "localhost"
    assert settings.chroma_port == 8001
    assert settings.chroma_ssl is True


def test_embedding_api_key_falls_back_to_dashscope_api_key(monkeypatch) -> None:
    monkeypatch.delenv("MESSAGE_TALK_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("MESSAGE_TALK_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    settings = get_settings()

    assert settings.api_key == "dashscope-key"
    assert settings.embedding_api_key == "dashscope-key"


def test_settings_support_model_override(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGE_TALK_API_KEY", "test-key")
    monkeypatch.setenv("MESSAGE_TALK_MODEL", "qwen3.7-plus")

    settings = get_settings(model_override="custom-model")

    assert settings.has_api_key is True
    assert settings.model == "custom-model"
