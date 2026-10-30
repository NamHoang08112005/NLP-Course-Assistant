"""Earley parser and simple semantic/intent extraction for the course CFG."""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple, Union

from .grammar_generator import RuleMap, load_grammar_text, parse_grammar, resolve_runtime_paths


Tree = Union[str, Tuple[str, Tuple["Tree", ...]]]

INTENTS = {
    "INFO_Q": "GET_COURSE_INFO", "SCHED_Q": "GET_SCHEDULE",
    "TOPIC_Q": "GET_TOPIC", "ASSIGN_Q": "GET_ASSIGNMENT",
    "DEADLINE_Q": "GET_DEADLINE", "RESOURCE_Q": "GET_RESOURCE", "RULE_Q": "GET_RULE",
    "VP_Credit": "GET_COURSE_INFO",
    "VP_Topic": "GET_TOPIC",
    "VP_Schedule": "GET_SCHEDULE",
    "VP_Req": "GET_ASSIGNMENT",
    "VP_Time": "GET_DEADLINE",
    "VP_Res": "GET_RESOURCE",
    "VP_YN": "GET_RULE",
    "VP_Todo": "GET_ASSIGNMENT",
    "INSTRUCTOR_Q": "GET_COURSE_INFO", "TOPIC_YN_Q": "GET_TOPIC",
    "GROUP_SIZE_Q": "GET_ASSIGNMENT", "LATE_Q": "GET_RULE",
    "ATTENDANCE_Q": "GET_RULE", "TEXTBOOK_Q": "GET_RESOURCE",
    "REFERENCE_Q": "GET_RESOURCE",
}


def _earley_parse(sentence: str, rules: RuleMap) -> Optional[Tree]:
    """Return the first parse tree found by an Earley chart parser."""
    sentence = unicodedata.normalize("NFKC", sentence)
    sentence = sentence.translate(str.maketrans({"“": "", "”": "", "‘": "", "’": ""}))
    sentence = re.sub(r"\b0+(\d+)\b", r"\1", sentence)
    nonterminals = set(rules)
    start_symbol = "S" if "S" in nonterminals else next(iter(rules))
    sentence = re.sub(r"[?.!]+\s*$", "", sentence.strip())
    tokens = re.findall(r"\w+|[^\w\s]", sentence, flags=re.UNICODE)
    normalized_tokens = [token.casefold() for token in tokens]
    chart: List[Dict[Tuple[str, Tuple[str, ...], int, int], Tuple[Tree, ...]]] = [
        {} for _ in range(len(tokens) + 1)
    ]
    queues: List[List[Tuple[str, Tuple[str, ...], int, int]]] = [
        [] for _ in range(len(tokens) + 1)
    ]
    synthetic_start = "__EARLEY_START__"
    initial = (synthetic_start, (start_symbol,), 0, 0)
    chart[0][initial] = ()
    queues[0].append(initial)

    def add_state(
        position: int,
        key: Tuple[str, Tuple[str, ...], int, int],
        children: Tuple[Tree, ...],
    ) -> None:
        if key not in chart[position]:
            chart[position][key] = children
            queues[position].append(key)

    for position in range(len(tokens) + 1):
        cursor = 0
        while cursor < len(queues[position]):
            key = queues[position][cursor]
            cursor += 1
            left, right, dot, origin = key
            children = chart[position][key]

            if dot < len(right):
                expected = right[dot]
                if expected in nonterminals:
                    for production in rules[expected]:
                        add_state(position, (expected, production, 0, position), ())

                    # This also handles nullable productions already completed
                    # at the same chart position.
                    for completed_key, completed_children in list(chart[position].items()):
                        c_left, c_right, c_dot, c_origin = completed_key
                        if c_left == expected and c_dot == len(c_right) and c_origin == position:
                            node: Tree = (c_left, completed_children)
                            add_state(
                                position,
                                (left, right, dot + 1, origin),
                                children + (node,),
                            )
                else:
                    # CFG terminals may be quoted phrases such as "bao nhiêu".
                    terminal_tokens = re.findall(r"\w+|[^\w\s]", expected, flags=re.UNICODE)
                    end = position + len(terminal_tokens)
                    if (
                        terminal_tokens
                        and end <= len(tokens)
                        and [token.casefold() for token in terminal_tokens]
                        == normalized_tokens[position:end]
                    ):
                        # Preserve the input's original casing and punctuation.
                        add_state(
                            end,
                            (left, right, dot + 1, origin),
                            children + (" ".join(tokens[position:end]),),
                        )
                continue

            completed: Tree = (left, children)
            for waiting_key, waiting_children in list(chart[origin].items()):
                w_left, w_right, w_dot, w_origin = waiting_key
                if w_dot < len(w_right) and w_right[w_dot] == left:
                    add_state(
                        position,
                        (w_left, w_right, w_dot + 1, w_origin),
                        waiting_children + (completed,),
                    )

    final_key = (synthetic_start, (start_symbol,), 1, 0)
    if final_key not in chart[len(tokens)]:
        return None
    children = chart[len(tokens)][final_key]
    return children[0] if children else None


