from __future__ import annotations

import json

import httpx

from embedding_validation import EmbeddingValidationOptions, validate_embedding_provider
from rag import LocalHashingEmbeddingProvider, OpenAICompatibleEmbeddingProvider
from scripts.validate_embedding_provider import main


def test_embedding_validation_accepts_semantic_provider_with_dense_probe() -> None:
    provider = _mock_semantic_provider()

    report = validate_embedding_provider(provider)

    assert report.ok is True
    assert report.provider == "openai-compatible"
    assert report.is_semantic is True
    assert report.health["ok"] is True
    assert report.sample_count == 3
    assert report.dimensions == 4
    assert report.dense_probe["top_title"] == "Urban Civilian Risk Control"
    assert report.dense_probe["top_score"] > 0.9
    assert report.issues == []


def test_embedding_validation_rejects_local_fallback_by_default() -> None:
    provider = LocalHashingEmbeddingProvider(dimensions=32)

    report = validate_embedding_provider(provider)

    assert report.ok is False
    assert report.is_semantic is False
    assert any("not semantic" in issue for issue in report.issues)


def test_embedding_validation_can_explicitly_allow_local_fallback() -> None:
    provider = LocalHashingEmbeddingProvider(dimensions=32)

    report = validate_embedding_provider(
        provider,
        options=EmbeddingValidationOptions(require_semantic=False),
    )

    assert report.ok is True
    assert report.is_semantic is False
    assert report.dense_probe["top_title"]


def test_validate_embedding_provider_cli_outputs_json_for_local_fallback(capsys) -> None:
    exit_code = main(
        [
            "--embedding-provider",
            "local-hashing",
            "--embedding-model",
            "local-hashing-v1",
            "--embedding-dimensions",
            "32",
            "--allow-local-fallback",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["provider"] == "local-hashing"
    assert payload["is_semantic"] is False
    assert payload["dense_probe"]["top_title"]


def test_validate_embedding_provider_cli_fails_when_real_semantic_provider_is_not_configured(capsys) -> None:
    exit_code = main(
        [
            "--embedding-provider",
            "local-hashing",
            "--embedding-model",
            "local-hashing-v1",
            "--embedding-dimensions",
            "32",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert any("not semantic" in issue for issue in payload["issues"])


def _mock_semantic_provider() -> OpenAICompatibleEmbeddingProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        inputs = payload["input"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": _embedding_for_text(text)}
                    for index, text in enumerate(inputs)
                ]
            },
        )

    return OpenAICompatibleEmbeddingProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="text-embedding-v4",
        dimensions=4,
        batch_size=2,
        max_retries=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _embedding_for_text(text: str) -> list[float]:
    lowered = text.lower()
    if "urban" in lowered or "civilian" in lowered:
        return [1.0, 0.0, 0.0, 0.0]
    if "mountain" in lowered or "supply" in lowered:
        return [0.0, 1.0, 0.0, 0.0]
    if "health" in lowered:
        return [0.5, 0.5, 0.0, 0.0]
    return [0.0, 0.0, 1.0, 0.0]
