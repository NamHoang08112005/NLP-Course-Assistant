"""Rule-based semantic slots for the domain grammar's question families."""
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from course_assistant.contracts import SemanticResult
from course_assistant.nlp.parser import parse_sentence
from course_assistant.nlp.grammar import load_grammar, normalize

def _lexicon():
    result={}
    for alias, entries in (load_grammar().lexicon or {}).items():
        for tag, _value in entries:
            section={"TOPIC":"TOPICS","COURSE":"COURSE","LO":"LO"}.get(tag,tag)
            result.setdefault(section,[]).append(alias)
    return result

LEX=_lexicon()
def _has(q,*phrases): return any(p in q for p in phrases)
def _id(text):
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"[^A-Z0-9]+", "_", plain.upper()).strip("_")


@lru_cache(maxsize=1)
def _entity_aliases():
    path = Path(__file__).resolve().parents[3] / "data" / "lexicon" / "entities.txt"
    section = ""
    aliases = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("="):
            continue
        if " = " not in line:
            section = line
            continue
        name, value = line.split(" = ", 1)
        aliases.setdefault(section, []).append((name, value))
    return aliases


def _entity_id(text, section="TOPICS"):
    folded = normalize(text).replace("_", " ")
    if section == "USAGE":
        usage_ids = {
            "statistical nlp": "STATISTICAL_NLP",
            "python nlp": "PYTHON_NLP",
            "d\u1ecbch m\u00e1y": "MACHINE_TRANSLATION",
            "tri th\u1ee9c th\u1ebf gi\u1edbi": "WORLD_KNOWLEDGE",
            "nlp ti\u1ebfng vi\u1ec7t": "VIETNAMESE_NLP",
            "n\u1ec1n t\u1ea3ng nlp": "FOUNDATIONAL_NLP",
            "nlp t\u1ed5ng qu\u00e1t": "BROAD_NLP",
        }
        return usage_ids.get(folded, _id(text))
    for alias, entries in (load_grammar().lexicon or {}).items():
        if normalize(alias).replace("_", " ") == folded:
            if any(tag == "SEM_TOPIC" for tag, _value in entries):
                semantic_ids = {
                    "các mức phân tích ngôn ngữ": "LEVELS_OF_LANGUAGE_ANALYSIS",
                    "biểu diễn và hiểu ngôn ngữ": "REPRESENTATION_AND_UNDERSTANDING",
                    "ứng dụng dialog-based": "DIALOG_BASED_APPLICATIONS",
                    "đồng tham chiếu": "ANAPHORA",
                    "quan hệ quy chiếu": "ANAPHORA",
                    "phân tích cú pháp": "PARSING",
                    "nghiên cứu ngôn ngữ tự nhiên": "STUDY_OF_NATURAL_LANGUAGE",
                    "ứng dụng text-based": "TEXT_BASED_APPLICATIONS",
                    "đánh giá hệ thống hiểu ngôn ngữ tự nhiên": "EVALUATING_NLU_SYSTEMS",
                    "tổ chức hệ thống nlu": "ORGANIZATION_OF_NLU_SYSTEMS",
                    "part-of-speech tagging": "POS_TAGGING",
                }
                return semantic_ids.get(folded, _id(text))
    entries = _entity_aliases().get(section, ())
    for name, value in entries:
        if folded == normalize(name) or folded == normalize(value):
            return _id(name)
    # Topic leaves sometimes use a plural surface form while the entity lexicon
    # stores the canonical singular name.
    singular = re.sub(r"\b([a-z]+)s\b", r"\1", folded)
    for name, value in entries:
        if singular == normalize(name) or singular == normalize(value):
            return _id(name)
    return _id(text)
def _find_alias(q,section):
    aliases=sorted(LEX.get(section,()),key=len,reverse=True)
    normalized_query = normalize(q).replace("_", " ")
    for alias in aliases:
        normalized_alias = normalize(alias).replace("_", " ")
        if normalized_alias in normalized_query: return alias
    return None


def _fold(text):
    """Fold accents and punctuation so catalog aliases match user spelling."""
    text = normalize(text).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _contains(text, *phrases):
    folded_text = f" {_fold(text)} "
    return any(
        bool(folded := _fold(phrase)) and f" {folded} " in folded_text
        for phrase in phrases
    )


def _code(prefix, digits):
    number = digits.lstrip("0") or "0"
    return f"{prefix}{number.zfill(2)}"


@lru_cache(maxsize=1)
def _resource_catalog():
    path = Path(__file__).resolve().parents[3] / "data" / "course" / "resources.txt"
    catalog = {}
    current = None
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        match = re.fullmatch(r"(TEXTBOOK|REFERENCE)\s+(\d+)", line, re.I)
        if match:
            current = f"{match.group(1).upper()}_{match.group(2)}"
            catalog[current] = {}
            continue
        field = re.match(r"([a-z_]+):\s*(.*)", line, re.I)
        if current and field:
            catalog[current][field.group(1).casefold()] = field.group(2).strip()
    return catalog


def _resource_title(q):
    """Return the best catalog title match, allowing short distinctive names."""
    query = set(_fold(q).split())
    candidates = []
    generic = {
        "a", "an", "and", "by", "course", "from", "lecture", "lectures",
        "of", "slide", "slides", "the", "to", "with",
    }
    for resource, fields in _resource_catalog().items():
        title = fields.get("title", "")
        if not title:
            continue
        title = re.split(r"\bby\b", title, maxsplit=1, flags=re.I)[0]
        title_words = set(_fold(title).split())
        for author_field in (fields.get("author", ""), fields.get("authors", "")):
            for author in author_field.split(";"):
                title_words -= set(_fold(author).split())
        title_words -= generic
        if len(title_words) < 2:
            continue
        overlap = len(query & title_words)
        ratio = overlap / len(title_words)
        if ratio >= 0.8:
            candidates.append((ratio, overlap, resource))
    return max(candidates, default=(0, 0, None))[2]


