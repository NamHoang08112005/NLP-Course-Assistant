"""Stable text renderers for Group A artifacts."""
import json
import re


COURSE_INFO_ACTIONS = {
    "GET_CREDIT",
    "GET_ECTS",
    "GET_SEMESTER",
    "GET_COURSE_NAME",
    "GET_DEPARTMENT",
    "GET_COURSE_TYPE",
    "GET_FORMAT",
    "GET_HOURS",
    "GET_DESCRIPTION",
    "GET_OBJECTIVE",
    "GET_MAIN_PARTS",
    "GET_ASSESSMENT",
    "GET_EXAM_DURATION",
    "GET_EXAM_FORMAT",
    "GET_CHAPTER_COUNT",
}

INFERRED_ATTRIBUTES = {
    "GET_CREDIT": "credits",
    "GET_ECTS": "ects",
    "GET_SEMESTER": "semester",
    "GET_COURSE_NAME": "course_name",
    "GET_DEPARTMENT": "department",
    "GET_COURSE_TYPE": "course_type",
    "GET_FORMAT": "format",
    "GET_HOURS": "hours",
    "GET_DESCRIPTION": "description",
    "GET_OBJECTIVE": "objective",
    "GET_MAIN_PARTS": "main_parts",
    "GET_ASSESSMENT": "assessment",
    "GET_EXAM_DURATION": "duration",
    "GET_EXAM_FORMAT": "exam_format",
    "GET_CHAPTER_COUNT": "chapter_count",
}


def format_semantic(result):
    if not result.valid:
        return "()"
    semantic = result.semantic
    action = semantic.get("action", "UNKNOWN")
    entities = dict(semantic.get("entities", {}))
    if action in COURSE_INFO_ACTIONS:
        entities.pop("attribute", None)
    arguments = ", ".join(
        f"{key}={_format_value(value)}" for key, value in entities.items()
    )
    return f"{action}({arguments})"


def format_intent_entities(result):
    semantic = result.semantic
    action = semantic.get("action", "UNKNOWN")
    intent = semantic.get("intent", "UNKNOWN") if result.valid else "UNKNOWN"
    if action in COURSE_INFO_ACTIONS:
        intent = "GET_COURSE_INFO"

    entities = dict(semantic.get("entities", {}))
    if not result.valid and "_out_of_scope" not in entities:
        entities = {}
    if "_out_of_scope" in entities:
        entities = {"OUT_OF_SCOPE": None}

    for key, value in tuple(entities.items()):
        if isinstance(value, str):
            match = re.fullmatch(r"@AMBIGUOUS\((.*)\)", value)
            if match:
                alternatives = match.group(1).split("|")
                if key == "part" and alternatives[0].startswith("TOPIC_"):
                    entities.pop(key)
                    entities["topic"] = (
                        alternatives[0][len("TOPIC_"):] + "|part=" + alternatives[1]
                    )
                elif key == "final":
                    entities.pop(key)
                    entities["exam"] = "FINAL|milestone=" + alternatives[1]
                else:
                    entities[key] = match.group(1)

    for key, value in tuple(entities.items()):
        if isinstance(value, list):
            entities[key] = "[" + ",".join(str(item) for item in value) + "]"

    if action in INFERRED_ATTRIBUTES:
        attribute = INFERRED_ATTRIBUTES[action]
        if action == "GET_COURSE_NAME" and entities.get("lang") == "EN":
            attribute = "course_name_en"
        entities["attribute"] = attribute
    if action == "GET_TOPIC" and entities.get("course"):
        entities["attribute"] = "chapters"
    if action == "GET_SCHEDULE" and "week" in entities:
        question = result.question.casefold()
        if "bài tập lớn" in question or "btl" in question:
            entities = {"assignment": "BTL01", **entities}

    if entities:
        body = ", ".join(
            key if value is None else f"{key}={value}"
            for key, value in entities.items()
        )
    else:
        body = "-"
    return f"INTENT: {intent}; ENTITIES: {body}"


def _format_value(value):
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(str(item) for item in value) + "]"
    return value


def format_grammar(grammar):
    lines = []
    for lhs, alternatives in grammar.productions.items():
        formatted = []
        for alternative in alternatives:
            formatted.append(" ".join(alternative))
        lines.append(f"{lhs} -> {' | '.join(formatted)}")
    return "\n".join(lines)
