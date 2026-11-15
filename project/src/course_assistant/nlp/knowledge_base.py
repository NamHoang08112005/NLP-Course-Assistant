import json
import os
import re
import unicodedata
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .grammar_generator import resolve_runtime_paths
except ImportError:
    def resolve_runtime_paths(data_dir=None, **kwargs):
        data_path = Path(data_dir) if data_dir else Path(__file__).resolve().parents[3] / "data"
        return {"data": data_path}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def read(path: os.PathLike) -> str:
    with open(path, encoding="utf-8") as f:
        return nfc(f.read())


KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


def parse_kv(text: str) -> OrderedDict:
    """'key: value' pairs; following non-key lines are continuation lines."""
    d, key = OrderedDict(), None
    for ln in text.splitlines():
        m = KEY_RE.match(ln)
        if m:
            key = m.group(1)
            d[key] = m.group(2).strip()
        elif key is not None and ln.strip():
            d[key] = (d[key] + "\n" + ln.strip()).strip()
    return d


def one_line(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


SMALL = {"and", "of", "to", "for", "the", "in", "on", "with"}


def smart_title(s: str) -> str:
    out = []
    for i, w in enumerate(s.lower().split()):
        out.append(w if (w in SMALL and i > 0) or w == "-" else w.capitalize())
    return " ".join(out)


# ---------------------------------------------------------------- domain lexicon
TOPIC_ALIASES = {
    "CFG": ["cfg", "context-free grammar"],
    "PCFG": ["pcfg", "probabilistic context-free grammar"],
    "DEPENDENCY_GRAMMAR": ["dependency grammar"],
    "FEATURES": ["feature"],
    "AUGMENTED_GRAMMAR": ["augmented grammar"],
    "UNIFICATION": ["unification"],
    "POS_TAGGING": ["pos tagging", "part-of-speech tagging"],
    "LOGICAL_FORM": ["logical form"],
    "THEMATIC_ROLES": ["thematic role"],
    "SELECTIONAL_RESTRICTION": ["selectional restriction"],
    "SEMANTIC_NETWORK": ["semantic network"],
    "WSD": ["wsd", "word sense disambiguation"],
    "SEMANTIC_GRAMMAR": ["semantic grammar"],
    "KNOWLEDGE_REPRESENTATION": ["knowledge representation"],
    "QUESTION_ANSWERING": ["question answering", "qa"],
    "LOCAL_DISCOURSE_CONTEXT": ["local discourse context", "discourse context"],
    "REFERENCE": ["reference"],
    "ANAPHORA": ["anaphora"],
    "CENTERING": ["centering"],
    "PARSING": ["parsing", "parser"],
    "ELLIPSIS": ["ellipsis"],
    "FRAMES": ["frame"],
    "TEMPLATE_MATCHING": ["template matching"],
    "PROBABILITY": ["probability", "probabilistic"],
    "CHART_PARSING": ["chart parser", "chart parsing"],
    "BEST_FIRST_PARSING": ["best-first parsing"],
    "SPEECH_ACTS": ["speech act"],
    "COMPOSITIONALITY": ["compositionality"],
}

TOPIC_DISPLAY = {
    "QUESTION_ANSWERING": "Question Answering",
    "WSD": "WSD",
    "STATISTICAL_NLP": "statistical NLP",
    "PYTHON_NLP": "Python NLP",
    "MACHINE_TRANSLATION": "machine translation",
    "VIETNAMESE_NLP": "NLP tiếng Việt",
    "WORLD_KNOWLEDGE": "world knowledge",
}

RESOURCE_KEYWORDS = {
    "STATISTICAL_NLP": ["statistical"],
    "PYTHON_NLP": ["python"],
    "MACHINE_TRANSLATION": ["machine translation"],
    "VIETNAMESE_NLP": ["vietnamese"],
    "WORLD_KNOWLEDGE": ["world knowledge"],
}

LO_CHAPTER = {
    "LO1.1": "CH01", "LO2.1": "CH02", "LO2.2": "CH03", "LO2.3": "CH04",
    "LO2.4": "CH05", "LO2.5": "CH06", "LO3.1": "CH07", "LO3.2": "CH08",
    "LO3.3": "CH09", "LO3.4": "CH10", "LO4.1": "CH11", "LO4.2": "CH12"
}


class KnowledgeBase:
    def __init__(self, data_dir: Optional[str] = None):
        paths = resolve_runtime_paths(data_dir=data_dir)
        data_path = paths["data"]
        
        # Định vị đúng thư mục chứa file txt (uu tiên data/course/)
        course_path = data_path / "course"
        self.dir = course_path if course_path.is_dir() else data_path

        self._load_course()
        self._load_schedule()
        self._load_topics()
        self._load_assignments()
        self._load_resources()
        
        reg_path = self.dir / "regulations.txt"
        self.rules = parse_kv(read(reg_path)) if reg_path.is_file() else {}
        self._load_faq()

    def _load_course(self):
        file_path = self.dir / "course_info.txt"
        if not file_path.is_file():
            self.course, self.los, self.main_parts = {}, {}, []
            return
        text = read(file_path)
        self.course = parse_kv(text)
        desc = self.course.get("course_description", "")
        parts = desc.split("Mục tiêu:")
        self.course["description"] = one_line(parts[0])
        self.course["goal"] = one_line(parts[1]) if len(parts) > 1 else None
        self.los = OrderedDict()
        for m in re.finditer(r"^(LO\d(?:\.\d)?) - (.*(?:\n[ \t]+.*)*)", text, re.M):
            self.los[m.group(1)] = one_line(m.group(2))
        self.main_parts = [one_line(x) for x in self.course.get("main_parts", "").splitlines() if x.strip()]

    def _load_schedule(self):
        file_path = self.dir / "schedule.txt"
        if not file_path.is_file():
            self.weeks, self.schedule_note = {}, ""
            return
        text = read(file_path)
        self.weeks = OrderedDict()
        for m in re.finditer(r"^WEEK (\d+)\s*$(.*?)(?=^WEEK \d+\s*$|\Z)", text, re.S | re.M):
            n, w = int(m.group(1)), {"week": int(m.group(1)), "topics": []}
            for ln in m.group(2).splitlines():
                if ln.strip().startswith("- "):
                    w["topics"].append(ln.strip()[2:].strip())
                else:
                    mm = re.match(r"(\w+):\s*(.*)", ln)
                    if mm and mm.group(1) != "topics":
                        w[mm.group(1)] = mm.group(2).strip()
            c = re.search(r"Chapter (\d+)", w.get("chapter", ""))
            w["chapter_id"] = f"CH{int(c.group(1)):02d}" if c else None
            self.weeks[n] = w
        self.schedule_note = one_line(text.split("WEEK 01")[0].replace("PROPOSED 15-WEEK STUDY PLAN", "").replace("=", ""))

    def _load_topics(self):
        file_path = self.dir / "topics.txt"
        if not file_path.is_file():
            self.chapters = {}
            return
        text = read(file_path)
        self.chapters = OrderedDict()
        for m in re.finditer(r"^CHAPTER (\d+): (.*?)$(.*?)(?=^CHAPTER \d+:|\Z)", text, re.S | re.M):
            body = m.group(3)
            cid = re.search(r"chapter_id:\s*(\w+)", body).group(1)
            subs = re.findall(r"^(\d+\.\d+(?:\.\d+)?) (.*)$", body.split("subtopics:")[1], re.M)
            self.chapters[cid] = {
                "id": cid, "num": int(m.group(1)), "title": smart_title(m.group(2).strip()),
                "part": re.search(r"part:\s*(.*)", body).group(1).strip(),
                "keywords": [k.strip() for k in re.search(r"keywords:\s*(.*)", body).group(1).split(",")],
                "summary": one_line(re.search(r"summary:\s*\n(.*?)\n\s*\n", body, re.S).group(1)),
                "subtopics": subs,
            }

    def _load_assignments(self):
        file_path = self.dir / "assignments.txt"
        if not file_path.is_file():
            self.assignment, self.assign_ext, self.parts = {}, {}, {}
            return
        text = read(file_path)
        main, _, ext = text.partition("LLM/RAG EXTENSION")
        head, *_ = re.split(r"^PART [IV]+ - ", main, flags=re.M)
        self.assignment = parse_kv(head)
        self.assignment["goal"] = one_line(self.assignment.get("goal", ""))
        self.assign_ext = parse_kv(ext)
        self.parts = OrderedDict()
        for m in re.finditer(r"^PART ([IV]+) - (.*?)$(.*?)(?=^PART [IV]+ - |\Z)", main, re.S | re.M):
            cur, d = None, OrderedDict()
            for ln in m.group(3).splitlines():
                s = ln.strip()
                if not s or set(s) <= {"-"}:
                    continue
                mm = re.match(r"(\w+):\s*(.*)$", s)
                if mm and not s.startswith("- "):
                    cur = mm.group(1)
                    d[cur] = [mm.group(2)] if mm.group(2) else []
                elif cur:
                    d[cur].append(s[2:] if s.startswith("- ") else s)
            self.parts["PART_" + m.group(1)] = {"id": "PART_" + m.group(1), "roman": m.group(1),
                                                "title": m.group(2).strip(), **d}

    def _load_resources(self):
        file_path = self.dir / "resources.txt"
        if not file_path.is_file():
            self.resources, self.resource_note = [], ""
            return
        text = read(file_path)
        body, _, note = text.partition("study_note:")
        self.resource_note = one_line(note)
        self.resources = []
        for m in re.finditer(r"^(TEXTBOOK|REFERENCE) (\d+)\s*$(.*?)(?=^(?:TEXTBOOK|REFERENCE) \d+\s*$|\Z)",
                             body, re.S | re.M):
            kv = parse_kv(m.group(3))
            kv["kind"], kv["no"] = m.group(1), int(m.group(2))
            kv["authors"] = kv.get("authors") or kv.get("author") or ""
            self.resources.append(kv)

    def _load_faq(self):
        file_path = self.dir / "faq.txt"
        if not file_path.is_file():
            self.faq = []
            return
        text = read(file_path)
        self.faq = []
        for m in re.finditer(r"^Q(\d+):\s*$(.*?)(?=^Q\d+:|\Z)", text, re.S | re.M):
            kv = parse_kv(m.group(2))
            self.faq.append({"id": f"Q{m.group(1)}", "question": one_line(kv.get("question", "")),
                             "answer": one_line(kv.get("answer", ""))})

    def to_dict(self) -> Dict[str, Any]:
        """Xuất toàn bộ Knowledge Base thành Python Dictionary có cấu trúc."""
        return {
            "course_info": getattr(self, "course", {}),
            "learning_outcomes": getattr(self, "los", {}),
            "schedule": {
                "note": getattr(self, "schedule_note", ""),
                "weeks": getattr(self, "weeks", {})
            },
            "topics": getattr(self, "chapters", {}),
            "assignments": {
                "overview": getattr(self, "assignment", {}),
                "parts": getattr(self, "parts", {}),
                "extension": getattr(self, "assign_ext", {})
            },
            "resources": {
                "note": getattr(self, "resource_note", ""),
                "items": getattr(self, "resources", [])
            },
            "regulations": getattr(self, "rules", {}),
            "faq": getattr(self, "faq", [])
        }

    def export_json(self, output_path: Optional[str] = None) -> str:
        if output_path is None:
            output_path = self.dir.parent / "knowledge_base.json"
        else:
            output_path = Path(output_path)
            
        kb_dict = self.to_dict()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(kb_dict, f, ensure_ascii=False, indent=2)
            
        print(f"Đã xuất Knowledge Base thành công ra: {output_path}")
        return str(output_path)


def generate_kb_json(data_dir: Optional[str] = None, output_file: Optional[str] = None):
    kb = KnowledgeBase(data_dir=data_dir)
    return kb.export_json(output_path=output_file)


if __name__ == "__main__":
    import sys
    target_data = sys.argv[1] if len(sys.argv) > 1 else None
    kb = KnowledgeBase(data_dir=target_data)
    kb.export_json()