def _format_tree(tree: Tree) -> str:
    if isinstance(tree, str):
        return re.sub(r"\s+", "_", re.sub(r"\s*-\s*", "-", tree.casefold().strip()))
    label, children = tree
    label_aliases = {
        "WEEK_CLF": "CLF",
        "PART_CLF": "CLF",
        "CONTENT_N": "N",
        "REQUIREMENT_N": "N",
        "DEADLINE_N": "N",
        "DAY_N": "N",
        "ROOM_N": "N",
        "HOUR_N": "N",
    }
    label = label_aliases.get(label, label)
    if not children:
        return "({})".format(label)
    return "({} {})".format(label, " ".join(_format_tree(child) for child in children))


def _find_nodes(tree: Tree, label: str) -> List[Tuple[str, Tuple[Tree, ...]]]:
    found: List[Tuple[str, Tuple[Tree, ...]]] = []
    if not isinstance(tree, str):
        if tree[0] == label:
            found.append(tree)
        for child in tree[1]:
            found.extend(_find_nodes(child, label))
    return found


def _leaves(tree: Tree) -> List[str]:
    if isinstance(tree, str):
        return [tree]
    result: List[str] = []
    for child in tree[1]:
        result.extend(_leaves(child))
    return result


def _first_value(tree: Tree, label: str) -> Optional[str]:
    nodes = _find_nodes(tree, label)
    if not nodes:
        return None
    value = " ".join(_leaves(nodes[0])).strip()
    return value or None


def _repair_mojibake(value: str) -> str:
    """Decode legacy UTF-8 text that was read as Windows-1252/Latin-1."""
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def _ascii_fold(value: str) -> str:
    value = unicodedata.normalize("NFD", value)
    folded = "".join(ch for ch in value if not unicodedata.combining(ch)).casefold()
    return folded.replace("đ", "d")


