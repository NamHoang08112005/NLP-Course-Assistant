"""Generate Group A artifacts from the newline-delimited input file."""
from pathlib import Path

from course_assistant.nlp.formatters import (
    format_grammar,
    format_intent_entities,
    format_semantic,
)
from course_assistant.nlp.generator import generate_sentences
from course_assistant.nlp.grammar import load_grammar
from course_assistant.nlp.semantic import analyze


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    source = root / "input" / "sentences.txt"
    output = root / "output"
    output.mkdir(parents=True, exist_ok=True)

    grammar = load_grammar()
    input_lines = source.read_text(encoding="utf-8-sig").splitlines()
    analyses = [analyze(line) for line in input_lines]
    files = {
        "grammar.txt": format_grammar(grammar),
        "samples.txt": "\n".join(generate_sentences(grammar, limit=10_000)),
        "parse-results.txt": "\n".join(item.parse_tree or "()" for item in analyses),
        "semantic.txt": "\n".join(format_semantic(item) for item in analyses),
        "intent-entity.txt": "\n".join(
            format_intent_entities(item) for item in analyses
        ),
    }
    for name, body in files.items():
        (output / name).write_text(body + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
