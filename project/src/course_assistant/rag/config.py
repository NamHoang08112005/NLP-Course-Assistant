"""Shared paths and validated configuration for the RAG options."""

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_environment() -> None:
    from dotenv import load_dotenv

    load_dotenv(project_root() / ".env")
    load_dotenv(project_root() / "src" / "course_assistant" / ".env")


def load_config() -> dict[str, Any]:
    config_path = project_root() / "models" / "rag_config.json"
    with config_path.open(encoding="utf-8-sig") as config_file:
        config = json.load(config_file)
    if not isinstance(config, dict):
        raise ValueError(f"RAG config must contain a JSON object: {config_path}")

    option = config.setdefault("option", "statistical")
    valid_numeric_option = type(option) is int and option in (1, 2)
    if not valid_numeric_option and option not in (
        "1",
        "2",
        "statistical",
        "llm",
    ):
        raise ValueError(
            "RAG config 'option' must be 1/'statistical' or 2/'llm'."
        )

    retrieval = config.setdefault("retrieval", {})
    if not isinstance(retrieval, dict):
        raise ValueError("RAG config 'retrieval' must contain a JSON object.")
    retrieval.setdefault("top_k", 5)
    config.setdefault("provider", "openai")
    config.setdefault("model", "gpt-4o-mini")
    config.setdefault("embedding_model", "text-embedding-3-small")
    config.setdefault("max_completion_tokens", 512)
    config.setdefault("temperature", 0.0)
    config.setdefault("index_path", "models/faiss_index")
    return config


def selected_option(config: dict[str, Any]) -> str:
    option = config.get("option", "statistical")
    if (type(option) is int and option == 1) or option in ("1", "statistical"):
        return "statistical"
    if (type(option) is int and option == 2) or option in ("2", "llm"):
        return "llm"
    raise ValueError("RAG config 'option' must be 1/'statistical' or 2/'llm'.")
