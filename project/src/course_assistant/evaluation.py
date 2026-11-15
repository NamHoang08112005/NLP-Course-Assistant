"""Run evaluation cases and summarize assignment metrics (by text)."""

import re
from pathlib import Path

from course_assistant.nlp.formatters import format_intent_entities
from course_assistant.nlp.semantic import analyze
from course_assistant.pipeline import answer_question
from course_assistant.rag.config import project_root
from course_assistant.rag.dialogue import resolve_reference

_NO_ANSWER = "Xin lỗi, tôi không tìm thấy thông tin này trong dữ liệu của môn học."

_EXTRA_KB_MISSING_CASES = [
    ("Q035", "Môn NLP học ở phòng nào?", "GET_SCHEDULE", "CO3085", "KB_MISSING"),
    ("Q036", "Chương 13 nói về gì?", "GET_TOPIC", "CH13", "KB_MISSING"),
    ("Q037", "Tuần 16 học gì?", "GET_SCHEDULE", "WEEK_16", "KB_MISSING"),
    ("Q038", "L.O.5.1 là gì?", "GET_LO", "LO5.1", "KB_MISSING"),
    ("Q039", "Tài liệu nào xuất bản năm 2025?", "GET_RESOURCE", "2025", "KB_MISSING"),
    ("Q040", "Môn NLP có bao nhiêu sinh viên?", "UNKNOWN", "OUT_OF_SCOPE", "KB_MISSING"),
]


def _extract_predicted_intent(sem_result) -> str:
    rendered = format_intent_entities(sem_result)
    m = re.match(r"INTENT:\s*([^;]+);", rendered)
    return m.group(1).strip() if m else "UNKNOWN"


def _extract_predicted_entities_str(sem_result) -> str:
    rendered = format_intent_entities(sem_result)
    m = re.search(r"ENTITIES:\s*(.+)$", rendered)
    return m.group(1).strip() if m else "-"


def _entity_matches(expected_entity: str, sem_result, resolved_ref: dict | None = None) -> bool:
    ent_str = _extract_predicted_entities_str(sem_result)
    raw_entities = sem_result.semantic.get("entities", {})
    if expected_entity in ent_str:
        return True
    for v in raw_entities.values():
        if str(v) == expected_entity or expected_entity in str(v):
            return True
    if resolved_ref:
        for v in resolved_ref.values():
            if expected_entity in str(v) or str(v) in expected_entity:
                return True
    return False


def run_evaluation(output_path: Path | None = None) -> str:
    """Evaluate sample_queries.txt, KB-missing cases, and corpus statistics, writing output/evaluation.txt."""
    root = project_root()
    sample_file = root / "data" / "evaluation" / "sample_queries.txt"
    sentences_file = root / "input" / "sentences.txt"
    out_file = output_path or (root / "output" / "evaluation.txt")

    cases = []
    current_section = "VALID_AND_PARAPHRASE"
    for raw_line in sample_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "OUT-OF-SCOPE" in line:
            current_section = "OUT_OF_SCOPE"
            continue
        if "REFERENCE / CONTEXT" in line:
            current_section = "CONTEXT_DEPENDENT"
            continue
        if not re.match(r"^Q\d+\s*\|", line):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 4:
            cases.append((parts[0], parts[1], parts[2], parts[3], current_section))

    cases.extend(_EXTRA_KB_MISSING_CASES)

    total = len(cases)
    intent_correct = 0
    entity_correct = 0
    answer_correct = 0
    full_correct = 0

    detailed_rows = []
    history = []
    last_answer = ""

    for qid, query, exp_intent, exp_entity, category in cases:
        raw_sem = analyze(query)
        resolved_map = {}

        if exp_intent == "CONTEXT_DEPENDENT" and history:
            resolved = resolve_reference(raw_sem, history, last_answer=last_answer)
            active_sem = resolved.semantic_result
            resolved_map = dict(resolved.resolved_references)
            pred_intent = "CONTEXT_DEPENDENT" if resolved_map else _extract_predicted_intent(active_sem)
        else:
            active_sem = raw_sem
            pred_intent = _extract_predicted_intent(active_sem)

        ans_result = answer_question(active_sem.question, semantic_result=active_sem)
        last_answer = ans_result.answer
        history.append(active_sem)

        i_ok = (pred_intent == exp_intent) or (
            category == "KB_MISSING" and pred_intent in {exp_intent, "UNKNOWN"}
        )
        e_ok = _entity_matches(exp_entity, active_sem, resolved_map)

        if category in {"OUT_OF_SCOPE", "KB_MISSING"}:
            a_ok = ans_result.abstained or (_NO_ANSWER in ans_result.answer)
        else:
            a_ok = not ans_result.abstained and (_NO_ANSWER not in ans_result.answer)

        if i_ok:
            intent_correct += 1
        if e_ok:
            entity_correct += 1
        if a_ok:
            answer_correct += 1

        case_passed = i_ok and e_ok and a_ok
        if case_passed:
            full_correct += 1

        if not case_passed:
            predicted_entities = _extract_predicted_entities_str(active_sem)
            detailed_rows.append(
                f"- {qid} [{category}] \"{query}\" | "
                f"expected: {exp_intent}/{exp_entity} | "
                f"predicted: {pred_intent}/{predicted_entities}"
            )

    corpus_lines = [
        ln.strip()
        for ln in sentences_file.read_text(encoding="utf-8-sig").splitlines()
        if ln.strip()
    ]
    corpus_total = len(corpus_lines)
    corpus_valid_parses = sum(1 for ln in corpus_lines if analyze(ln).valid)
    corpus_invalid_parses = corpus_total - corpus_valid_parses


    category_counts = {
        category: sum(1 for case in cases if case[4] == category)
        for category in dict.fromkeys(case[4] for case in cases)
    }

    def percentage(value: int, denominator: int) -> float:
        return value / denominator * 100 if denominator else 0.0

    category_lines = [
        f"- {category}: {count}"
        for category, count in category_counts.items()
    ]
    review_lines = detailed_rows or ["- Không có ca nào cần xem lại."]

    report = f"""BÁO CÁO ĐÁNH GIÁ

Số ca kiểm thử: {total}
Theo nhóm:
{chr(10).join(category_lines)}

Intent đúng: {intent_correct}/{total} ({percentage(intent_correct, total):.1f}%)
Entity đúng: {entity_correct}/{total} ({percentage(entity_correct, total):.1f}%)
Câu trả lời đúng: {answer_correct}/{total} ({percentage(answer_correct, total):.1f}%)
Đạt cả ba tiêu chí: {full_correct}/{total} ({percentage(full_correct, total):.1f}%)

Corpus:
- Câu phân tích hợp lệ: {corpus_valid_parses}/{corpus_total} ({percentage(corpus_valid_parses, corpus_total):.1f}%)
- Câu không phân tích được: {corpus_invalid_parses}/{corpus_total} ({percentage(corpus_invalid_parses, corpus_total):.1f}%)

Ca cần xem lại:
{chr(10).join(review_lines)}
"""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report.strip() + "\n", encoding="utf-8")
    return report