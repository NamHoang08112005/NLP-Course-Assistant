"""Generate a concise answer from retrieved course knowledge."""

import re
import unicodedata

from course_assistant.contracts import AssistantResult, RetrievedChunk, SemanticResult
from course_assistant.rag.client import generate
from course_assistant.rag.config import load_config, selected_option
from course_assistant.rag.knowledge import load_knowledge_data
from course_assistant.rag.prompt import build_prompt
from course_assistant.rag.retriever import retrieve

_NO_ANSWER = "Xin lỗi, tôi không tìm thấy thông tin này trong dữ liệu của môn học."


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )


def _faq_answer(text: str) -> str | None:
    match = re.search(r"(?:^|\|\s*)answer:\s*(.*)", text, flags=re.DOTALL)
    if match is None:
        return None
    return " ".join(match.group(1).split()).strip()


def _faq_matches_question(question: str, text: str) -> bool:
    match = re.search(
        r"(?:^|\|\s*)question:\s*(.*?)(?:\s*\|\s*answer:|$)",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        return False

    stop_words = {"bao", "co", "gi", "la", "mon", "nao", "nhung", "ve"}
    query_terms = {
        term
        for term in re.findall(r"[^\W_]+", _normalize(question))
        if term not in stop_words and len(term) > 1
    }
    faq_terms = {
        term
        for term in re.findall(r"[^\W_]+", _normalize(match.group(1)))
        if term not in stop_words and len(term) > 1
    }
    if not query_terms or not faq_terms:
        return False
    return len(query_terms & faq_terms) / min(len(query_terms), len(faq_terms)) >= 0.5


def _entity_number(value: object, prefix: str) -> int | None:
    match = re.search(rf"(?:{prefix})[_\s-]*(\d+)$", str(value), re.IGNORECASE)
    if match is None:
        return None
    return int(match.group(1))


def _structured_answer(
    query: SemanticResult,
    chunks: list[RetrievedChunk],
) -> str | None:
    data = load_knowledge_data()
    entities = query.semantic.get("entities", {})
    if not isinstance(entities, dict):
        return None

    action = query.semantic.get("action")
    course = data["course_info"]
    course_name = course["course_name"]
    course_id = course["course_id"]
    course_label = f"{course_name} ({course_id})"

    direct_fields = {
        "GET_CREDIT": ("credits", f"Môn {course_label} có {{value}} tín chỉ."),
        "GET_ECTS": ("ects", f"Môn {course_label} có {{value}} ECTS."),
        "GET_INSTRUCTOR": (
            "instructor",
            f"Giảng viên của môn {course_name} là {{value}}.",
        ),
        "GET_SEMESTER": (
            "semester",
            f"Môn {course_label} được tổ chức vào học kỳ {{value}}.",
        ),
        "GET_DEPARTMENT": (
            "department",
            f"Môn học thuộc {{value}}.",
        ),
        "GET_COURSE_TYPE": (
            "course_type",
            f"Môn học thuộc khối kiến thức {{value}}.",
        ),
        "GET_DESCRIPTION": ("description", "{value}"),
        "GET_OBJECTIVE": ("goal", "{value}"),
        "GET_COURSE_NAME": (
            "course_name_en" if entities.get("lang") == "EN" else "course_name",
            "{value}",
        ),
    }
    if action in direct_fields:
        key, template = direct_fields[action]
        value = course.get(key)
        if value:
            return template.format(value=" ".join(str(value).split()))

    if action == "GET_ECTS":
        value = course.get("ects")
        if value:
            return f"Môn {course_label} có {value} ECTS."

    if action == "GET_FORMAT":
        format_value = course.get("format", "")
        aspect = entities.get("aspect")
        if aspect == "WEEKS":
            match = re.search(r"(\d+)\s+weeks?", str(format_value), re.IGNORECASE)
            if match:
                return f"Môn học kéo dài {match.group(1)} tuần."
        if aspect == "PERIODS_PER_WEEK":
            match = re.search(
                r"(\d+)\s+lecture periods per week",
                str(format_value),
                re.IGNORECASE,
            )
            if match:
                return f"Mỗi tuần môn học có {match.group(1)} tiết lý thuyết."
        return str(format_value) or None

    if action == "GET_HOURS":
        fields = {
            "TOTAL": ("total_course_hours", "Tổng thời lượng môn học là {value} giờ."),
            "LECTURE": ("lecture_hours", "Thời lượng lý thuyết là {value} giờ."),
            "ASSIGNMENT": (
                "major_assignment_hours",
                "Thời lượng dành cho bài tập lớn là {value} giờ.",
            ),
            "SELF_STUDY": ("self_study_hours", "Thời lượng tự học là {value} giờ."),
        }
        selected = fields.get(entities.get("type"))
        if selected and course.get(selected[0]):
            return selected[1].format(value=course[selected[0]])

    if action == "GET_ASSESSMENT":
        assessment_fields = {
            "CLASS_ATTENTION_AND_ASSIGNMENTS": (
                "class_attention_and_assignments",
                "Điểm chuyên cần và bài tập chiếm {value}.",
            ),
            "MAJOR_ASSIGNMENT": (
                "major_assignment",
                "Bài tập lớn chiếm {value} điểm.",
            ),
            "MIDTERM": ("midterm_exam", "Thi giữa kỳ chiếm {value} điểm."),
            "FINAL": ("final_exam", "Thi cuối kỳ chiếm {value} điểm."),
        }
        selected = assessment_fields.get(entities.get("component"))
        if selected and course.get(selected[0]):
            return selected[1].format(value=course[selected[0]])
        parts = [
            f"{label}: {course[key]}"
            for label, key in (
                ("Chuyên cần và bài tập", "class_attention_and_assignments"),
                ("Bài tập lớn", "major_assignment"),
                ("Giữa kỳ", "midterm_exam"),
                ("Cuối kỳ", "final_exam"),
            )
            if course.get(key)
        ]
        if parts:
            return "Cơ cấu điểm gồm " + "; ".join(parts) + "."

    if action in {"GET_EXAM_DURATION", "GET_EXAM_FORMAT"}:
        exam = str(entities.get("exam", "")).casefold()
        details = course.get(exam)
        if details:
            duration = re.search(r"(\d+)\s+minutes?", str(details), re.IGNORECASE)
            if action == "GET_EXAM_DURATION" and duration:
                label = "giữa kỳ" if exam == "midterm" else "cuối kỳ"
                return f"Thời lượng thi {label} là {duration.group(1)} phút."
            if action == "GET_EXAM_FORMAT":
                return f"Hình thức thi {exam} là {details}."

    if action == "GET_CHAPTER_COUNT":
        chapters = data.get("topics", {})
        if chapters:
            return f"Môn học có {len(chapters)} chương."

    if action == "GET_MAIN_PARTS":
        parts = course.get("main_parts", "")
        if parts:
            normalized = " ".join(str(parts).split())
            return f"Môn học gồm các phần chính: {normalized}."

    if action == "GET_LO":
        outcomes = data.get("learning_outcomes", {})
        learning_outcome = entities.get("lo")
        if learning_outcome:
            value = outcomes.get(str(learning_outcome).upper())
            if value:
                return f"{str(learning_outcome).upper()}: {' '.join(str(value).split())}"
        if outcomes:
            return "; ".join(
                f"{key}: {' '.join(str(value).split())}"
                for key, value in outcomes.items()
            )

    if action in {"GET_DEADLINE", "GET_ASSIGNMENT"}:
        assignment = data.get("assignments", {})
        deadline = assignment.get("overview", {}).get("deadline")
        if action == "GET_DEADLINE" and deadline:
            return f"Deadline bài tập lớn là {deadline}."
        part = str(entities.get("part", "")).upper()
        part_data = assignment.get("parts", {}).get(part)
        if part_data:
            requirements = part_data.get("requirements", [])
            details = "; ".join(str(item) for item in requirements)
            return f"Phần {part_data.get('roman', '')} - {part_data.get('title', '')}: {details}."
        overview = assignment.get("overview", {})
        if overview.get("goal"):
            return f"Bài tập lớn yêu cầu {overview['goal']}"

    if action == "GET_RULE":
        regulations = data.get("regulations", {})
        rule = str(entities.get("rule", ""))
        value = next(
            (
                text
                for key, text in regulations.items()
                if key.casefold() == rule.casefold()
            ),
            None,
        )
        if value:
            return " ".join(str(value).split())

    if action == "GET_TOPIC":
        topics = data.get("topics", {})
        topic_entity = entities.get("chapter") or entities.get("topic")
        chapter_number = _entity_number(topic_entity, "CH")
        if chapter_number is not None:
            chapter_id = f"CH{chapter_number:02d}"
            chapter = topics.get(chapter_id)
            if chapter:
                return (
                    f"Chương {chapter_number} ({chapter.get('title', '')}): "
                    f"{chapter.get('summary', '')}"
                )
        elif topic_entity:
            target = _normalize(str(topic_entity))
            for chapter_id, chapter in topics.items():
                searchable = " ".join(
                    [
                        str(chapter.get("title", "")),
                        str(chapter.get("summary", "")),
                        " ".join(str(item) for item in chapter.get("keywords", [])),
                        " ".join(
                            str(item[-1])
                            for item in chapter.get("subtopics", [])
                            if isinstance(item, list) and item
                        ),
                    ]
                )
                if target and target in _normalize(searchable):
                    return (
                        f"{chapter_id} ({chapter.get('title', '')}): "
                        f"{chapter.get('summary', '')}"
                    )

    if action == "GET_RESOURCE":
        items = data.get("resources", {}).get("items", [])
        matching_items = []
        for chunk in chunks:
            match = re.fullmatch(r"resources\.items\.(\d+)", chunk.source)
            if match:
                item_index = int(match.group(1)) - 1
                if 0 <= item_index < len(items):
                    title = items[item_index].get("title")
                    if title and title not in matching_items:
                        matching_items.append(title)
        if matching_items:
            return "Tài liệu phù hợp: " + "; ".join(matching_items) + "."

    return None


def _schedule_answer(
    query: SemanticResult,
    chunks: list[RetrievedChunk],
) -> str | None:
    data = load_knowledge_data()
    schedule = data.get("schedule", {}).get("weeks", {})
    entities = query.semantic.get("entities", {})
    if not isinstance(entities, dict):
        return None

    week_value = entities.get("week")
    if week_value is not None:
        week = _entity_number(week_value, "WEEK")
        record = schedule.get(str(week)) if week is not None else None
        if record:
            topics = ", ".join(record.get("topics", []))
            if entities.get("attribute") == "PART":
                return f"Tuần {week} thuộc phần {record.get('part', '')}."
            if entities.get("attribute") == "CHAPTER":
                return f"Tuần {week} học {record.get('chapter', '')}."
            return f"Tuần {week} học {topics}."

    chapter_value = entities.get("chapter")
    if chapter_value is not None:
        chapter_number = _entity_number(chapter_value, "CH")
        target = (
            f"CH{chapter_number:02d}"
            if chapter_number is not None
            else str(chapter_value)
        )
        weeks = [
            int(week)
            for week, record in schedule.items()
            if record.get("chapter_id") == target
        ]
        if weeks:
            week_text = ", ".join(f"tuần {week}" for week in weeks)
            return f"{target} được học vào {week_text}."

    topic_value = entities.get("topic")
    if topic_value:
        topic = _normalize(str(topic_value))
        topic_aliases = {
            "cfg": "context free grammar",
            "pcfg": "probabilistic context free grammar",
            "qa": "question answering",
        }
        topic = topic_aliases.get(topic, topic)
        matching_weeks = [
            int(week)
            for week, record in schedule.items()
            if topic
            in _normalize(
                " ".join(
                    [
                        *record.get("topics", []),
                        str(record.get("part", "")),
                        str(record.get("chapter", "")),
                    ]
                )
            )
        ]
        if matching_weeks:
            week_text = ", ".join(
                f"tuần {week}" for week in matching_weeks
            )
            return f"{topic_value} được học ở {week_text}."

    if chunks:
        return _schedule_answer_from_retrieval(query.question, chunks)
    return None


def _schedule_answer_from_retrieval(
    question: str,
    chunks: list[RetrievedChunk],
) -> str | None:
    normalized_question = _normalize(question)
    week_match = re.search(r"(?:tuan|week)\s*(\d+)", normalized_question)
    if week_match is None:
        return None

    week = int(week_match.group(1))
    for chunk in chunks:
        if chunk.source != f"schedule.weeks.{week}":
            continue
        topics_match = re.search(
            r"(?:^|\|\s*)topics:\s*(.*?)(?:\s*\|\s*part:|$)",
            chunk.text,
            flags=re.DOTALL,
        )
        if topics_match:
            topics = " ".join(topics_match.group(1).split())
            return f"Tuần {week} học {topics}."
    return None


def _statistical_answer(
    query: SemanticResult,
    chunks: list[RetrievedChunk],
) -> str:
    direct_answer = _structured_answer(query, chunks)
    if direct_answer:
        return direct_answer

    if query.semantic.get("action") in {"GET_SCHEDULE", "GET_TOPIC"}:
        schedule_answer = _schedule_answer(query, chunks)
        if schedule_answer:
            return schedule_answer

    for chunk in chunks:
        if not _faq_matches_question(query.question, chunk.text):
            continue
        answer = _faq_answer(chunk.text)
        if answer:
            return answer

    return _NO_ANSWER


def answer(question: str, query: SemanticResult) -> AssistantResult:
    config = load_config()
    option = selected_option(config)
    chunks = retrieve(query)

    if option == "llm":
        answer_text = (
            generate(build_prompt(question, chunks)) if chunks else _NO_ANSWER
        )
    else:
        answer_text = _statistical_answer(query, chunks)

    answer_text = " ".join(answer_text.split())
    sources = tuple(dict.fromkeys(chunk.source for chunk in chunks))
    return AssistantResult(
        answer=answer_text,
        retrieved_chunks=tuple(chunks),
        sources=sources,
        abstained=answer_text == _NO_ANSWER,
    )
