"""Generate all NLP, QA/RAG, Dialogue, and Evaluation artifacts."""

from collections.abc import Sequence

from course_assistant.contracts import AssistantResult, SemanticResult
from course_assistant.evaluation import run_evaluation
from course_assistant.nlp.formatters import (
    format_grammar,
    format_intent_entities,
    format_semantic,
)
from course_assistant.nlp.generator import generate_sentences
from course_assistant.nlp.grammar import load_grammar
from course_assistant.nlp.semantic import analyze
from course_assistant.pipeline import answer_question
from course_assistant.rag.config import load_config, project_root, selected_option
from course_assistant.rag.dialogue import run_dialogues


def _format_answers(results: list[AssistantResult]) -> str:
    return "\n".join(
        f"{index} | {' '.join(result.answer.split())}"
        for index, result in enumerate(results, start=1)
    )


def _format_retrievals(
    questions: Sequence[str],
    analyses: Sequence[SemanticResult],
    results: Sequence[AssistantResult],
) -> str:
    rows = []
    for index, (question, analysis, res) in enumerate(
        zip(questions, analyses, results), start=1
    ):
        if not analysis.valid or res.abstained and not res.retrieved_chunks:
            rows.append(
                f"{index} | QUESTION: {question} | SOURCES: - | CONTEXT: (Rejected by Parser / Out-of-Scope) | ANSWER: {res.answer}"
            )
            continue
        sources = ", ".join(res.sources) if res.sources else "-"
        top_context = (
            " ; ".join(chunk.text for chunk in res.retrieved_chunks[:2])
            if res.retrieved_chunks
            else "-"
        )
        rows.append(
            f"{index} | QUESTION: {question} | SOURCES: [{sources}] | CONTEXT: {top_context} | ANSWER: {res.answer}"
        )
    return "\n".join(rows)


def _expected_intent(analysis: SemanticResult) -> str:
    if not analysis.valid:
        return "UNKNOWN"

    action = analysis.semantic.get("action")
    if action in {
        "GET_CREDIT",
        "GET_ECTS",
        "GET_COURSE_NAME",
        "GET_INSTRUCTOR",
        "GET_SEMESTER",
        "GET_DEPARTMENT",
        "GET_COURSE_TYPE",
        "GET_FORMAT",
        "GET_HOURS",
        "GET_DESCRIPTION",
        "GET_OBJECTIVE",
        "GET_MAIN_PARTS",
        "GET_CHAPTER_COUNT",
        "GET_ASSESSMENT",
        "GET_EXAM_DURATION",
        "GET_EXAM_FORMAT",
    }:
        return "GET_COURSE_INFO"

    intent = analysis.semantic.get("intent", "UNKNOWN")
    return "UNKNOWN" if intent == "AMBIGUOUS" else intent


def _expected_entity(analysis: SemanticResult) -> str:
    entities = analysis.semantic.get("entities", {})
    if not isinstance(entities, dict):
        return "-"
    if entities.get("_out_of_scope") == "OUT_OF_SCOPE":
        return "OUT_OF_SCOPE"

    for key in (
        "week",
        "chapter",
        "topic",
        "lo",
        "assignment",
        "part",
        "rule",
        "exam",
        "course",
    ):
        value = entities.get(key)
        if value is None:
            continue
        if key == "week":
            return f"WEEK_{int(value):02d}" if str(value).isdigit() else str(value)
        if key == "chapter":
            chapter = str(value)
            return f"CH{int(chapter):02d}" if chapter.isdigit() else chapter
        if isinstance(value, list):
            return "[" + ",".join(str(item) for item in value) + "]"
        return str(value)
    return "-"


def _format_queries(
    questions: list[str],
    analyses: Sequence[SemanticResult],
) -> str:
    rows = [
        "ID | QUERY | EXPECTED_INTENT | EXPECTED_ENTITY",
        "",
    ]
    rows.extend(
        f"Q{index:03d} | {question} | "
        f"{_expected_intent(analysis)} | {_expected_entity(analysis)}"
        for index, (question, analysis) in enumerate(
            zip(questions, analyses),
            start=1,
        )
    )
    return "\n".join(rows)


def main() -> None:
    root = project_root()
    source = root / "input" / "sentences.txt"
    output = root / "output"
    output.mkdir(parents=True, exist_ok=True)

    grammar = load_grammar()
    # Keep raw lines aligned with Expected/ files for Part I & II.1-II.2
    raw_lines = source.read_text(encoding="utf-8-sig").splitlines()
    raw_analyses = [analyze(line) for line in raw_lines]

    files = {
        "grammar.txt": format_grammar(grammar),
        "samples.txt": "\n".join(generate_sentences(grammar, limit=10_000)),
        "parse-results.txt": "\n".join(item.parse_tree or "()" for item in raw_analyses),
        "semantic.txt": "\n".join(format_semantic(item) for item in raw_analyses),
        "intent-entity.txt": "\n".join(
            format_intent_entities(item) for item in raw_analyses
        ),
    }
    for name, body in files.items():
        (output / name).write_text(body + "\n", encoding="utf-8")

    questions = [line.strip() for line in raw_lines if line.strip()]
    analyses = [analyze(question) for question in questions]

    (output / "query.txt").write_text(
        _format_queries(questions, analyses) + "\n",
        encoding="utf-8",
    )

    answers = [
        answer_question(question, semantic_result=analysis)
        for question, analysis in zip(questions, analyses)
    ]
    config = load_config()
    answer_name = (
        "answer_llm.txt"
        if selected_option(config) == "llm"
        else "answer.txt"
    )
    answer_path = output / answer_name
    answer_path.write_text(
        _format_answers(answers) + "\n",
        encoding="utf-8",
    )

    # Write retrieval.txt showing question, retrieved context, and answer
    (output / "retrieval.txt").write_text(
        _format_retrievals(questions, analyses, answers) + "\n",
        encoding="utf-8",
    )

    run_dialogues(output_path=output / "dialogue.txt")

    run_evaluation(output_path=output / "evaluation.txt")

    print(
        f"Hoàn tất pipeline! Đã xuất đầy đủ các file vào {output}:\n"
        f"  - grammar.txt, samples.txt, parse-results.txt\n"
        f"  - semantic.txt, intent-entity.txt, query.txt, retrieval.txt\n"
        f"  - {answer_name}, dialogue.txt, evaluation.txt"
    )


if __name__ == "__main__":
    main()