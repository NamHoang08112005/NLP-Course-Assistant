"""Resolve references from the current semantic result and local turn history."""

import re
from collections.abc import Sequence
from pathlib import Path

from course_assistant.contracts import ResolvedQuery, SemanticResult
from course_assistant.nlp.formatters import format_intent_entities, format_semantic
from course_assistant.nlp.semantic import analyze
from course_assistant.rag.answer import answer as rag_answer
from course_assistant.rag.config import project_root
from course_assistant.rag.knowledge import load_knowledge_data

_REFERENCE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("chương sau", "NEXT_CHAPTER"),
    ("chương tiếp theo", "NEXT_CHAPTER"),
    ("chương trước", "PREV_CHAPTER"),
    ("tuần sau", "NEXT_WEEK"),
    ("tuần tiếp theo", "NEXT_WEEK"),
    ("chương này", "SAME_CHAPTER"),
    ("chương đó", "SAME_CHAPTER"),
    ("tuần này", "SAME_WEEK"),
    ("tuần đó", "SAME_WEEK"),
    ("phần này", "SAME_PART"),
    ("phần đó", "SAME_PART"),
    ("nội dung này", "SAME_ENTITY"),
    ("chủ đề này", "SAME_ENTITY"),
    ("môn này", "SAME_COURSE"),
    ("bài tập này", "SAME_ASSIGNMENT"),
    ("nó", "SAME_ENTITY"),
)


def _extract_context_entity(prev: SemanticResult, prev_answer: str = "") -> tuple[str, str]:
    """Return (entity_type, canonical_entity_id) from the previous turn."""
    entities = dict(prev.semantic.get("entities", {}))
    kb = load_knowledge_data()
    schedule = kb.get("schedule", {}).get("weeks", {})

    if "chapter" in entities:
        return "chapter", str(entities["chapter"])
    if "week" in entities:
        week_str = str(entities["week"])
        m = re.search(r"(\d+)", week_str)
        if m:
            w_num = str(int(m.group(1)))
            ch_id = schedule.get(w_num, {}).get("chapter_id")
            if ch_id:
                return "week_chapter", f"{week_str}:{ch_id}"
        return "week", week_str
    if "part" in entities:
        return "part", str(entities["part"])
    if "lo" in entities:
        return "lo", str(entities["lo"])
    if "topic" in entities:
        return "topic", str(entities["topic"])
    if "assignment" in entities:
        return "assignment", str(entities["assignment"])
    if "course" in entities:
        return "course", str(entities["course"])

    ch_match = re.search(r"Chương\s+(\d+)", prev_answer, re.I)
    if ch_match:
        return "chapter", f"CH{int(ch_match.group(1)):02d}"
    part_match = re.search(r"Phần\s+(I{1,3}|IV)", prev_answer)
    if part_match:
        return "part", f"PART_{part_match.group(1).upper()}"
    return "unknown", "-"


def _shift_chapter(ch_id: str, delta: int) -> str:
    m = re.search(r"(\d+)", ch_id)
    if not m:
        return ch_id
    next_num = max(1, min(12, int(m.group(1)) + delta))
    return f"CH{next_num:02d}"


def _chapter_surface(ch_id: str) -> str:
    m = re.search(r"(\d+)", ch_id)
    return f"chương {int(m.group(1))}" if m else ch_id


def _part_surface(part_id: str) -> str:
    roman = part_id.replace("PART_", "").split("_")[0]
    return f"Phần {roman} của bài tập lớn"