def _author_ids(q):
    folded_query = _fold(q)
    query = set(folded_query.split())
    found = []
    for fields in _resource_catalog().values():
        authors = fields.get("authors", fields.get("author", ""))
        for full_name in authors.split(";"):
            name_parts = _fold(full_name).split()
            if not name_parts:
                continue
            last_name = name_parts[-1]
            full_name = " ".join(name_parts)
            if last_name in query:
                canonical = (
                    _id(full_name)
                    if len(name_parts) >= 3 and full_name in folded_query
                    else _id(last_name)
                )
                position = folded_query.find(full_name if full_name in folded_query else last_name)
                found.append((position, canonical))
    ordered = []
    for _, canonical in sorted(found):
        if canonical not in ordered:
            ordered.append(canonical)
    return ordered


def _find_aliases(q, section):
    """Return matching aliases in surface order, without duplicate spans."""
    query = _fold(q)
    matches = []
    for alias in LEX.get(section, ()):
        folded = _fold(alias)
        if not folded:
            continue
        for match in re.finditer(rf"(?<![a-z0-9]){re.escape(folded)}(?![a-z0-9])", query):
            matches.append((match.start(), match.end(), alias))
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    selected = []
    for start, end, alias in matches:
        if any(start < old_end and old_start < end for old_start, old_end, _ in selected):
            continue
        selected.append((start, end, alias))
    return [alias for _, _, alias in selected]


def _ambiguous_part(tree_leaves, q):
    leaves = dict(tree_leaves)
    if not _contains(q, "là gì") or _contains(q, "bài tập lớn", "btl"):
        return None

    topic = leaves.get("TOPIC")
    assignment_parts = {
        "hỏi_đáp": "PART_II",
        "question_answering": "PART_II",
        "qa": "PART_II",
        "semantic_interpretation": "PART_II",
        "semantic_interpretation_and_qa": "PART_II",
        "local_discourse_context": "PART_III",
        "dialogue": "PART_III",
        "hội_thoại": "PART_III",
    }
    if topic in assignment_parts and leaves.get("CLF") == "phần":
        topic_id = _entity_id(topic)
        part_id = assignment_parts[topic]
        return {
            "action": "GET_PART",
            "intent": "AMBIGUOUS",
            "entities": {"part": f"@AMBIGUOUS(TOPIC_{topic_id}|{part_id})"},
        }

    course_part_ids = {
        "syntactic_processing": ("PART_I", "COURSE_PART_I"),
        "semantic_interpretation": ("PART_II", "COURSE_PART_II"),
        "context_and_world_knowledge": ("PART_III", "COURSE_PART_III"),
    }
    course_part = leaves.get("CPART")
    if course_part in course_part_ids and leaves.get("CLF") == "phần":
        part_id, course_id = course_part_ids[course_part]
        return {
            "action": "GET_PART",
            "intent": "AMBIGUOUS",
            "entities": {"part": f"@AMBIGUOUS({part_id}|{course_id})"},
        }

    roman = leaves.get("ROMAN")
    if roman and roman.upper() in {"I", "II", "III"} and leaves.get("CLF") == "part":
        part_id = "PART_" + roman.upper()
        course_id = "COURSE_PART_" + roman.upper()
        return {
            "action": "GET_PART",
            "intent": "AMBIGUOUS",
            "entities": {"part": f"@AMBIGUOUS({part_id}|{course_id})"},
        }
    return None


