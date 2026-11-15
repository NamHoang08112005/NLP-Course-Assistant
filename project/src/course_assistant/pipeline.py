"""Connect single-question semantic analysis to the RAG answerer."""

from collections.abc import Mapping

from course_assistant.contracts import AssistantResult, SemanticResult
from course_assistant.nlp.semantic import analyze
from course_assistant.rag.answer import answer

_NO_ANSWER = "Xin lỗi, tôi không tìm thấy thông tin này trong dữ liệu của môn học."


def answer_question(
    question: str,
    semantic_result: SemanticResult | None = None,
) -> AssistantResult:
    question = question.strip()
    if not question:
        raise ValueError("Question must not be empty.")

    if semantic_result is None:
        semantic_result = analyze(question)
    elif semantic_result.question.strip() != question:
        raise ValueError("Semantic result must belong to the supplied question.")

    entities = semantic_result.semantic.get("entities", {})
    if (
        isinstance(entities, Mapping)
        and entities.get("_out_of_scope") == "OUT_OF_SCOPE"
    ):
        return AssistantResult(answer=_NO_ANSWER, abstained=True)
    if not semantic_result.valid:
        return AssistantResult(answer=_NO_ANSWER, abstained=True)

    return answer(question, semantic_result)