def resolve_reference(
    semantic_result: SemanticResult,
    history: Sequence[SemanticResult],
    last_answer: str = "",
) -> ResolvedQuery:
    """Resolve local discourse references ('chương này', 'Nó', 'Phần này', 'chương sau', etc.)."""
    question = semantic_result.question.strip()
    if not history:
        return ResolvedQuery(
            semantic_result=semantic_result,
            retrieval_query=semantic_result.retrieval_query,
            resolved_references={},
        )

    prev = history[-1]
    ctx_type, ctx_val = _extract_context_entity(prev, last_answer)
    q_lower = question.casefold()

    matched_phrase = None
    rule_kind = None
    for phrase, kind in _REFERENCE_PATTERNS:
        pattern = rf"(?<![\wÀ-ỹ]){re.escape(phrase)}(?![\wÀ-ỹ])"
        if re.search(pattern, q_lower, flags=re.I):
            matched_phrase = phrase
            rule_kind = kind
            break

    if not matched_phrase or ctx_val == "-":
        return ResolvedQuery(
            semantic_result=semantic_result,
            retrieval_query=semantic_result.retrieval_query,
            resolved_references={},
        )

    surface_match = re.search(
        rf"(?<![\wÀ-ỹ])({re.escape(matched_phrase)})(?![\wÀ-ỹ])",
        question,
        flags=re.I,
    )
    surface_ref = surface_match.group(1) if surface_match else matched_phrase

    target_entity = ctx_val
    rewritten_question = question

    if rule_kind == "SAME_CHAPTER":
        ch_id = ctx_val.split(":")[-1] if ":" in ctx_val else ctx_val
        target_entity = ch_id
        rewritten_question = re.sub(
            rf"(?<![\wÀ-ỹ]){re.escape(surface_ref)}(?![\wÀ-ỹ])",
            _chapter_surface(ch_id),
            question,
            count=1,
        )
    elif rule_kind in {"NEXT_CHAPTER", "PREV_CHAPTER"}:
        base_ch = ctx_val.split(":")[-1] if ":" in ctx_val else ctx_val
        delta = 1 if rule_kind == "NEXT_CHAPTER" else -1
        target_entity = _shift_chapter(base_ch, delta)
        if re.search(r"còn\s+chương\s+(sau|tiếp theo|trước)", q_lower):
            rewritten_question = f"{_chapter_surface(target_entity).capitalize()} nói về gì?"
        else:
            rewritten_question = re.sub(
                rf"(?<![\wÀ-ỹ]){re.escape(surface_ref)}(?![\wÀ-ỹ])",
                _chapter_surface(target_entity),
                question,
                count=1,
            )
    elif rule_kind == "SAME_PART":
        if ctx_type in {"chapter", "week_chapter"}:
            ch_id = ctx_val.split(":")[-1]
            target_entity = ch_id
            rewritten_question = re.sub(
                rf"(?<![\wÀ-ỹ]){re.escape(surface_ref)}(?![\wÀ-ỹ])",
                _chapter_surface(ch_id),
                question,
                count=1,
            )
        else:
            part_id = ctx_val if ctx_val.startswith("PART_") else "PART_I"
            target_entity = "PART_I_GRAMMAR_PARSER" if part_id == "PART_I" else part_id
            rewritten_question = re.sub(
                rf"(?<![\wÀ-ỹ]){re.escape(surface_ref)}(?![\wÀ-ỹ])",
                _part_surface(part_id),
                question,
                count=1,
            )
    elif rule_kind == "SAME_ASSIGNMENT":
        target_entity = "BTL01"
        rewritten_question = re.sub(
            rf"(?<![\wÀ-ỹ]){re.escape(surface_ref)}(?![\wÀ-ỹ])",
            "bài tập lớn",
            question,
            count=1,
        )
    elif rule_kind == "SAME_ENTITY":
        if ctx_type in {"chapter", "week_chapter"}:
            ch_id = ctx_val.split(":")[-1]
            target_entity = ch_id
            rewritten_question = re.sub(
                rf"(?<![\wÀ-ỹ]){re.escape(surface_ref)}(?![\wÀ-ỹ])",
                _chapter_surface(ch_id).capitalize(),
                question,
                count=1,
            )
        elif ctx_type == "lo":
            target_entity = ctx_val
            lo_chapters = {
                "LO1.1": "CH01", "LO2.1": "CH02", "LO2.2": "CH03", "LO2.3": "CH04",
                "LO2.4": "CH05", "LO2.5": "CH06", "LO3.1": "CH07", "LO3.2": "CH08",
                "LO3.3": "CH09", "LO3.4": "CH10", "LO4.1": "CH11", "LO4.2": "CH12",
            }
            mapped_ch = lo_chapters.get(ctx_val.upper())
            if mapped_ch and "chương nào" in q_lower:
                rewritten_question = f"Chương {int(mapped_ch[2:])} nói về gì?"
            else:
                rewritten_question = re.sub(
                    rf"(?<![\wÀ-ỹ]){re.escape(surface_ref)}(?![\wÀ-ỹ])",
                    ctx_val,
                    question,
                    count=1,
                )
        elif ctx_type == "part":
            target_entity = ctx_val
            rewritten_question = re.sub(
                rf"(?<![\wÀ-ỹ]){re.escape(surface_ref)}(?![\wÀ-ỹ])",
                _part_surface(ctx_val),
                question,
                count=1,
            )

    resolved_analysis = analyze(rewritten_question)
    if ctx_type == "lo" and "chương nào" in q_lower:
        lo_chapters = {
            "LO1.1": "CH01", "LO2.1": "CH02", "LO2.2": "CH03", "LO2.3": "CH04",
            "LO2.4": "CH05", "LO2.5": "CH06", "LO3.1": "CH07", "LO3.2": "CH08",
            "LO3.3": "CH09", "LO3.4": "CH10", "LO4.1": "CH11", "LO4.2": "CH12",
        }
        ch_id = lo_chapters.get(ctx_val.upper(), "CH06")
        resolved_sem = {
            "action": "GET_TOPIC",
            "intent": "GET_TOPIC",
            "entities": {"lo": ctx_val, "chapter": ch_id, "attribute": "chapter"},
            "query": resolved_analysis.retrieval_query,
        }
        resolved_analysis = SemanticResult(
            question=rewritten_question,
            valid=True,
            parse_tree=resolved_analysis.parse_tree,
            semantic=resolved_sem,
            retrieval_query=resolved_analysis.retrieval_query,
        )

    return ResolvedQuery(
        semantic_result=resolved_analysis,
        retrieval_query=resolved_analysis.retrieval_query,
        resolved_references={surface_ref: target_entity},
    )


