"""Generic CFG parser with lexical leaves serialized in the assignment format."""
from functools import lru_cache

from course_assistant.nlp.grammar import load_grammar, normalize


def _serialize(node):
    label, children = node
    if isinstance(children, str):
        return f"({label} {children})"
    return f"({label} {' '.join(_serialize(child) for child in children)})"


def _valid_tree(node):
    """Reject parses whose lexical heads conflict with their CFG category."""
    label, children = node
    if isinstance(children, str):
        return True
    leaves = [child for child in children if isinstance(child[1], str)]
    direct = {child[0]: child[1] for child in leaves}
    values_by_tag = {}
    for tag, value in leaves:
        values_by_tag.setdefault(tag, set()).add(value)
    if label == "NP_WEEK" and direct.get("CLF") not in {"tuần", "week"}:
        return False
    if label == "NP_CHAP" and direct.get("CLF") not in {"chương", "chapter"}:
        return False
    if label == "NP_TOPIC" and direct.get("CLF") in {"tuần", "week", "chương", "chapter"}:
        return False
    if label == "NP_TOPIC" and direct.get("CLF") == "phần" and direct.get("TOPIC") in {
        "syntactic_processing", "semantic_interpretation",
        "context_and_world_knowledge",
    }:
        return False
    if label == "NP_APART" and direct.get("CLF") in {"tuần", "chương", "week", "chapter"}:
        return False
    if label == "NP_CPART" and direct.get("CLF") in {"chương", "chapter"} and "ROMAN" in direct:
        return False
    if label == "WH_SEM" and direct.get("N") not in {"học_kỳ", "học_kì"}:
        return False
    if label == "WH_DAY" and direct.get("N") != "thứ":
        return False
    if label == "WH_ROOM" and direct.get("N") != "phòng":
        return False
    if label == "WH_CHAP" and direct.get("CLF") == "tuần":
        return False
    if label == "WH_WEEK" and direct.get("CLF") in {"chương", "chapter"}:
        return False
    if label == "WH_DATE" and direct.get("N") != "ngày":
        return False
    if label == "DEADLINE_Q" and direct.get("N") in {"tuần", "chương"}:
        if "TOPIC" in direct:
            return False
    child_labels = {child[0] for child in children}
    nouns = {value for tag, value in direct.items() if tag == "N"}
    if label == "TOPIC_Q":
        if "NP_COURSE" in child_labels and nouns & {"phần", "phần_chính", "lo", "chuẩn_đầu_ra"}:
            return False
        if "NP_COURSE" in child_labels and nouns & {"giáo_trình", "quy_định"}:
            return False
        if "NP_WEEK" in child_labels and "WH_WEEK" in child_labels:
            return False
        if "N" in direct and direct["N"] == "tuần":
            return False
        if direct.get("V") == "nộp" and "NP_TOPIC" in child_labels:
            return False
    if label == "SCHED_Q" and "NP_WEEK" in child_labels:
        if direct.get("N") == "chương" and direct.get("WH") == "mấy":
            return False
    if label == "RESOURCE_Q":
        if direct.get("N") in {
            "lo", "chuẩn_đầu_ra", "deadline", "hạn_nộp", "tên", "yêu_cầu",
            "sinh_viên", "quy_định",
        }:
            return False
    if label == "RULE_Q" and direct.get("PART") == "phải_không":
        if "không" in values_by_tag.get("V", set()):
            return False
    if label == "ASSIGN_Q" and direct.get("V") == "nộp" and direct.get("WH") == "khi_nào":
        return False
    if label == "LO_Q" and direct.get("N") == "sinh_viên":
        return False
    if label == "LO_Q" and direct.get("N") == "quy_định":
        return False
    if label == "TOPIC_Q" and "NP_CPART" in child_labels:
        cparts = [child for child in children if child[0] == "NP_CPART"]
        if any(any(grandchild[0] == "ROMAN" for grandchild in part[1])
               for part in cparts if not isinstance(part[1], str)):
            return False
    if label == "S":
        root_child = children[0] if children else None
        if root_child and root_child[0] in {"INFO_Q", "RESOURCE_Q"}:
            if any(
                child[0] == "N" and child[1] in {"lo", "chuẩn_đầu_ra"}
                for child in root_child[1]
                if isinstance(child, tuple) and isinstance(child[1], str)
            ):
                return False
        if "NP_COURSE" in child_labels and nouns & {"phần", "phần_chính"}:
            return False
        if "NP_COURSE" in child_labels and nouns & {"lo", "chuẩn_đầu_ra"}:
            return False
    if label == "INFO_Q" and "NP_COURSE" in child_labels and nouns & {"lo", "chuẩn_đầu_ra"}:
        return False
    if label == "INFO_Q" and "NP_COURSE" in child_labels and nouns & {
        "giáo_trình", "quy_định", "sinh_viên"
    }:
        return False
    if label == "ASSIGN_Q" and "môn" in values_by_tag.get("N", set()):
        return False
    if label == "LO_Q" and "NP_COURSE" in child_labels and direct.get("N") == "chương":
        return False
    # Resolve common lexical ambiguities with the most specific constituent.
    if label == "INFO_Q" and "NP_COURSE" in child_labels and nouns & {
        "lo", "chu\u1ea9n_\u0111\u1ea7u_ra"
    }:
        return False
    if label == "TOPIC_Q" and "NP_COURSE" in child_labels and nouns & {
        "ph\u1ea7n", "ph\u1ea7n_ch\u00ednh", "lo", "chu\u1ea9n_\u0111\u1ea7u_ra"
    }:
        return False
    if label == "SCHED_Q" and "NP_WEEK" in child_labels:
        if direct.get("N") == "ch\u01b0\u01a1ng" and direct.get("WH") == "m\u1ea5y":
            return False
    if label == "ASSIGN_Q" and direct.get("N") in {
        "deadline", "h\u1ea1n_n\u1ed9p"
    }:
        return False
    if label == "S" and children:
        root = children[0]
        if root[0] == "RESOURCE_Q":
            root_leaves = {
                child[0]: child[1] for child in root[1]
                if isinstance(child, tuple) and isinstance(child[1], str)
            }
            if root_leaves.get("N") in {
                "lo", "chu\u1ea9n_\u0111\u1ea7u_ra", "ph\u1ea7n", "ch\u01b0\u01a1ng"
            }:
                return False
        if root[0] == "INFO_Q":
            root_leaves = {
                child[0]: child[1] for child in root[1]
                if isinstance(child, tuple) and isinstance(child[1], str)
            }
            if "EXAM" in root_leaves and root_leaves.get("WH") == "khi_n\u00e0o":
                return False
        if root[0] == "RULE_Q":
            for child in root[1]:
                if child[0] == "NP_TOOL" and isinstance(child[1], tuple):
                    if any(grandchild[0] == "TOOL" and grandchild[1] == "llm/rag"
                           for grandchild in child[1]):
                        return False
        if root[0] == "INFO_Q":
            direct_root = {
                child[0]: child[1] for child in root[1]
                if isinstance(child, tuple) and isinstance(child[1], str)
            }
            if direct_root.get("N") in {"điểm", "sinh_viên"} and "EXAM" in direct_root or direct_root.get("N") == "sinh_viên":
                return False
        if root[0] == "RESOURCE_Q" and any(
            isinstance(child, tuple) and child[0] == "N"
            and child[1] in {"lo", "chu\u1ea9n_\u0111\u1ea7u_ra"}
            for child in root[1]
        ):
            return False
        if root[0] == "INFO_Q":
            course_np = next(
                (child for child in root[1]
                 if isinstance(child, tuple) and child[0] == "NP_COURSE"),
                None,
            )
            if course_np and not any(
                isinstance(child, tuple) and child[0] == "COURSE"
                for child in course_np[1]
            ) and not any(
                isinstance(child, tuple) and child == ("CLF", "môn_học")
                for child in course_np[1]
            ):
                return False
    if label == "NP_CPART" and direct.get("CLF") in {
        "ch\u01b0\u01a1ng", "chapter", "part"
    } and "ROMAN" in direct:
        return False
    if label == "SCHED_Q" and "NP_ASSIGN" in child_labels and direct.get("V") == "n\u1ed9p":
        return False
    if label == "SCHED_Q" and "EXAM" in direct and direct.get("V") == "n\u1ed9p":
        return False
    if label == "ASSIGN_Q" and "N" in direct and direct["N"] in {
        "deadline", "h\u1ea1n_n\u1ed9p"
    }:
        return False
    return all(_valid_tree(child) for child in children if isinstance(child, tuple))


