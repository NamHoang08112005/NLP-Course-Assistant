"""Bounded deterministic sentence generation from the pure CFG."""
from course_assistant.nlp.grammar import load_grammar


def generate_sentences(grammar=None, limit: int = 10_000) -> list[str]:
    if limit <= 0:
        return []
    grammar = grammar or load_grammar()
    pending = [(grammar.start, 0)]
    seen = set()
    results = []
    expansions = 0
    max_expansions = max(1_000_000, limit * 1_000)
    max_depth = 80

    while pending and len(results) < limit and expansions < max_expansions:
        sequence, depth = pending.pop()
        if isinstance(sequence, str):
            sequence = (sequence,)
        index = next(
            (i for i, symbol in enumerate(sequence)
             if symbol in grammar.nonterminals),
            None,
        )
        if index is None:
            words = [
                symbol[1:-1].replace("\\'", "'").replace("_", " ")
                for symbol in sequence
            ]
            sentence = " ".join(words)
            if sentence and sentence not in seen:
                seen.add(sentence)
                results.append(sentence)
            continue
        if depth >= max_depth:
            continue

        symbol = sequence[index]
        alternatives = grammar.productions.get(symbol, ())
        for alternative in reversed(alternatives):
            expansions += 1
            pending.append((
                sequence[:index] + alternative + sequence[index + 1:],
                depth + 1,
            ))
    return results[:limit]
