from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="message_talk_pytest_")
_TEST_RUNTIME_PATH = Path(_TEST_RUNTIME.name)
_API_KEY_ENV_NAMES = [
    "MESSAGE_TALK_API_KEY",
    "SAFETY_AGENT_API_KEY",
    "DASHSCOPE_API_KEY",
    "API_KEY",
    "OPENAI_API_KEY",
    "MESSAGE_TALK_EMBEDDING_API_KEY",
    "EMBEDDING_API_KEY",
]


def _apply_local_rag_profile(data_dir: Path) -> None:
    for key in _API_KEY_ENV_NAMES:
        os.environ.pop(key, None)
    os.environ.update(
        {
            "MESSAGE_TALK_DB_PATH": str(data_dir / "decision_records.db"),
            "MESSAGE_TALK_EMBEDDING_PROVIDER": "local-hashing",
            "MESSAGE_TALK_EMBEDDING_MODEL": "local-hashing-v1",
            "MESSAGE_TALK_EMBEDDING_DIMENSIONS": "128",
            "MESSAGE_TALK_VECTOR_STORE": "sqlite",
            "MESSAGE_TALK_VECTOR_DB_PATH": str(data_dir / "rag_vectors.db"),
            "MESSAGE_TALK_VECTOR_COLLECTION": "tactical_knowledge",
            "MESSAGE_TALK_INGESTION_HISTORY_DB_PATH": str(data_dir / "rag_ingestion.db"),
            "MESSAGE_TALK_RAG_DENSE_ENABLED": "true",
            "MESSAGE_TALK_RAG_STRICT_EMBEDDING": "false",
        }
    )


# Test modules can create configured services during collection, before fixtures run.
_apply_local_rag_profile(_TEST_RUNTIME_PATH)


@pytest.fixture(autouse=True)
def isolated_test_runtime(monkeypatch, tmp_path) -> None:
    for key in _API_KEY_ENV_NAMES:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("MESSAGE_TALK_DB_PATH", str(tmp_path / "decision_records.db"))
    monkeypatch.setenv("MESSAGE_TALK_EMBEDDING_PROVIDER", "local-hashing")
    monkeypatch.setenv("MESSAGE_TALK_EMBEDDING_MODEL", "local-hashing-v1")
    monkeypatch.setenv("MESSAGE_TALK_EMBEDDING_DIMENSIONS", "128")
    monkeypatch.setenv("MESSAGE_TALK_VECTOR_STORE", "sqlite")
    monkeypatch.setenv("MESSAGE_TALK_VECTOR_DB_PATH", str(tmp_path / "rag_vectors.db"))
    monkeypatch.setenv("MESSAGE_TALK_VECTOR_COLLECTION", "tactical_knowledge")
    monkeypatch.setenv(
        "MESSAGE_TALK_INGESTION_HISTORY_DB_PATH",
        str(tmp_path / "rag_ingestion.db"),
    )
    monkeypatch.setenv("MESSAGE_TALK_RAG_DENSE_ENABLED", "true")
    monkeypatch.setenv("MESSAGE_TALK_RAG_STRICT_EMBEDDING", "false")