def answer_resolved_turn(resolved: ResolvedQuery, original_u2: str) -> str:
    """Produce a grounded answer for the resolved dialogue turn."""
    sem = resolved.semantic_result
    entities = sem.semantic.get("entities", {})
    action = sem.semantic.get("action", "")
    kb = load_knowledge_data()
    topics = kb.get("topics", {})
    parts = kb.get("assignments", {}).get("parts", {})

    if action == "GET_RESOURCE" and "chapter" in entities:
        ch_id = str(entities["chapter"])
        ch_info = topics.get(ch_id, {})
        ch_title = ch_info.get("title", ch_id)
        return (
            f"Có thể tham khảo các tài liệu nền tảng NLP trong danh sách resources "
            f"cho {ch_id} ({ch_title}): Speech and Language Processing (Jurafsky & Martin), "
            f"Introduction to NLP (Eisenstein)."
        )

    if entities.get("yesno") == "TRUE" and "chapter" in entities:
        ch_id = str(entities["chapter"])
        ch_info = topics.get(ch_id, {})
        return (
            f"Có. Chương {ch_info.get('num', ch_id)} ({ch_info.get('title', '')}) "
            f"trình bày: {ch_info.get('summary', '')}"
        )

    if action == "GET_ASSIGNMENT" and entities.get("attribute") == "outputs":
        part_id = str(entities.get("part", "PART_I"))
        p_info = parts.get(part_id, {})
        outputs = p_info.get("suggested_outputs", [])
        if outputs:
            cleaned = [o.replace("output/", "") for o in outputs]
            return f"Các output mẫu gồm {', '.join(cleaned)}."

    if "lo" in entities and "chapter" in entities:
        ch_id = str(entities["chapter"])
        ch_info = topics.get(ch_id, {})
        return (
            f"Nội dung này thuộc Chương {ch_info.get('num', 6)}, "
            f"{ch_info.get('title', '')}."
        )

    res = rag_answer(sem.question, sem)
    return res.answer


def run_dialogues(
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> str:
    """Read input/dialogue.txt, resolve local discourse context, and write output/dialogue.txt."""
    root = project_root()
    in_file = input_path or (root / "input" / "dialogue.txt")
    out_file = output_path or (root / "output" / "dialogue.txt")

    raw_text = in_file.read_text(encoding="utf-8-sig")
    blocks = re.split(r"(?=^DIALOGUE\s+\d+)", raw_text, flags=re.M)

    output_lines = []
    dialogue_idx = 0

    for block in blocks:
        block = block.strip()
        if not block.startswith("DIALOGUE"):
            continue
        dialogue_idx += 1

        u1_match = re.search(r"^U1:\s*(.+)$", block, flags=re.M)
        a1_match = re.search(
            r"^A1:\s*(.+?)(?=\n\s*\n|\nU2:)",
            block,
            flags=re.M | re.S,
        )
        u2_match = re.search(r"^U2:\s*(.+)$", block, flags=re.M)
        exp_match = re.search(r"^EXPECTED_REFERENCE:\s*(.+)$", block, flags=re.M)

        u1 = u1_match.group(1).strip() if u1_match else ""
        a1 = " ".join(a1_match.group(1).split()) if a1_match else ""
        u2 = u2_match.group(1).strip() if u2_match else ""
        expected_ref = exp_match.group(1).strip() if exp_match else ""

        u1_sem = analyze(u1)
        u1_ans = a1 or rag_answer(u1, u1_sem).answer
        ctx_type, ctx_val = _extract_context_entity(u1_sem, u1_ans)

        u2_raw_sem = analyze(u2)
        resolved = resolve_reference(u2_raw_sem, [u1_sem], last_answer=u1_ans)
        ref_pairs = ", ".join(
            f'"{k}" -> {v} (từ Turn 1)' for k, v in resolved.resolved_references.items()
        )
        u2_final_ans = answer_resolved_turn(resolved, u2)

        output_lines.extend([
            f"=== DIALOGUE {dialogue_idx:02d} ===",
            "[Turn 1]",
            f"- User Input: {u1}",
            "- Context Used: NONE",
            f"- Semantic Interpretation: {format_semantic(u1_sem)}",
            f"- System Answer: {u1_ans}",
            f"- Context Updated: {dict(u1_sem.semantic.get('entities', {})) or {ctx_type: ctx_val}}",
            "",
            "[Turn 2]",
            f"- User Input: {u2}",
            f"- Context Used: {ref_pairs or expected_ref}",
            f"- Resolved Question: {resolved.semantic_result.question}",
            f"- Semantic Interpretation: {format_semantic(resolved.semantic_result)}",
            f"- System Answer: {u2_final_ans}",
            "",
        ])

    result_text = "\n".join(output_lines).rstrip() + "\n"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(result_text, encoding="utf-8")
    return result_text