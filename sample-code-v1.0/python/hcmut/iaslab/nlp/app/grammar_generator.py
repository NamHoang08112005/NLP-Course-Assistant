"""Load a course CFG and generate grammar and example sentence files."""

from collections import deque
from pathlib import Path
import re
import shlex
from typing import Dict, List, Optional, Tuple


RuleMap = Dict[str, List[Tuple[str, ...]]]

# Dockerfile copies only the python/ build context into /src, while the CFG
# lives at the local project root. Prefer that file whenever it is available;
# this bundled copy keeps the Docker run usable without changing instructor files.
DEFAULT_COURSE_GRAMMAR = '# Start symbol: one production family per supported intent.\nS -> INFO_Q | SCHED_Q | TOPIC_Q | ASSIGN_Q | DEADLINE_Q | RESOURCE_Q | RULE_Q\n\n# Course information and schedule.\nINFO_Q -> NP_COURSE V WH ATTR\nINFO_Q -> NP_COURSE WH ATTR\nINFO_Q -> ATTR P NP_COURSE V WH\nINFO_Q -> WH V NP_COURSE\nINFO_Q -> WH V ATTR P NP_COURSE\nSCHED_Q -> NP_COURSE V P WH_DAY\nSCHED_Q -> NP_TOPIC V WH_WEEK\nSCHED_Q -> NP_TOPIC V P WH_WEEK\nSCHED_Q -> WH_WEEK V TOPIC\nSCHED_Q -> NP_COURSE V P WH_ROOM\nSCHED_Q -> NP_COURSE V P WH_TIME\nTOPIC_Q -> NP_WEEK V DET CONTENT_N WH\nTOPIC_Q -> NP_WEEK V DET WH\nTOPIC_Q -> NP_WEEK V WH\nTOPIC_Q -> NP_WEEK V V TOPIC PART\nTOPIC_Q -> NP_WEEK V CONTENT_N WH\nTOPIC_Q -> CONTENT_N P NP_WEEK V WH\n\n# Assignment, deadline, resource, and course-rule questions.\nASSIGN_Q -> NP_ASSIGN V DET REQUIREMENT_N WH\nASSIGN_Q -> NP_USER V V DET N WH\nASSIGN_Q -> NP_ASSIGN V WH\nASSIGN_Q -> REQUIREMENT_N P NP_ASSIGN V WH\nASSIGN_Q -> NP_ASSIGN V P N WH N\nDEADLINE_Q -> DEADLINE_N P NP_ASSIGN V WH\nDEADLINE_Q -> N NP_ASSIGN V WH\nDEADLINE_Q -> WH V V NP_ASSIGN\nDEADLINE_Q -> NP_ASSIGN V P WH_WEEK\nRESOURCE_Q -> N WH V TOPIC\nRESOURCE_Q -> N P NP_COURSE V WH\nRESOURCE_Q -> N P NP_TOPIC V WH\nRESOURCE_Q -> N P NP_WEEK V WH\nRESOURCE_Q -> N P TOPIC V WH\nRULE_Q -> NP_ASSIGN V V V NP_TOOL PART\nRULE_Q -> NP_ASSIGN V V V ADV PART\nRULE_Q -> NP_COURSE V N WH P N\n\n# Phrase structure.\nNP_COURSE -> CLF COURSE\nNP_WEEK -> WEEK_CLF NUM\nNP_WEEK -> WEEK_CLF DEIXIS\nNP_WEEK -> WEEK_CLF REL\nNP_TOPIC -> PART_CLF TOPIC\nNP_TOPIC -> PART_CLF TOPIC_LIST\nTOPIC_LIST -> TOPIC CONJ TOPIC\nNP_ASSIGN -> ASSIGN\nNP_ASSIGN -> ASSIGN NUM\nNP_ASSIGN -> ASSIGN NP_WEEK\nNP_USER -> "tôi"\nNP_TOOL -> N TOOL\nNP_TOOL -> TOOL\nWH_DAY -> DAY_N WH\nWH_WEEK -> WEEK_CLF WH\nWH_ROOM -> ROOM_N WH\nWH_TIME -> WH HOUR_N\nPART_CLF -> "phần"\nWEEK_CLF -> "tuần"\nDAY_N -> "thứ"\nROOM_N -> "phòng"\nHOUR_N -> "giờ"\nCONTENT_N -> "nội dung"\nREQUIREMENT_N -> "yêu cầu"\nDEADLINE_N -> "deadline" | "hạn nộp"\nNP_TOPIC -> PART_CLF DEIXIS\n\n# Lexicon. Quoted multiword terminals render as one normalized tree leaf.\nCLF -> "môn" | "học phần" | "tuần" | "phần"\nCOURSE -> "nlp" | "co3085" | "xử lý ngôn ngữ tự nhiên"\nNUM -> "1" | "2" | "3" | "5" | "7" | "13" | "15" | "16" | "20" | "100" | "99999999999999999999"\nTOPIC -> "cfg" | "parsing" | "rag" | "llm" | "phân tích cú pháp" | "context-free grammar" | "văn phạm phi ngữ cảnh" | "word embedding" | "pos tagging" | "ner" | "gán nhãn từ loại" | "nhận diện thực thể"\nCONJ -> "và"\nASSIGN -> "bài tập lớn" | "bài tập" | "btl" | "project"\nTOOL -> "ai"\nTOOL -> "chatgpt"\nTOOL -> "copilot"\nDEIXIS -> "này"\nDEIXIS -> "đó"\nREL -> "sau"\nREL -> "trước"\nN -> "tín chỉ" | "thứ" | "bài tập" | "tài liệu" | "tài liệu tham khảo" | "công cụ" | "deadline" | "hạn nộp" | "giáo trình" | "nhóm" | "người" | "phòng" | "giờ" | "quy định" | "điểm danh"\nATTR -> "tín chỉ" | "giảng viên"\nV -> "có" | "học" | "nằm ở" | "là" | "cần" | "hoàn thành" | "phải" | "nộp" | "nói về" | "ở" | "được" | "sử dụng" | "dùng" | "dạy" | "làm"\nP -> "của" | "vào" | "ở" | "về" | "theo" | "lúc"\nWH -> "bao nhiêu" | "mấy" | "ai" | "gì" | "nào" | "khi nào" | "bao giờ" | "đâu"\nDET -> "những"\nPART -> "không"\nADV -> "trễ"\n'


