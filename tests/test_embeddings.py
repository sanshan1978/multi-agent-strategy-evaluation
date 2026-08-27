from __future__ import annotations

import json

import httpx
import pytest

from rag import OpenAICompatibleEmbeddingProvider


def test_openai_compatible_embedding_provider_batches_requests() -> None:
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        payloads.append(payload)
        inputs = payload["input"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": [1.0, 0.0, 0.0, float(index + 1)]}
                    for index, _text in enumerate(inputs)
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleEmbeddingProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="text-embedding-v4",
        dimensions=4,
        batch_size=2,
        max_retries=0,
        client=client,
    )

    vectors = provider.embed_texts(["alpha", "beta", "gamma"])

    assert len(vectors) == 3
    assert len(payloads) == 2
    assert payloads[0]["model"] == "text-embedding-v4"
    assert payloads[0]["input"] == ["alpha", "beta"]
    assert payloads[1]["input"] == ["gamma"]
    assert all(len(vector) == 4 for vector in vectors)
    assert provider.is_semantic is True
    client.close()


def test_openai_compatible_embedding_provider_health_check() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.0, 1.0, 0.0, 0.0]}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleEmbeddingProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="text-embedding-v4",
        dimensions=4,
        client=client,
    )

    health = provider.health_check()

    assert health.ok is True
    assert health.provider == "openai-compatible"
    assert health.model == "text-embedding-v4"
    assert health.dimensions == 4
    assert health.to_dict()["ok"] is True
    client.close()


def test_openai_compatible_embedding_provider_rejects_dimension_mismatch() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [1.0, 0.0]}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleEmbeddingProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="text-embedding-v4",
        dimensions=4,
        max_retries=0,
        client=client,
    )

    with pytest.raises(RuntimeError, match="embedding request failed"):
        provider.embed_query("dimension mismatch")
    client.close()
