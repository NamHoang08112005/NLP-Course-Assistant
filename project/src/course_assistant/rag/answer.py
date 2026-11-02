"""Orchestrate optional dialogue resolution, retrieval, prompting, and answering."""

from course_assistant.contracts import AssistantResult, ResolvedQuery, SemanticResult


def answer(question: str, query: SemanticResult | ResolvedQuery) -> AssistantResult:
    raise NotImplementedError("Group B: run retrieval and produce a grounded answer.")
