"""Retrieve relevant course chunks for a semantic or resolved query."""

from course_assistant.contracts import ResolvedQuery, RetrievedChunk, SemanticResult


def retrieve(query: SemanticResult | ResolvedQuery) -> list[RetrievedChunk]:
    raise NotImplementedError("Group B: retrieve ranked chunks and preserve source names.")
