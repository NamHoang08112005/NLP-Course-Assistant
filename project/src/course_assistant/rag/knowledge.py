"""Read and flatten the structured course knowledge base into retrieval records."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from course_assistant.rag.config import project_root


@dataclass(frozen=True)
class KnowledgeRecord:
    text: str
    source: str


def knowledge_base_path() -> Path:
    return project_root() / "data" / "knowledge_base.json"


@lru_cache(maxsize=1)
def load_knowledge_data() -> Mapping[str, Any]:
    path = knowledge_base_path()
    with path.open(encoding="utf-8-sig") as knowledge_file:
        data = json.load(knowledge_file)
    if not isinstance(data, Mapping):
        raise ValueError(f"Knowledge base must contain a JSON object: {path}")
    return data


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if item is not None)
    return str(value).strip()


def _walk(value: Any, path: tuple[str, ...]) -> Iterator[KnowledgeRecord]:
    if isinstance(value, Mapping):
        fields: list[str] = []
        branches: list[tuple[str, Any]] = []
        for key, child in value.items():
            if child is None:
                continue
            if not isinstance(child, (Mapping, list)):
                text = _format_value(child)
                if text:
                    fields.append(f"{key}: {text}")
            elif isinstance(child, list) and all(
                not isinstance(item, (Mapping, list)) for item in child
            ):
                text = _format_value(child)
                if text:
                    fields.append(f"{key}: {text}")
            else:
                branches.append((str(key), child))

        if fields:
            yield KnowledgeRecord(
                text=" | ".join(fields),
                source=".".join(path),
            )
        for key, child in branches:
            yield from _walk(child, (*path, key))
        return

    if isinstance(value, list):
        for index, item in enumerate(value, start=1):
            yield from _walk(item, (*path, str(index)))
        return

    text = _format_value(value)
    if text and any(character.isalpha() for character in text):
        yield KnowledgeRecord(text=text, source=".".join(path))


def load_knowledge_records() -> list[KnowledgeRecord]:
    return list(_walk(load_knowledge_data(), ()))