def _resource_semantics(q, tree_leaves, course, week, chapter):
    if _contains(q, "mở tài liệu", "được mở tài liệu", "hình thức thi", "open book"):
        return None
    folded = _fold(q)
    resource = _resource_title(q)
    author_ids = _author_ids(q)
    explicit_id = re.search(r"\b(reference|textbook)\s*(\d+)\b", folded)
    resource_words = (
        "tài liệu", "giáo trình", "sách", "slide", "bài giảng", "tài nguyên",
        "tham khảo", "textbook", "cuốn", "tác giả", "nhà xuất bản",
    )
    has_resource_cue = any(_contains(q, word) for word in resource_words)
    if course and _contains(q, "môn", "co3085") and not has_resource_cue:
        resource = None
    if not resource and not explicit_id and not has_resource_cue:
        return None

    entities = {}
    if explicit_id:
        entities["resource"] = f"{explicit_id.group(1).upper()}_{explicit_id.group(2)}"
    elif resource:
        entities["resource"] = resource

    if not resource and not explicit_id and author_ids:
        entities["author"] = f"[{','.join(author_ids)}]" if len(author_ids) > 1 else author_ids[0]

    attribute = None
    if _contains(q, "không có tác giả", "chưa có tác giả"):
        attribute = "no_author"
    elif _contains(q, "tác giả", "ai viết", "ai là đồng tác giả", "do ai viết", "ai là tác giả", "của ai"):
        attribute = "author" if resource or explicit_id else None
    elif _contains(q, "xuất bản năm nào", "xuất bản vào năm nào", "năm nào xuất bản"):
        attribute = "year"
    elif _contains(q, "nhà xuất bản nào", "do nhà xuất bản nào", "nhà xuất bản"):
        attribute = "publisher"
    elif _contains(q, "dùng để làm gì", "được dùng để làm gì", "công dụng"):
        attribute = "usage"
    elif _contains(q, "bao nhiêu giáo trình", "mấy giáo trình", "bao nhiêu sách"):
        attribute = "count"
        if course:
            entities = {"course": "CO3085", "type": "TEXTBOOK"}
    elif _contains(q, "nên đọc thêm", "hiểu sâu", "study note"):
        entities = {"course": "CO3085"}
        attribute = "study_note"

    if attribute is None and not resource and not explicit_id:
        author_cue = _contains(q, "tác giả", "do", "viết cuốn nào")
        if _contains(q, "bài tập lớn", "btl", "btl01"):
            entities = {"assignment": "BTL01"}
        elif author_cue and author_ids:
            pass
        elif week and _contains(q, "bài giảng", "slide"):
            entities = {"week": _code("WEEK_", week.group(1)), "type": "LECTURE_SLIDES"}
        elif chapter:
            entities = {"chapter": _code("CH", chapter.group(1))}
        elif any(tag == "CPART" for tag, _ in tree_leaves):
            part = next(value for tag, value in tree_leaves if tag == "CPART")
            part_map = {
                "syntactic_processing": "COURSE_PART_I",
                "semantic_interpretation": "COURSE_PART_II",
                "context_and_world_knowledge": "COURSE_PART_III",
            }
            entities = {"course_part": part_map.get(part, _id(part))}
        else:
            usage = _find_alias(q, "USAGE")
            authors = _author_ids(q)
            topic_aliases = _find_aliases(q, "TOPICS")
            topic_ids = list(dict.fromkeys(_entity_id(alias) for alias in topic_aliases))
            year = re.search(r"\b(\d{4})\b", folded)
            publisher = "MIT_PRESS" if _contains(q, "mit press") else None
            if usage:
                entities = {"usage": _entity_id(usage, "USAGE")}
            elif topic_ids:
                entities = {"topic": topic_ids[0] if len(topic_ids) == 1 else topic_ids}
            elif authors:
                entities = {"author": f"[{','.join(authors)}]" if len(authors) > 1 else authors[0]}
            elif publisher:
                entities = {"publisher": publisher}
            elif year:
                entities = {"year": year.group(1)}
            elif _contains(q, "môn nlp", "môn học", "co3085"):
                entities = {"course": "CO3085"}
                if _contains(q, "tài liệu tham khảo", "reference"):
                    entities["type"] = "REFERENCE"
                elif _contains(q, "giáo trình", "textbook"):
                    entities["type"] = "TEXTBOOK"

    if attribute:
        entities["attribute"] = attribute
    if not entities and course:
        entities["course"] = "CO3085"
        if _contains(q, "tài liệu tham khảo", "reference"):
            entities["type"] = "REFERENCE"
        elif _contains(q, "giáo trình", "textbook"):
            entities["type"] = "TEXTBOOK"
    if resource and _contains(q, "tài liệu tham khảo", "reference") and not _contains(q, "reference "):
        entities["type"] = "REFERENCE"
    return {"action": "GET_RESOURCE", "intent": "GET_RESOURCE", "entities": entities}


def _rule_semantics(q, course, tree):
    rule_terms = {
        "EXTERNAL_LIBRARIES": ("thư viện bên ngoài", "thư viện công khai", "thư viện ngoài", "external libraries"),
        "ASSIGNMENT_SHARING": ("sao chép", "chia sẻ bài", "chia sẻ mã", "nhóm khác"),
        "SOURCE_CODE": ("mã nguồn", "source code"),
        "ACADEMIC_INTEGRITY": ("liêm chính học thuật", "code of ethics", "đạo văn"),
        "ATTENDANCE": ("điểm danh", "chuyên cần", "tham dự đầy đủ"),
        "AI_USAGE": ("trí tuệ nhân tạo", "chatgpt"),
        "LLM_RAG": ("llm", "rag"),
        "OUT_OF_SCOPE": ("ngoài phạm vi", "không tìm thấy câu trả lời", "không có câu trả lời"),
        "REFERENCES": ("tài liệu tham khảo",),
    }
    matched_rule = next(
        (rule for rule, terms in rule_terms.items() if any(_contains(q, term) for term in terms)),
        None,
    )
    if matched_rule is None and _contains(q, "ai") and (
        _contains(q, "dùng ai", "sử dụng ai", "khai báo việc dùng ai", "công cụ ai")
        or _contains(q, "quy định")
    ):
        matched_rule = "AI_USAGE"
    if matched_rule == "REFERENCES" and not _contains(q, "quy định"):
        matched_rule = None
    explicit_rule = _contains(q, "quy định")
    if matched_rule is None and not explicit_rule:
        return None
    if "ASSIGN_Q" in tree and not explicit_rule:
        return None

    policy_cues = (
        "quy định", "được phép", "có được", "có thể dùng", "có thể sử dụng", "phải",
        "có cần", "cần tuân thủ", "cần khai báo", "cần giải thích", "cần hiểu",
        "yêu cầu", "tuân thủ", "được sử dụng", "làm gì",
    )
    has_policy_cue = any(_contains(q, cue) for cue in policy_cues)
    if not explicit_rule and not has_policy_cue:
        return None

    if _contains(q, "những quy định nào", "các quy định nào"):
        matched_rule = "ALL"
    elif matched_rule is None and explicit_rule:
        matched_rule = "SUBMISSION" if _contains(q, "nộp") else "UNKNOWN"
    assignment = _contains(q, "bài tập lớn", "btl", "btl01")
    entities = {}
    if assignment:
        entities["assignment"] = "BTL01"
    elif course:
        entities["course"] = "CO3085"
    if matched_rule:
        entities["rule"] = matched_rule
    if _contains(q, "chatgpt"):
        entities["tool"] = "CHATGPT"
    if matched_rule == "LLM_RAG" and _contains(q, "mô tả", "trình bày"):
        entities["attribute"] = "requirements_to_describe"
    return {"action": "GET_RULE", "intent": "GET_RULE", "entities": entities}


