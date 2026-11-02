"""Stable data contracts shared by the NLP and RAG workstreams."""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class SemanticResult:
    question: str
    valid: bool
    parse_tree: str | None
    semantic: Mapping[str, Any]
    retrieval_query: str
    unresolved_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedQuery:
    semantic_result: SemanticResult
    retrieval_query: str
    resolved_references: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source: str
    score: float | None = None


@dataclass(frozen=True)
class AssistantResult:
    answer: str
    retrieved_chunks: tuple[RetrievedChunk, ...] = ()
    sources: tuple[str, ...] = ()
    abstained: bool = False