def parse_sentence(sentence: str):
    grammar = load_grammar()
    text = normalize(sentence)
    if not text:
        return "()"

    @lru_cache(maxsize=None)
    def parse_symbol(symbol, position, active=()):
        key = (symbol, position)
        if key in active:
            return ()
        next_active = active + (key,)
        results = []
        for alternative in grammar.productions.get(symbol, ()):
            # Lexical productions have one quoted terminal. Underscores in the
            # canonical terminal correspond to spaces in the surface question.
            if len(alternative) == 1 and alternative[0].startswith("'"):
                terminal = alternative[0][1:-1].replace("\\'", "'")
                phrase = normalize(terminal.replace("_", " "))
                cursor = position
                while cursor < len(text) and text[cursor].isspace():
                    cursor += 1
                if text.startswith(phrase, cursor):
                    end = cursor + len(phrase)
                    if end == len(text) or not text[end].isalnum():
                        results.append((end, (symbol, terminal)))
                continue

            states = [(position, ())]
            for child_symbol in alternative:
                next_states = []
                for cursor, children in states:
                    for end, child in parse_symbol(child_symbol, cursor, next_active):
                        next_states.append((end, children + (child,)))
                states = next_states[:128]
                if not states:
                    break
            for end, children in states:
                results.append((end, (symbol, children)))
        return tuple(results[:256])

    for end, tree in parse_symbol(grammar.start, 0):
        cursor = end
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor == len(text) and _valid_tree(tree):
            return _serialize(tree)
    return "()"
