from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from embedding_validation import EmbeddingValidationOptions, validate_embedding_provider
from rag import EmbeddingConfig, create_embedding_provider
from settings import get_settings


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()
    try:
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
        report = validate_embedding_provider(
            provider,
            options=EmbeddingValidationOptions(
                require_semantic=not args.allow_local_fallback,
                dense_probe_query=args.probe_query,
                expected_dense_title=args.expected_probe_title,
            ),
        )
        payload = report.to_dict()
    except Exception as exc:  # noqa: BLE001 - CLI reports configuration/provider boundary failures as JSON
        payload = {
            "ok": False,
            "provider": args.embedding_provider or settings.embedding_provider,
            "model": args.embedding_model or settings.embedding_model,
            "is_semantic": False,
            "dimensions": args.embedding_dimensions or settings.embedding_dimensions,
            "health": {},
            "sample_count": 0,
            "vector_count": 0,
            "dense_probe": {},
            "issues": [str(exc)],
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") is True else 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate an embedding provider with health, sample embedding, and dense retrieval probes."
    )
    parser.add_argument("--embedding-provider", help="Embedding provider, e.g. openai-compatible.")
    parser.add_argument("--embedding-model", help="Embedding model name.")
    parser.add_argument("--embedding-api-key", help="Embedding API key. Defaults to settings/env.")
    parser.add_argument("--embedding-base-url", help="OpenAI-compatible base URL.")
    parser.add_argument("--embedding-dimensions", type=int, help="Expected embedding vector dimensions.")
    parser.add_argument("--embedding-timeout", type=int, help="Embedding request timeout in seconds.")
    parser.add_argument("--embedding-batch-size", type=int, help="Embedding batch size.")
    parser.add_argument("--embedding-max-retries", type=int, help="Embedding max retries.")
    parser.add_argument(
        "--allow-local-fallback",
        action="store_true",
        help="Allow local-hashing to pass validation. Do not use this to claim real semantic dense retrieval.",
    )
    parser.add_argument(
        "--probe-query",
        default="urban civilian risk",
        help="Dense retrieval probe query.",
    )
    parser.add_argument(
        "--expected-probe-title",
        default="Urban Civilian Risk Control",
        help="Expected top title for the dense retrieval probe.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
