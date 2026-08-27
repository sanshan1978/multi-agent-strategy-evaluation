from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str
    model: str
    dimensions: int = 128
    api_key: str = ""
    base_url: str = ""
    timeout_sec: float = 30.0
    batch_size: int = 32
    max_retries: int = 2


@dataclass(frozen=True)
class EmbeddingHealth:
    provider: str
    model: str
    ok: bool
    dimensions: int
    latency_ms: float
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "ok": self.ok,
            "dimensions": self.dimensions,
            "latency_ms": round(self.latency_ms, 3),
            "error": self.error,
        }


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimensions: int
    is_semantic: bool

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...

    def health_check(self) -> EmbeddingHealth:
        ...


class LocalHashingEmbeddingProvider:
    name = "local-hashing"
    is_semantic = False

    def __init__(self, dimensions: int = 128, model: str = "local-hashing-v1") -> None:
        self.dimensions = max(16, dimensions)
        self.model = model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return _normalize(vector)

    def health_check(self) -> EmbeddingHealth:
        started_at = time.perf_counter()
        vector = self.embed_query("health check")
        return EmbeddingHealth(
            provider=self.name,
            model=self.model,
            ok=bool(vector),
            dimensions=len(vector),
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )


class OpenAICompatibleEmbeddingProvider:
    name = "openai-compatible"
    is_semantic = True

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        dimensions: int = 1536,
        timeout_sec: float = 30.0,
        batch_size: int = 32,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("embedding api_key is required for openai-compatible provider")
        if not model:
            raise ValueError("embedding model is required for openai-compatible provider")
        self.model = model
        self.expected_dimensions = max(1, dimensions)
        self.dimensions = self.expected_dimensions
        self.batch_size = max(1, batch_size)
        self.max_retries = max(0, max_retries)
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_sec)
        self._endpoint = _embedding_endpoint(base_url)
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        cleaned = [_validate_embedding_text(text) for text in texts]
        if not cleaned:
            return []

        vectors: list[list[float]] = []
        for batch in _batched(cleaned, self.batch_size):
            vectors.extend(self._embed_batch(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_texts([text])
        return vectors[0] if vectors else []

    def health_check(self) -> EmbeddingHealth:
        started_at = time.perf_counter()
        try:
            vector = self.embed_query("embedding health check")
            return EmbeddingHealth(
                provider=self.name,
                model=self.model,
                ok=bool(vector),
                dimensions=len(vector),
                latency_ms=(time.perf_counter() - started_at) * 1000,
            )
        except Exception as exc:  # noqa: BLE001 - health check reports provider boundary failures
            return EmbeddingHealth(
                provider=self.name,
                model=self.model,
                ok=False,
                dimensions=0,
                latency_ms=(time.perf_counter() - started_at) * 1000,
                error=str(exc),
            )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": texts}
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.post(self._endpoint, headers=self._headers, json=payload)
                response.raise_for_status()
                return self._parse_vectors(response.json(), expected_count=len(texts))
            except Exception as exc:  # noqa: BLE001 - retry across network/provider errors
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(min(2.0, 0.25 * (2**attempt)))
        raise RuntimeError(f"embedding request failed after {self.max_retries + 1} attempts: {last_error}")

    def _parse_vectors(self, payload: dict[str, Any], expected_count: int) -> list[list[float]]:
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("embedding response missing data list")

        ordered = sorted(data, key=lambda item: int(item.get("index", 0)) if isinstance(item, dict) else 0)
        vectors: list[list[float]] = []
        for item in ordered:
            if not isinstance(item, dict):
                raise ValueError("embedding response data item must be an object")
            raw_vector = item.get("embedding")
            if not isinstance(raw_vector, list) or not raw_vector:
                raise ValueError("embedding response item missing embedding vector")
            vector = [float(value) for value in raw_vector]
            if len(vector) != self.expected_dimensions:
                raise ValueError(
                    "embedding vector dimension mismatch: "
                    f"expected {self.expected_dimensions}, got {len(vector)}"
                )
            vectors.append(_normalize(vector))

        if len(vectors) != expected_count:
            raise ValueError(f"embedding response count mismatch: expected {expected_count}, got {len(vectors)}")
        self.dimensions = len(vectors[0]) if vectors else self.expected_dimensions
        return vectors


def create_embedding_provider(config: EmbeddingConfig) -> EmbeddingProvider:
    provider = config.provider.strip().lower()
    if provider in {"", "off", "none", "disabled"}:
        raise ValueError("embedding provider is disabled")
    if provider in {"local", "local-hashing", "hashing"}:
        return LocalHashingEmbeddingProvider(
            dimensions=config.dimensions,
            model=config.model or "local-hashing-v1",
        )
    if provider in {"openai", "openai-compatible", "dashscope"}:
        return OpenAICompatibleEmbeddingProvider(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            dimensions=config.dimensions,
            timeout_sec=config.timeout_sec,
            batch_size=config.batch_size,
            max_retries=config.max_retries,
        )
    raise ValueError(f"unsupported embedding provider: {config.provider}")


def _embedding_endpoint(base_url: str) -> str:
    normalized = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
    if normalized.endswith("/embeddings"):
        return normalized
    return f"{normalized}/embeddings"


def _validate_embedding_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        raise ValueError("embedding input text cannot be empty")
    return cleaned


def _batched(items: list[str], batch_size: int) -> list[list[str]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_RE.findall(text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", match):
            tokens.extend(_char_ngrams(match, size=2))
            tokens.append(match)
        else:
            tokens.append(match)
    return tokens


def _char_ngrams(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    return [text[index : index + size] for index in range(len(text) - size + 1)]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