def _ambiguous_final(q):
    if (
        _contains(q, "final")
        and _contains(q, "khi nào", "bao giờ")
        and not _contains(q, "nộp", "deadline", "thi", "exam")
    ):
        return {
            "action": "GET_FINAL",
            "intent": "AMBIGUOUS",
            "entities": {"final": "@AMBIGUOUS(EXAM_FINAL|FINAL_SUBMISSION_AND_DEMO)"},
        }
    return None


def _out_of_scope_question(q):
    folded = _fold(q)
    words = folded.split()
    if re.search(r"[\u3400-\u9fff]", q):
        return True
    if not re.search(r"[a-z]{2,}", folded):
        return False
    if re.search(r"[<>{}\U0001f300-\U0001faff]", q) or _contains(
        q, "ignore previous instructions", "reveal the system prompt"
    ):
        return False
    if _contains(q, "xin chào", "cảm ơn", "thank you", "hello", "đc ko", "được không"):
        return False
    if q.isascii() and set(words) & {"tuan", "tuaanf", "hoc", "hocj", "gi", "gif"}:
        return False
    if re.fullmatch(r"(?:[a-z]\s*){1,3}", folded) or re.fullmatch(
        r"(?:null|undefined|cfg|\d+)", folded
    ):
        return False
    if re.search(r"\bbai\s+\d+\b|\bch\s+\d+\b", folded) or folded.endswith(" cua"):
        return False
    if _contains(q, "của là"):
        return False

    outside_topics = (
        "machine learning", "toán", "blockchain", "xác suất", "stanford", "hôm nay",
        "tuần này", "how many credits", "giải bài", "lời giải", "viết giúp tôi",
        "chương trình học", "có mưa không", "tổng thống",
        "thủ đô", "điểm thi của tôi", "mấy giờ rồi", "bạn là ai", "đoạn code python",
        "ngoài phạm vi",
    )
    if any(_contains(q, phrase) for phrase in outside_topics):
        return True
    if re.search(r"\b(which week|what is week \d+ about|week \d+ covers what)\b", folded):
        return True
    if _contains(q, "nlu", "nlp", "reference") and _contains(q, "là gì", "what is"):
        return True
    if _contains(q, "giải thích", "explain") and _contains(q, "cho tôi", "for me"):
        return True
    if _contains(q, "tại sao", "why") and _contains(q, "nlp", "môn học"):
        return True
    if _contains(q, "nlp") and any(
        _contains(q, cue)
        for cue in ("có khó không", "nên học không", "có nên học", "năm ngoái")
    ):
        return True
    if len(words) < 3:
        return False
    return False


def _result(question, q, tree, valid, action, intent, entities):
    semantic = {
        "action": action if valid else "()",
        "intent": intent,
        "entities": entities,
        "query": q,
    }
    return SemanticResult(question, valid, tree, semantic, q)