def parse_grammar(grammar_text: str) -> RuleMap:
    """Parse CFG productions with quoted terminals and ``|`` alternatives."""
    rules: RuleMap = {}
    for line_number, raw_line in enumerate(grammar_text.splitlines(), 1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if "->" not in line:
            raise ValueError("Invalid CFG line {}: missing '->'".format(line_number))

        left, right = line.split("->", 1)
        left = left.strip()
        if not left:
            raise ValueError("Invalid CFG line {}: empty left-hand side".format(line_number))

        alternatives = rules.setdefault(left, [])
        for alternative in _split_alternatives(right):
            try:
                symbols = shlex.split(alternative, posix=True)
            except ValueError as error:
                raise ValueError("Invalid quoting on CFG line {}: {}".format(line_number, error))
            # An explicitly quoted empty terminal ("") represents epsilon.
            alternatives.append(tuple(symbol for symbol in symbols if symbol))

    if not rules:
        raise ValueError("The CFG file contains no production rules")
    return rules


def _split_alternatives(text: str) -> List[str]:
    """Split on unquoted pipes while preserving quoted multiword terminals."""
    alternatives: List[str] = []
    current: List[str] = []
    quote = None
    escaped = False
    for character in text:
        if escaped:
            current.append(character)
            escaped = False
            continue
        if character == "\\":
            current.append(character)
            escaped = True
            continue
        if character in ("'", '"'):
            if quote == character:
                quote = None
            elif quote is None:
                quote = character
        if character == "|" and quote is None:
            alternatives.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    alternatives.append("".join(current).strip())
    return alternatives


def _project_root() -> Path:
    module_path = Path(__file__).resolve()
    package_root = module_path.parents[4]  # python/ locally, /src in Docker
    for parent in module_path.parents:
        if (parent / "data" / "course_grammar.cfg").is_file():
            return parent
        if (parent / "input" / "sentences.txt").is_file():
            return parent
    if package_root.name.casefold() == "python":
        return package_root.parent
    return package_root


def _choose_directory(
    explicit: Optional[str],
    candidates: List[Path],
    marker: Optional[str],
    fallback: Optional[Path] = None,
) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()

    if marker:
        for candidate in candidates:
            if (candidate / marker).is_file():
                return candidate.resolve()
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return (fallback or candidates[0]).resolve()


def resolve_runtime_paths(
    input_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    data_dir: Optional[str] = None,
) -> Dict[str, Path]:
    """Resolve mounted Docker paths or paths relative to the local project."""
    root = _project_root()
    cwd = Path.cwd()
    docker_input = Path("/nlp/input")
    docker_output = Path("/nlp/output")
    docker_data = Path("/nlp/data")

    data_path = _choose_directory(
        data_dir,
        [docker_data, root / "data", cwd / "data"],
        "course_grammar.cfg",
        root / "data",
    )
    input_path = _choose_directory(
        input_dir,
        [docker_input, root / "input", cwd / "input"],
        "sentences.txt",
        root / "input",
    )
    output_path = _choose_directory(
        output_dir,
        [docker_output, root / "output", cwd / "output"],
        None,
        root / "output",
    )
    return {"root": root, "data": data_path, "input": input_path, "output": output_path}


def load_grammar_text(
    grammar_path: Optional[str] = None,
    data_dir: Optional[str] = None,
) -> Tuple[str, Optional[Path]]:
    """Read the project CFG, with a bundled fallback for the Docker image."""
    paths = resolve_runtime_paths(data_dir=data_dir)
    source_path = Path(grammar_path).expanduser().resolve() if grammar_path else paths["data"] / "course_grammar.cfg"
    if source_path.is_file():
        return source_path.read_text(encoding="utf-8-sig"), source_path
    if grammar_path:
        raise FileNotFoundError("Course grammar not found: {}".format(source_path))
    return DEFAULT_COURSE_GRAMMAR, None


def generate(
    grammar_path: Optional[str] = None,
    data_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    max_sentences: int = 10000,
) -> Dict[str, object]:
    """Write grammar.txt and up to 10,000 sentences to samples.txt."""
    paths = resolve_runtime_paths(data_dir=data_dir, output_dir=output_dir)
    grammar_text, source_path = load_grammar_text(grammar_path=grammar_path, data_dir=data_dir)
    rules = parse_grammar(grammar_text)
    nonterminals = set(rules)
    start = "S" if "S" in nonterminals else next(iter(rules))
    limit = max(0, min(int(max_sentences), 10000))

    output_path = paths["output"]
    output_path.mkdir(parents=True, exist_ok=True)
    grammar_output = output_path / "grammar.txt"
    samples_output = output_path / "samples.txt"
    grammar_output.write_text(grammar_text, encoding="utf-8")

    # Breadth-first expansion gives short derivations first. Sentential forms
    # are deduplicated and capped to keep recursive or unexpectedly large CFGs safe.
    pending = deque([(start,)])
    visited = {(start,)}
    samples: List[str] = []
    sample_set = set()
    max_states = 200000
    max_symbols = 80
    examined = 0

    while pending and len(samples) < limit and examined < max_states:
        form = pending.popleft()
        examined += 1
        expand_at = next((i for i, symbol in enumerate(form) if symbol in nonterminals), None)
        if expand_at is None:
            sentence = " ".join(form).strip()
            sentence = re.sub(r"\s+([,.;:!?])", r"\1", sentence)
            if sentence and sentence not in sample_set:
                sample_set.add(sentence)
                samples.append(sentence)
            continue

        symbol = form[expand_at]
        for production in rules[symbol]:
            expanded = form[:expand_at] + production + form[expand_at + 1 :]
            if len(expanded) > max_symbols or expanded in visited:
                continue
            visited.add(expanded)
            pending.append(expanded)

    samples_output.write_text("\n".join(samples) + ("\n" if samples else ""), encoding="utf-8")
    return {
        "grammar_path": source_path,
        "grammar_output": grammar_output,
        "samples_output": samples_output,
        "sample_count": len(samples),
    }


def run(**kwargs: object) -> Dict[str, object]:
    """Convenience entry point for the assignment pipeline."""
    return generate(
        grammar_path=kwargs.get("grammar_path"),
        data_dir=kwargs.get("data_dir"),
        output_dir=kwargs.get("output_dir"),
        max_sentences=kwargs.get("max_sentences", 10000),
    )
