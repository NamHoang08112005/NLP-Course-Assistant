"""Integration layer owned by the designated integrator."""

from course_assistant.contracts import AssistantResult


def answer_question(question: str) -> AssistantResult:
    raise NotImplementedError(
        "Connect NLP analysis, optional dialogue resolution, and RAG here."
    )
