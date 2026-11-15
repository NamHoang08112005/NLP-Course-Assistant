"""Retrieve course knowledge with TF-IDF or a local FAISS vector index."""

import math
import re
import unicodedata
from collections import Counter

from course_assistant.contracts import RetrievedChunk, SemanticResult
from course_assistant.rag.config import load_config, selected_option
from course_assistant.rag.index import load_index
from course_assistant.rag.knowledge import load_knowledge_records

_QUERY_STOP_WORDS = {
    "a",
    "about",
    "and",
    "bao",
    "be",
    "chu",
    "c",
    "co",
    "de",
    "dinh",
    "does",
    "for",
    "gi",
    "have",
    "hoc",
    "how",
    "is",
    "la",
    "many",
    "mon",
    "nhung",
    "nhieu",
    "of",
    "the",
    "tuan",
    "what",
    "which",
    "quy",
    "gi",
}
_QUERY_SYNONYMS = (
    ("tin chi", "credits ects"),
    ("mon hoc", "course"),
    ("tuan", "week"),
    ("chu de", "topics"),
    ("quy dinh", "regulations rules"),
    ("bai tap lon", "major assignment assignments"),
    ("giang vien", "instructor"),
    ("lich hoc", "schedule"),
    ("thoi luong", "duration"),
)


def _features(text: str) -> Counter[str]:
    folded = unicodedata.normalize("NFD", text.casefold())
    normalized = "".join(
        char for char in folded if unicodedata.category(char) != "Mn"
    )
    tokens = re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
    features = list(tokens)
    features.extend(
        f"{left} {right}" for left, right in zip(tokens, tokens[1:])
    )
    return Counter(features)


def _query_features(text: str) -> Counter[str]:
    folded = unicodedata.normalize("NFD", text.casefold())
    normalized = "".join(
        char for char in folded if unicodedata.category(char) != "Mn"
    )
    tokens = re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
    tokens = [token for token in tokens if token not in _QUERY_STOP_WORDS]
    features = Counter(tokens)
    features.update(
        f"{left} {right}" for left, right in zip(tokens, tokens[1:])
    )
    for phrase, aliases in _QUERY_SYNONYMS:
        if phrase in normalized:
            features.update(_features(aliases))
            following_number = re.search(
                rf"{re.escape(phrase)}\s+(\d+)",
                normalized,
            )
            if following_number:
                alias = aliases.split()[0]
                features[f"{alias} {following_number.group(1)}"] += 1
    return features


def _statistical_retrieve(query_text: str, top_k: int) -> list[RetrievedChunk]:
    records = load_knowledge_records()
    if not records:
        return []

    document_features = [
        _features(f"{record.source} {record.text}") for record in records
    ]
    document_frequency: Counter[str] = Counter()
    for features in document_features:
        document_frequency.update(features.keys())

    query_features = _query_features(query_text)
    document_count = len(records)

    def weight(term: str, count: int) -> float:
        term_frequency = 1.0 + math.log(count)
        inverse_document_frequency = math.log(
            (document_count + 1) / (document_frequency[term] + 1)
        ) + 1.0
        return term_frequency * inverse_document_frequency

    query_weights = {
        term: weight(term, count)
        for term, count in query_features.items()
        if term in document_frequency
    }
    if not query_weights:
        return []
    query_norm = math.sqrt(sum(value * value for value in query_weights.values()))

    ranked: list[tuple[float, int]] = []
    for index, features in enumerate(document_features):
        document_weights = {
            term: weight(term, count)
            for term, count in features.items()
            if term in query_weights
        }
        if not document_weights:
            continue
        dot_product = sum(
            query_weights[term] * term_weight
            for term, term_weight in document_weights.items()
        )
        document_norm = math.sqrt(
            sum(weight(term, count) ** 2 for term, count in features.items())
        )
        if document_norm:
            score = dot_product / (query_norm * document_norm)
            if score > 0:
                ranked.append((score, index))

    ranked.sort(key=lambda result: result[0], reverse=True)
    return [
        RetrievedChunk(
            text=records[index].text,
            source=records[index].source,
            score=score,
        )
        for score, index in ranked[:top_k]
    ]


def _vector_retrieve(query_text: str, top_k: int) -> list[RetrievedChunk]:
    vector_store = load_index()
    matches = vector_store.similarity_search_with_score(query_text, k=top_k)
    return [
        RetrievedChunk(
            text=document.page_content,
            source=str(document.metadata.get("source", "unknown")),
            score=1.0 / (1.0 + max(float(distance), 0.0)),
        )
        for document, distance in matches
    ]


def retrieve(query: SemanticResult) -> list[RetrievedChunk]:
    config = load_config()
    top_k = config["retrieval"]["top_k"]
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("RAG retrieval.top_k must be a positive integer.")

    query_text = query.retrieval_query.strip()
    if not query_text:
        return []

    if selected_option(config) == "statistical":
        return _statistical_retrieve(query_text, top_k)
    return _vector_retrieve(query_text, top_k)
