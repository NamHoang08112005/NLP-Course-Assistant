"""Load and tokenize the pure context-free grammar."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import unicodedata


TOKEN_RE = re.compile(r"'(?:\\.|[^'\\])*'|[^\s|]+")


@dataclass(frozen=True)
class Grammar:
    productions: dict[str, tuple[tuple[str, ...], ...]]
    nonterminals: frozenset[str]
    lexicon: dict[str, tuple[tuple[str, str], ...]]
    start: str = "S"

    def __getitem__(self, symbol):
        return self.productions[symbol]


def _unquote(symbol):
    body = symbol[1:-1]
    return re.sub(r"\\(.)", r"\1", body)


@lru_cache(maxsize=1)
def load_grammar():
    path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "grammar"
        / "course_assistant.cfg"
    )
    raw_rules = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lhs, rhs = line.split("->", 1)
        alternatives = tuple(
            tuple(TOKEN_RE.findall(alternative.strip()))
            for alternative in rhs.split("|")
        )
        raw_rules[lhs.strip()] = alternatives

    nonterminals = frozenset(raw_rules)
    lexical = {}
    for lhs, alternatives in raw_rules.items():
        for alternative in alternatives:
            if len(alternative) == 1 and alternative[0].startswith("'"):
                terminal = _unquote(alternative[0])
                lexical.setdefault(terminal, []).append((lhs, terminal))
    return Grammar(
        raw_rules,
        nonterminals,
        {terminal: tuple(entries) for terminal, entries in lexical.items()},
    )


def normalize(text):
    """Normalize punctuation, common abbreviations, and whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = unicodedata.normalize("NFC", text).casefold().strip()
    text = re.sub(r"^[\"'“‘]+|[\"'”’]+$", "", text).strip()
    text = re.sub(r"\bl\s*\.\s*o\.?\s*(?=\d)", "lo", text)
    text = re.sub(r"\blo\s+(?=\d)", "lo", text)
    text = re.sub(r"[?!。！？.]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()