def analyze(question: str) -> SemanticResult:
    tree = parse_sentence(question)
    valid = tree != "()"
    q = normalize(question)
    tree_leaves = re.findall(r"\(([A-Z_]+) ([^()]+)\)", tree) if valid else []
    entities = {}
    intent = "UNKNOWN"
    action = "UNKNOWN"
    course = bool(
        re.search(
            r"\b(co3085|nlp)\b|natural language processing|xử lý ngôn ngữ tự nhiên|môn học",
            q,
        )
    )
    week = re.search(r"\b(?:tuần|week)\s*(?:thứ\s*|số\s*)?(\d+)\b", q)
    chapter = re.search(r"\b(?:chương|chapter)\s*(?:(?:thứ|số)\s*)?(\d+)\b", q)
    lo = re.search(r"\blo\s*([1-4](?:\.\d+)?)", q)
    part = re.search(r"\b(?:part|phần)\s*(i{1,3}|iv|1|2|3|4)\b", q)
    semester = re.search(r"\bhk\s*(\d{3})\b", q)

    if valid:
        ambiguous_part = _ambiguous_part(tree_leaves, q)
        if ambiguous_part:
            return _result(
                question, q, tree, valid, ambiguous_part["action"],
                ambiguous_part["intent"], ambiguous_part["entities"],
            )
        ambiguous_final = _ambiguous_final(q)
        if ambiguous_final:
            return _result(
                question, q, tree, valid, ambiguous_final["action"],
                ambiguous_final["intent"], ambiguous_final["entities"],
            )
        rule_result = _rule_semantics(q, course, tree)
        if rule_result:
            return _result(
                question, q, tree, valid, rule_result["action"],
                rule_result["intent"], rule_result["entities"],
            )
        resource_result = _resource_semantics(q, tree_leaves, course, week, chapter)
        if resource_result:
            return _result(
                question, q, tree, valid, resource_result["action"],
                resource_result["intent"], resource_result["entities"],
            )
        if "TOPIC_Q" in tree and week and _contains(q, "chương nào", "chapter nào"):
            topic_ids = list(dict.fromkeys(
                _entity_id(value)
                for tag, value in tree_leaves
                if tag == "TOPIC"
            ))
            topic = topic_ids[0] if len(topic_ids) == 1 else topic_ids
            slots = {"week": _code("WEEK_", week.group(1))}
            if topic:
                slots["topic"] = topic
            slots["attribute"] = "chapter"
            return _result(question, q, tree, valid, "GET_TOPIC", "GET_TOPIC", slots)
    if course: entities["course"]="CO3085"
    if semester: entities["semester"]="HK"+semester.group(1)
    if lo: entities={"lo":"LO"+lo.group(1)}

    if _has(q,"bao nhiêu phút","kéo dài bao lâu","thời lượng thi"):
        intent=action="GET_EXAM_DURATION"; exam="FINAL" if _has(q,"final","cuối kỳ","cuối kì") else "MIDTERM"; entities={"exam":exam}
    elif _has(q,"mở tài liệu","được mở tài liệu","hình thức thi","open book"):
        intent=action="GET_EXAM_FORMAT"; exam="FINAL" if _has(q,"final","cuối kỳ","cuối kì") else "MIDTERM"; entities={"exam":exam}
        if _has(q,"mở tài liệu","open book"): entities["aspect"]="OPEN_BOOK"
    elif _has(q,"chiếm","phần trăm điểm","cách tính điểm"):
        intent=action="GET_ASSESSMENT"; entities={"course":"CO3085"}
        component="CLASS_ATTENTION_AND_ASSIGNMENTS" if _has(q,"chuyên cần") and _has(q,"bài tập") else "MAJOR_ASSIGNMENT" if _has(q,"bài tập lớn") else "MIDTERM" if _has(q,"midterm","giữa kỳ","giữa kì") else "FINAL" if _has(q,"final","cuối kỳ","cuối kì") else None
        if component: entities["component"]=component
    elif _has(q,"ai dạy","giảng viên","giáo viên phụ trách","người dạy"):
        intent=action="GET_INSTRUCTOR"
    elif lo or _has(q,"chuẩn đầu ra","learning outcome") or (course and _has(q," lo nào"," bao nhiêu lo")) or ("LO_Q" in tree and _has(q,"lo nào liên quan")):
        intent=action="GET_LO"
        if lo: entities={"lo":"LO"+lo.group(1)}
        elif course: entities={"course":"CO3085"}
        elif any(tag == "TOPIC" for tag, _value in tree_leaves):
            topic_leaf=next(value for tag,value in tree_leaves if tag=="TOPIC")
            entities={"topic":_entity_id(topic_leaf)}
        if _has(q,"bao nhiêu","có mấy","số lượng") or _has(q,"bao nhiêu lo"): entities["attribute"]="count"
    elif (
        _has(q, "deadline", "h\u1ea1n n\u1ed9p", "h\u1ea1n cu\u1ed1i", "khi n\u00e0o ph\u1ea3i n\u1ed9p", "bao gi\u1edd ph\u1ea3i n\u1ed9p", "checkpoint")
        or ("n\u1ed9p" in q and _has(q, "khi n\u00e0o", "tu\u1ea7n n\u00e0o", "tu\u1ea7n m\u1ea5y"))
        or ("demo" in q and _has(q, "khi n\u00e0o"))
    ):
        intent = action = "GET_DEADLINE"
        entities = {"assignment": "BTL01"}
        if part:
            entities["part"] = "PART_" + part.group(1).upper()
        topic_leaf = next((value for tag, value in tree_leaves if tag == "TOPIC"), None)
        part_aliases = {
            "parser": "PART_I",
            "grammar_and_parser": "PART_I",
            "semantic_interpretation": "PART_II",
            "semantic_interpretation_and_qa": "PART_II",
            "question_answering": "PART_II",
            "local_discourse_context": "PART_III",
            "dialogue": "PART_III",
            "evaluation": "PART_IV",
        }
        if topic_leaf in part_aliases:
            entities["part"] = part_aliases[topic_leaf]
        if _has(q, "checkpoint 1", "checkpoint_1"):
            entities["milestone"] = "CHECKPOINT_1"
        elif _has(q, "checkpoint 2", "checkpoint_2"):
            entities["milestone"] = "CHECKPOINT_2"
        if _has(q, "final n\u1ed9p", "final submission", "n\u1ed9p cu\u1ed1i", "demo", "b\u1ea3n n\u1ed9p cu\u1ed1i"):
            entities["milestone"] = "FINAL_SUBMISSION_AND_DEMO"
        if _has(q, "checkpoint") and _has(q, "g\u00ec", "y\u00eau c\u1ea7u"):
            entities["attribute"] = "content"
    elif course and _has(q,"phần chính","gồm những phần","mấy phần"):
        intent="GET_COURSE_INFO"; action="GET_MAIN_PARTS"; entities={"course":"CO3085"}
    elif course and _has(q,"bao nhiêu chương","mấy chương","số chương"):
        intent="GET_COURSE_INFO"; action="GET_CHAPTER_COUNT"; entities={"course":"CO3085"}
    elif "RULE_Q" in tree and _has(q,"quy định"):
        intent=action="GET_RULE"
        entities={"assignment":"BTL01"} if "ASSIGN" in dict(tree_leaves) else {}
        entities["rule"]="SUBMISSION" if _has(q,"nộp") else "AI_USAGE" if _has(q,"ai") else "UNKNOWN"
    elif "ASSIGN_Q" in tree and not _has(q,"quy định","tài liệu","giáo trình"):
        intent=action="GET_ASSIGNMENT"
        entities={"assignment":"BTL01"}
        leaf_map=dict(tree_leaves)
        part_aliases = {
            "hỏi_đáp": "PART_II",
            "question_answering": "PART_II",
            "qa": "PART_II",
            "semantic_interpretation": "PART_II",
            "semantic_interpretation_and_qa": "PART_II",
            "parser": "PART_I",
            "grammar_and_parser": "PART_I",
            "đánh_giá": "PART_IV",
            "evaluation": "PART_IV",
            "hội_thoại": "PART_III",
            "dialogue": "PART_III",
            "local_discourse_context": "PART_III",
        }
        if part:
            part_id="PART_"+part.group(1).upper()
            if part.group(1).lower() in {"ii","iii"} and not _has(q,"bài tập lớn","btl"):
                intent="AMBIGUOUS"; action="GET_PART"
                course_part="COURSE_PART_"+part.group(1).upper()
                entities={"part":f"@AMBIGUOUS({part_id}|{course_part})"}
            else:
                entities["part"]=part_id
        topic_leaf=leaf_map.get("TOPIC")
        if topic_leaf in part_aliases:
            entities["part"]=part_aliases[topic_leaf]
        file_leaf=leaf_map.get("FILE")
        if file_leaf:
            entities["file"]=_id(file_leaf)
            entities["attribute"]="content" if _has(q,"chứa gì") else "purpose"
        item=leaf_map.get("ITEM")
        if item:
            entities["item"]=_id(item)
            entities["attribute"]="required" if _has(q,"cần") else "not_required"
        extension=leaf_map.get("EXT")
        if extension:
            entities["extension"]="LLM_RAG_EXTENSION"; entities["attribute"]="optional"
        if _has(q,"intent nào"):
            entities["part"]="PART_II"; entities["attribute"]="suggested_intents"
        elif _has(q,"không bắt buộc những gì"):
            entities["attribute"]="not_required"
        elif _has(q,"gồm những phần nào"):
            entities["attribute"]="parts"
        elif _has(q,"xuất file"):
            entities["attribute"]="outputs"
        elif _has(q,"intelligent course assistant"):
            entities={"assignment":"BTL01"}
        elif "NP_APART" in tree and "part" not in entities:
            roman=next((value for tag,value in tree_leaves if tag=="ROMAN"),None)
            if roman: entities["part"]="PART_"+roman.upper()
        field = (
            "requirements"
            if (
                _has(q, "y\u00eau c\u1ea7u", "x\u00e2y d\u1ef1ng", "ph\u1ea3i l\u00e0m nh\u1eefng g\u00ec")
                and not _has(q, "kh\u00f4ng")
            )
            else "title" if _has(q, "t\u00ean")
            else "team_size" if _has(q, "nh\u00f3m", "sinh vi\u00ean")
            else "domain" if _has(q, "mi\u1ec1n \u1ee9ng d\u1ee5ng")
            else "goal" if _has(q, "m\u1ee5c ti\u00eau")
            else "parts" if _has(q, "c\u00e1c ph\u1ea7n", "m\u1ea5y ph\u1ea7n", "g\u1ed3m nh\u1eefng ph\u1ea7n")
            else "outputs" if _has(q, "s\u1ea3n ph\u1ea9m", "\u0111\u1ea7u ra", "xu\u1ea5t file", "g\u1ed3m nh\u1eefng file")
            else "not_required" if _has(q, "kh\u00f4ng b\u1eaft bu\u1ed9c")
            else "optional" if _has(q, "b\u1eaft bu\u1ed9c")
            else "submission_format" if _has(q, "n\u1ed9p", "\u0111\u1ecbnh d\u1ea1ng")
            else "required" if _has(q, "c\u1ea7n test")
            else None
        )
        if field and "attribute" not in entities:
            entities["attribute"]=field
    elif "INFO_Q" in tree and any(tag=="COMP" and value=="bài_tập_lớn" for tag,value in tree_leaves) and _has(q,"đánh giá"):
        intent="GET_COURSE_INFO"; action="GET_ASSESSMENT"
        entities={"course":"CO3085","component":"MAJOR_ASSIGNMENT"}
    elif not course and _has(q,"bài tập lớn","btl01","btl","mỗi nhóm") and _has(q,"yêu cầu","mục tiêu","tên","nhóm","phần","sản phẩm","nộp","xây dựng","là gì","bao nhiêu") and not _has(q,"tuần nào","học vào tuần","học ở tuần","tài liệu","giáo trình"):
        intent=action="GET_ASSIGNMENT"; entities={"assignment":"BTL01"}
        if part: entities["part"]="PART_"+part.group(1).upper()
        field = (
            "requirements"
            if (
                _has(q, "y\u00eau c\u1ea7u", "x\u00e2y d\u1ef1ng", "ph\u1ea3i l\u00e0m nh\u1eefng g\u00ec")
                and not _has(q, "kh\u00f4ng")
            )
            else "title" if _has(q, "t\u00ean")
            else "team_size" if _has(q, "nh\u00f3m", "sinh vi\u00ean")
            else "domain" if _has(q, "mi\u1ec1n \u1ee9ng d\u1ee5ng")
            else "goal" if _has(q, "m\u1ee5c ti\u00eau")
            else "parts" if _has(q, "c\u00e1c ph\u1ea7n", "m\u1ea5y ph\u1ea7n", "g\u1ed3m nh\u1eefng ph\u1ea7n")
            else "outputs" if _has(q, "s\u1ea3n ph\u1ea9m", "\u0111\u1ea7u ra", "xu\u1ea5t file", "g\u1ed3m nh\u1eefng file")
            else "not_required" if _has(q, "kh\u00f4ng b\u1eaft bu\u1ed9c")
            else "optional" if _has(q, "b\u1eaft bu\u1ed9c")
            else "submission_format" if _has(q, "n\u1ed9p", "\u0111\u1ecbnh d\u1ea1ng")
            else "required" if _has(q, "c\u1ea7n test")
            else None
        )
        if field: entities["attribute"]=field
    elif _has(q,"tài liệu","giáo trình","sách","slide","tài nguyên","tham khảo"):
        intent=action="GET_RESOURCE"
        usage=_find_alias(q,"USAGE")
        if usage: entities={"usage":_entity_id(usage,"USAGE")}
        elif week: entities={"week":_code("WEEK_", week.group(1)),"type":"LECTURE_SLIDES"}
        elif course: entities={"course":"CO3085","type":"TEXTBOOK"}
        else: entities={"assignment":"BTL01"} if _has(q,"bài tập lớn","btl") else {}
    elif _has(q,"quy định","điểm danh","tham dự","tuân thủ","liêm chính","được phép","có được"):
        intent=action="GET_RULE"
        rule=next((v for terms,v in [(('ai','trí tuệ nhân tạo'),'AI_USAGE'),(('llm','rag'),'LLM_RAG'),(('điểm danh','chuyên cần'),'ATTENDANCE'),(('liêm chính học thuật','đạo văn'),'ACADEMIC_INTEGRITY'),(('source code','mã nguồn'),'SOURCE_CODE'),(('chia sẻ bài','chia sẻ mã'),'ASSIGNMENT_SHARING'),(('thư viện ngoài','external libraries'),'EXTERNAL_LIBRARIES'),(('ngoài phạm vi','out of scope'),'OUT_OF_SCOPE')] if _has(q,*terms)),None)
        if rule: entities={"rule":rule}
        if course: entities={"course":"CO3085"}
        if _has(q,"bài tập lớn","btl"): entities={"assignment":"BTL01","rule":rule} if rule else {"assignment":"BTL01"}
    elif week or _has(q,"lịch học","tuần nào","tuần mấy","học vào tuần","học ở tuần","thi vào tuần","thi vào ngày","thứ mấy","phòng nào") or (any(tag == "EXAM" for tag, _ in tree_leaves) and _has(q,"thi vào")):
        intent=action="GET_SCHEDULE"
        if week: entities={"week":_code("WEEK_", week.group(1))}
        elif chapter: entities={"chapter":_code("CH", chapter.group(1))}
        else:
            cpart=part
            topic=_find_alias(q,"TOPICS")
            if cpart: entities={"course_part":"COURSE_PART_"+cpart.group(1).upper()}
            elif topic: entities={"topic":_id(topic)}
            elif course: entities={"course":"CO3085"}
        slot_topic=next((v for tag,v in tree_leaves if tag=="TOPIC"),None)
        slot_exam=next((v for tag,v in tree_leaves if tag=="EXAM"),None)
        slot_part=next((v for tag,v in tree_leaves if tag=="CPART"),None)
        slot_chid=next((v for tag,v in tree_leaves if tag=="CHID"),None)
        if slot_topic: entities={"topic":_entity_id(slot_topic)}
        if slot_exam: entities={"exam":slot_exam.upper()}
        if slot_part:
            part_map={"syntactic_processing":"COURSE_PART_I","xử_lý_cú_pháp":"COURSE_PART_I","semantic_interpretation":"COURSE_PART_II","diễn_dịch_ngữ_nghĩa":"COURSE_PART_II","context_and_world_knowledge":"COURSE_PART_III","ngữ_cảnh_và_tri_thức_thế_giới":"COURSE_PART_III","introduction":"INTRODUCTION","integration_and_evaluation":"INTEGRATION_AND_EVALUATION"}
            entities={"course_part":part_map.get(slot_part,_id(slot_part))}
        if slot_chid: entities={"chapter":_id(slot_chid)}
        if week:
            if _has(q,"hoạt động"): entities["attribute"]="activity"
            elif _has(q,"milestone","mốc"): entities["attribute"]="milestone"
            elif _has(q,"thuộc phần"): entities["attribute"]="part"
            elif _has(q,"học chương"): entities["attribute"]="chapter"
            if _has(q,"bài tập lớn","btl"): entities={"assignment":"BTL01",**entities}
        elif _has(q,"milestone","mốc"):
            entities={"attribute":"milestone"}
        elif chapter and _has(q,"tuần"): entities={"chapter":_code("CH", chapter.group(1))}
        elif part and _has(q,"bài tập lớn","btl"):
            entities={"assignment":"BTL01","part":"PART_"+part.group(1).upper()}
        elif "SCHED_Q" in tree and any(tag=="NUM" for tag,_ in tree_leaves):
            numeric=next(v for tag,v in tree_leaves if tag=="NUM")
            clf=next((v for tag,v in tree_leaves if tag=="CLF"),"")
            if clf in {"tuần","week"}: entities={"week":_code("WEEK_", numeric)}
            elif clf in {"chương","chapter"}: entities={"chapter":_code("CH", numeric)}
        if _has(q,"ngày nào"): entities["attribute"]="date"
        elif _has(q,"thứ mấy"): entities={"course":"CO3085","attribute":"day"}
        elif _has(q,"phòng nào"): entities={"course":"CO3085","attribute":"room"}
        # Combine schedule slots when a question mentions more than one entity.
        if week or chapter or slot_topic or slot_exam:
            slot_values = []
            if _has(q,"bài tập lớn","btl") and not slot_topic:
                slot_values.append((q.find("bài tập") if "bài tập" in q else q.find("btl"), "assignment", "BTL01"))
            if chapter:
                slot_values.append((chapter.start(), "chapter", _code("CH", chapter.group(1))))
            if week:
                slot_values.append((week.start(), "week", _code("WEEK_", week.group(1))))
            if slot_topic:
                slot_values.append((q.find(normalize(slot_topic).replace("_", " ")), "topic", _entity_id(slot_topic)))
            if slot_exam:
                slot_values.append((q.find(normalize(slot_exam)), "exam", slot_exam.upper()))
            ordered = sorted(
                slot_values,
                key=lambda item: (
                    0 if item[1] == "assignment" else 1,
                    item[0] if item[0] >= 0 else len(q),
                ),
            )
            entities = {key: value for _, key, value in ordered}
            if _has(q,"hoạt động"): entities["attribute"] = "activity"
            elif _has(q,"milestone","mốc"): entities["attribute"] = "milestone"
            elif _has(q,"thuộc phần"): entities["attribute"] = "part"
            elif _has(q,"học chương", "chương nào", "chapter nào") and chapter is None: entities["attribute"] = "chapter"
            elif _has(q,"ngày nào"): entities["attribute"] = "date"
            if _has(q,"không","phải không","đúng không"): entities["yesno"] = "TRUE"
    elif _has(q,"chương","chapter","chủ đề","nội dung","topic","các chương") or any(tag in {"CHID", "TOPIC", "SUBID"} for tag, _ in tree_leaves):
        intent=action="GET_TOPIC"
        if chapter: entities={"chapter":_code("CH", chapter.group(1))}
        subid=next((value for tag,value in tree_leaves if tag=="SUBID"),None)
        if subid: entities={"subtopic":subid}
        topic=_find_alias(q,"TOPICS")
        if topic: entities["topic"]=_entity_id(topic)
        tree_part=next((v for tag,v in tree_leaves if tag=="CPART"),None)
        tree_topics=list(dict.fromkeys(_entity_id(v) for tag,v in tree_leaves if tag=="TOPIC"))
        if tree_topics: entities["topic"]=tree_topics[0] if len(tree_topics)==1 else tree_topics
        tree_chid=next((v for tag,v in tree_leaves if tag=="CHID"),None)
        if tree_chid: entities={"chapter":_id(tree_chid)}
        if tree_part:
            pmap={"syntactic_processing":"COURSE_PART_I","semantic_interpretation":"COURSE_PART_II","context_and_world_knowledge":"COURSE_PART_III"}
            entities={"course_part":pmap.get(tree_part,_id(tree_part)),"attribute":"chapters"}
        if course and _has(q,"những chương","các chương"): entities={"course":"CO3085","attribute":"chapters"}
        elif course and not chapter: entities={"course":"CO3085","attribute":"chapters"}
        if chapter:
            if _has(q,"tên của","title"): entities={"chapter":_code("CH", chapter.group(1)),"attribute":"title"}
            elif _has(q,"từ khóa","keywords"): entities={"chapter":_code("CH", chapter.group(1)),"attribute":"keywords"}
            elif _has(q,"mấy mục nhỏ","bao nhiêu mục nhỏ"): entities={"chapter":_code("CH", chapter.group(1)),"attribute":"subtopic_count"}
            elif _has(q,"mục nhỏ","subtopic"): entities={"chapter":_code("CH", chapter.group(1)),"attribute":"subtopics"}
            elif _has(q,"thuộc phần nào"): entities={"chapter":_code("CH", chapter.group(1)),"attribute":"course_part"}
        if valid and _has(q,"không","phải không","đúng không"):
            entities["yesno"]="TRUE"
        if _has(q,"không") and topic: entities["yesno"]="TRUE"
    elif course:
        intent="GET_COURSE_INFO"
        attr=None
        if _has(q,"tín chỉ"): attr="credits"; action="GET_CREDIT"
        elif _has(q,"ects"): attr="ects"; action="GET_ECTS"
        elif _has(q,"học kỳ","học kì","semester"): attr="semester"; action="GET_SEMESTER"
        elif _has(q,"tên tiếng anh","english name"): attr="course_name_en"; action="GET_COURSE_NAME"; entities["lang"]="EN"
        elif _has(q,"tên","môn gì"): attr="course_name"; action="GET_COURSE_NAME"; entities["lang"]="VI"
        elif _has(q,"khoa"): attr="department"; action="GET_DEPARTMENT"
        elif _has(q,"khối kiến thức","loại môn"): attr="course_type"; action="GET_COURSE_TYPE"
        elif _has(q,"mỗi tuần","tiết"): attr="format"; action="GET_FORMAT"; entities["aspect"]="PERIODS_PER_WEEK"
        elif _has(q,"bao nhiêu tuần","số tuần"): attr="format"; action="GET_FORMAT"; entities["aspect"]="WEEKS"
        elif _has(q,"giờ"): attr="hours"; action="GET_HOURS"; entities["type"]="LECTURE" if _has(q,"lý thuyết") else "ASSIGNMENT" if _has(q,"bài tập") else "SELF_STUDY" if _has(q,"tự học") else "TOTAL"
        elif _has(q,"mô tả"): attr="description"; action="GET_DESCRIPTION"
        elif _has(q,"mục tiêu"): attr="objective"; action="GET_OBJECTIVE"
        elif _has(q,"phần chính","gồm mấy phần"): attr="main_parts"; action="GET_MAIN_PARTS"
        elif _has(q,"đánh giá","điểm giữa kỳ","cuối kỳ"): attr="assessment"; action="GET_ASSESSMENT"
        if attr:
            entities["attribute"]=attr
            if entities.get("lang"): entities={"course":"CO3085","lang":entities["lang"],"attribute":attr}
    elif _has(q,"chương","chủ đề","nội dung"):
        intent=action="GET_TOPIC"
        if chapter: entities={"chapter":_code("CH", chapter.group(1))}
        topic=_find_alias(q,"TOPICS")
        if topic: entities["topic"]=_id(topic)

    # Preserve the OOD marker only for coherent questions outside the course scope.
    if not valid and _out_of_scope_question(q):
        entities={"_out_of_scope":"OUT_OF_SCOPE"}
    if not valid: action="()"
    semantic={"action":action,"intent":intent,"entities":entities,"query":q}
    return SemanticResult(question,valid,tree,semantic,q)
