from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_env_example_api_keys_are_forwarded_by_docker_compose() -> None:
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    configured_key_names = {
        line.split("=", 1)[0].strip()
        for line in env_example.splitlines()
        if line
        and not line.startswith("#")
        and line.split("=", 1)[0].strip()
        in {"DASHSCOPE_API_KEY", "MESSAGE_TALK_API_KEY", "MESSAGE_TALK_EMBEDDING_API_KEY"}
    }

    assert configured_key_names
    assert all(f"{key}: \"${{{key}:-}}\"" in compose for key in configured_key_names)
