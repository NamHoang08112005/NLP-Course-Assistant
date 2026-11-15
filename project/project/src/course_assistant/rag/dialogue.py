"""Resolve references from the current semantic result and local turn history."""

from collections.abc import Sequence

from course_assistant.contracts import ResolvedQuery, SemanticResult


def resolve_reference(
    semantic_result: SemanticResult,
    history: Sequence[SemanticResult],
) -> ResolvedQuery:
    raise NotImplementedError("Group B: resolve placeholders using recent dialogue context.")