def _semantic_value(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    normalized = re.sub(r"[^\w]+", "_", str(value), flags=re.UNICODE).strip("_")
    return normalized.upper()


def _topic_entity(value: str) -> str:
    folded = re.sub(r"[\W_]+", " ", _ascii_fold(_repair_mojibake(value))).strip()
    if folded == "cfg" or "context free grammar" in folded or "van pham phi ngu canh" in folded:
        return "CFG"
    if folded == "parsing" or "phan tich cu phap" in folded:
        return "PARSING"
    if folded == "ner" or "nhan dien thuc the" in folded:
        return "NER"
    if folded == "pos tagging" or "gan nhan tu loai" in folded:
        return "POS_TAGGING"
    return re.sub(r"\s+", "_", value.strip().upper())


def _interpret_legacy(tree: Tree) -> Tuple[str, str, Dict[str, Any]]:
    category = None
    if not isinstance(tree, str):
        category = next(
            (
                child[0]
                for child in tree[1]
                if not isinstance(child, str) and child[0] in INTENTS
            ),
            None,
        )
    intent = INTENTS.get(category, "OUT_OF_SCOPE")
    if intent == "OUT_OF_SCOPE":
        return "UNKNOWN()", intent, {}

    entities: Dict[str, Any] = {}
    if category in ("Q_COURSE_INFO", "VP_Credit"):
        course = _first_value(tree, "COURSE_SUBJECT") or _first_value(tree, "CourseName") or "NLP"
        if course.casefold() in ("nlp", "co3085", "xử lý ngôn ngữ tự nhiên"):
            course = "NLP"
        entities["course"] = course
        semantic = "GET_CREDIT(course={})".format(_semantic_value(course))
    elif category in ("Q_TOPIC", "VP_Topic"):
        week_value = (
            _first_value(tree, "WEEK_SUBJECT")
            or _first_value(tree, "NP_Time")
            or _first_value(tree, "N_Week")
            or ""
        )
        match = re.search(r"\d+", week_value)
        if match:
            entities["week"] = int(match.group(0))
        entities["topic"] = "course_content"
        semantic = "GET_TOPIC(week={}, topic=COURSE_CONTENT)".format(
            entities.get("week", "UNKNOWN")
        )
    elif category in ("Q_SCHEDULE", "VP_Schedule"):
        topic = _first_value(tree, "TOPIC") or _first_value(tree, "TopicName") or ""
        entities["topic"] = topic
        semantic = "GET_SCHEDULE(topic={})".format(_semantic_value(topic))
    elif category in ("Q_ASSIGNMENT", "VP_Req", "VP_Todo"):
        if category == "VP_Req" or (
            category == "Q_ASSIGNMENT" and _find_nodes(tree, "ASSIGNMENT_SUBJECT")
        ):
            entities["assignment"] = "PROJECT"
            entities["detail"] = "requirements"
        else:
            entities["assignment"] = "ALL"
            entities["detail"] = "list"
        semantic = "GET_ASSIGNMENT(assignment={}, detail={})".format(
            _semantic_value(entities["assignment"]), _semantic_value(entities["detail"])
        )
    elif category in ("Q_DEADLINE", "VP_Time"):
        entities["assignment"] = "PROJECT"
        semantic = "GET_DEADLINE(assignment=PROJECT)"
    elif category in ("Q_RESOURCE", "VP_Res"):
        topic = (
            _first_value(tree, "RESOURCE_TOPIC_NAME")
            or _first_value(tree, "TOPIC")
            or _first_value(tree, "TopicName")
            or ""
        ).rstrip("?.!,;:")
        entities["topic"] = topic
        semantic = "GET_RESOURCE(topic={})".format(_semantic_value(topic))
    else:  # Q_RULE
        entities["assignment"] = "PROJECT"
        entities["topic"] = "AI_TOOL_USAGE"
        semantic = "GET_RULE(assignment=PROJECT, topic=AI_TOOL_USAGE)"

    return semantic, intent, entities


def _interpret(tree: Tree) -> Tuple[str, str, Dict[str, Any]]:
    category = next((c[0] for c in tree[1] if not isinstance(c, str) and c[0] in INTENTS), None) if not isinstance(tree, str) else None
    intent = INTENTS.get(category)
    if intent is None:
        return "UNKNOWN()", "OUT_OF_SCOPE", {}
    leaves = _repair_mojibake(" ".join(_leaves(tree))).casefold()
    entities: Dict[str, Any] = {}
    def assignment() -> str:
        match = re.search(r"(?:bai\s*tap|hw)\s*(?:so\s*)?([123])\b", _ascii_fold(leaves), re.I)
        return "HW{}".format(match.group(1)) if match else "PROJECT"
    if category in ("INFO_Q", "INSTRUCTOR_Q"):
        instructor = category == "INSTRUCTOR_Q" or "giang vien" in _ascii_fold(leaves) or "ai day" in _ascii_fold(leaves)
        entities.update(course="NLP", attribute="instructor" if instructor else "credit")
        semantic = "GET_INSTRUCTOR(course=NLP)" if instructor else "GET_CREDIT(course=NLP)"
    elif category in ("TOPIC_Q", "TOPIC_YN_Q"):
        number = _first_value(tree, "NUM")
        if number is not None: entities["week"] = int(number)
        elif _find_nodes(tree, "WEEK_CLF") and _first_value(tree, "DEIXIS"): entities["week"] = "@CURRENT_WEEK"
        elif _first_value(tree, "REL"):
            entities["week"] = "@PREV_WEEK" if "truoc" in _ascii_fold(_first_value(tree, "REL") or "") else "@NEXT_WEEK"
        elif _first_value(tree, "DEIXIS"): entities["week"] = "@CURRENT_WEEK"
        topic = _repair_mojibake(_first_value(tree, "TOPIC") or "") or None
        if topic: entities["topic"] = topic.upper().replace(" ", "_")
        if _find_nodes(tree, "PART") or category == "TOPIC_YN_Q":
            entities["question_type"] = "yesno"
            semantic = "GET_TOPIC(week={}, topic={}, yesno=TRUE)".format(entities.get("week", "UNKNOWN"), entities.get("topic", "UNKNOWN"))
        else: semantic = "GET_TOPIC(week={})".format(entities.get("week", "UNKNOWN"))
    elif category == "SCHED_Q":
        topic = _repair_mojibake(_first_value(tree, "TOPIC_LIST") or _first_value(tree, "TOPIC") or "") or None
        if _first_value(tree, "DEIXIS"):
            deixis = _ascii_fold(_first_value(tree, "DEIXIS") or "")
            context = "@CONTEXT(phần đó)" if deixis == "do" else "@CONTEXT(phần này)"
            entities["topic"] = context
            semantic = "GET_SCHEDULE(topic=@CONTEXT)"
        elif topic:
            if _find_nodes(tree, "TOPIC_LIST"):
                vals = []
                for x in _leaves(_find_nodes(tree, "TOPIC_LIST")[0]):
                    if not isinstance(x, str) or _ascii_fold(_repair_mojibake(x)) == "va":
                        continue
                    vals.append(_topic_entity(x))
                val = "[{}]".format(",".join(vals))
            else:
                val = _topic_entity(topic)
            entities["topic"] = val; semantic = "GET_SCHEDULE(topic={})".format(val)
        else:
            attribute = "room" if _find_nodes(tree, "WH_ROOM") else ("time" if _find_nodes(tree, "WH_TIME") else "day")
            entities.update(course="NLP", attribute=attribute)
            semantic = "GET_SCHEDULE(course=NLP, attribute={})".format(attribute.upper())
    elif category in ("ASSIGN_Q", "GROUP_SIZE_Q"):
        if category == "GROUP_SIZE_Q" or "nhom" in _ascii_fold(leaves):
            entities.update(assignment="PROJECT", attribute="group_size"); semantic = "GET_ASSIGNMENT(assignment=PROJECT, attribute=GROUP_SIZE)"
        elif _find_nodes(tree, "NP_WEEK") or _find_nodes(tree, "WEEK_CLF"):
            number = _first_value(tree, "NUM"); week = int(number) if number is not None else "@CURRENT_WEEK"
            entities["week"] = week; semantic = "GET_ASSIGNMENT(week={})".format(week)
        elif _find_nodes(tree, "NP_USER"):
            entities.update(user="ME", filter="PENDING"); semantic = "GET_ASSIGNMENT(scope=PENDING)"
        else:
            a = assignment(); entities.update(assignment=a, attribute="requirement")
            semantic = "GET_ASSIGNMENT(assignment={}, attribute=REQUIREMENT)".format(a)
    elif category == "DEADLINE_Q":
        a = assignment(); entities["assignment"] = a; semantic = "GET_DEADLINE(assignment={})".format(a)
    elif category in ("RESOURCE_Q", "TEXTBOOK_Q", "REFERENCE_Q"):
        number = _first_value(tree, "NUM")
        if number is not None or (_first_value(tree, "DEIXIS") and _find_nodes(tree, "WEEK_CLF")):
            week = int(number) if number is not None else "@CURRENT_WEEK"; entities["week"] = week
            semantic = "GET_RESOURCE(week={})".format(week)
        elif category == "TEXTBOOK_Q" or "giao trinh" in _ascii_fold(leaves):
            entities.update(course="NLP", type="textbook"); semantic = "GET_RESOURCE(course=NLP, type=TEXTBOOK)"
        elif category == "REFERENCE_Q" or "tham khao" in _ascii_fold(leaves):
            entities.update(course="NLP", type="reference"); semantic = "GET_RESOURCE(course=NLP, type=REFERENCE)"
        elif "nay" in _ascii_fold(leaves) or "do" in _ascii_fold(leaves):
            entities["topic"] = "@CONTEXT(phần này)" if "nay" in _ascii_fold(leaves) else "@CONTEXT(phần đó)"
            semantic = "GET_RESOURCE(topic=@CONTEXT)"
        else:
            topic = _topic_entity(_first_value(tree, "TOPIC") or "CFG")
            entities["topic"] = topic; semantic = "GET_RESOURCE(topic={})".format(topic)
    else:
        a = assignment()
        if category == "ATTENDANCE_Q" or "diem danh" in _ascii_fold(leaves) or "di hoc" in _ascii_fold(leaves) or "vang" in _ascii_fold(leaves):
            entities.update(course="NLP", rule="attendance"); semantic = "GET_RULE(course=NLP, rule=ATTENDANCE)"
        elif category == "LATE_Q" or "tre" in _ascii_fold(leaves) or "muon" in _ascii_fold(leaves):
            entities.update(assignment=a, rule="late_submission"); semantic = "GET_RULE(assignment={}, rule=LATE_SUBMISSION)".format(a)
        else:
            entities.update(assignment=a, rule="ai_usage")
            tool = _first_value(tree, "TOOL")
            if tool and _ascii_fold(tool) != "ai":
                tool = tool.upper()
                entities["tool"] = tool
                semantic = "GET_RULE(assignment={}, rule=AI_USAGE, tool={})".format(a, tool)
            else:
                semantic = "GET_RULE(assignment={}, rule=AI_USAGE)".format(a)
    return semantic, intent, entities


def _analyze(sentence: str, rules: RuleMap) -> Dict[str, Any]:
    sentence = re.sub(r"\s+", " ", sentence).strip()
    tree = _earley_parse(sentence, rules)
    if tree is not None:
        category = next(
            (child[0] for child in tree[1] if not isinstance(child, str)),
            None,
        ) if not isinstance(tree, str) else None
        assignment_name = _first_value(tree, "ASSIGN") or ""
        if (
            category == "ASSIGN_Q"
            and _ascii_fold(assignment_name) == "bai tap"
            and not _find_nodes(tree, "NUM")
            and not _find_nodes(tree, "NP_WEEK")
        ):
            tree = None
    if tree is None:
        return {
            "sentence": sentence,
            "is_valid": False,
            "parse_tree": "()",
            "semantic": "UNKNOWN()",
            "intent": "OUT_OF_SCOPE",
            "entities": {},
        }

    semantic, intent, entities = _interpret(tree)
    return {
        "sentence": sentence,
        "is_valid": True,
        "parse_tree": _format_tree(tree),
        "semantic": semantic,
        "intent": intent,
        "entities": entities,
    }


def _load_rules(grammar_path: Optional[str] = None, data_dir: Optional[str] = None) -> RuleMap:
    grammar_text, _ = load_grammar_text(grammar_path=grammar_path, data_dir=data_dir)
    return parse_grammar(grammar_text)


def analyze_sentence(sentence: str) -> Dict[str, Any]:
    """Analyze one sentence using the course CFG found in Docker or local paths."""
    return _analyze(sentence, _load_rules())


def process_sentences(
    grammar_path: Optional[str] = None,
    input_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    paths = resolve_runtime_paths(input_dir=input_dir, output_dir=output_dir, data_dir=data_dir)
    input_path = paths["input"] / "sentences.txt"
    if not input_path.is_file():
        raise FileNotFoundError("Sentence input not found: {}".format(input_path))

    grammar_text, _ = load_grammar_text(grammar_path=grammar_path, data_dir=data_dir)
    rules = parse_grammar(grammar_text)
    sentences = input_path.read_text(encoding="utf-8-sig").splitlines()
    results = [_analyze(sentence, rules) for sentence in sentences]

    output_path = paths["output"]
    output_path.mkdir(parents=True, exist_ok=True)
    parse_output = output_path / "parse-results.txt"
    semantic_output = output_path / "semantic.txt"
    intent_output = output_path / "intent-entity.txt"

    parse_output.write_text(
        "\n".join(result["parse_tree"] for result in results) + ("\n" if results else ""),
        encoding="utf-8",
    )
    semantic_output.write_text(
        "\n".join(result["semantic"] if result["is_valid"] else "()" for result in results)
        + ("\n" if results else ""),
        encoding="utf-8",
    )
    intent_output.write_text(
        "\n".join(
            "INTENT: {}; ENTITIES: {}".format(
                result["intent"] if result["intent"] != "OUT_OF_SCOPE" else "UNKNOWN",
                _format_entities(result["entities"]),
            )
            for result in results
        ) + ("\n" if results else ""),
        encoding="utf-8",
    )
    return {
        "results": results,
        "parse_output": parse_output,
        "semantic_output": semantic_output,
        "intent_output": intent_output,
        "valid_count": sum(1 for result in results if result["is_valid"]),
    }


def _format_entities(entities: Dict[str, Any]) -> str:
    if not entities:
        return "-"
    fields: List[str] = []
    for key, value in entities.items():
        if key == "topic" and isinstance(value, str) and value.startswith("[") and value.endswith("]"):
            fields.extend(
                "topic={}".format(topic.strip())
                for topic in value[1:-1].split(",")
            )
        else:
            fields.append("{}={}".format(key, value))
    return ", ".join(fields)


def run(**kwargs: Any) -> Dict[str, Any]:
    """Convenience entry point for the assignment pipeline."""
    return process_sentences(
        grammar_path=kwargs.get("grammar_path"),
        input_dir=kwargs.get("input_dir"),
        output_dir=kwargs.get("output_dir"),
        data_dir=kwargs.get("data_dir"),
    )
