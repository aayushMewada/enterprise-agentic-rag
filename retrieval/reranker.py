from sentence_transformers import CrossEncoder

from config.settings import (
    MAX_CHUNKS_PER_SOURCE,
    RERANK_MODEL,
    RERANK_TOP_N,
    SOURCE_MATCH_BOOST,
)

_model = None  # lazy-loaded once


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(RERANK_MODEL)
    return _model


def rerank_chunks(
    query: str,
    chunks: list[dict],
    top_n: int = RERANK_TOP_N,
) -> list[dict]:
    model = _get_model()
    pairs = [(query, c["text"]) for c in chunks]
    scores = model.predict(pairs)

    for chunk, score in zip(chunks, scores):
        source_boost = _source_match_boost(query, chunk.get("source", ""))
        chunk["rerank_score"] = round(float(score) + source_boost, 4)
        chunk["source_boost"] = round(source_boost, 4)

    candidates = _prefer_source_matches(chunks, top_n=top_n)
    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    return _select_diverse_sources(ranked, top_n=top_n)


def _select_diverse_sources(chunks: list[dict], top_n: int) -> list[dict]:
    selected = []
    source_counts = {}

    for chunk in chunks:
        source = chunk.get("source")
        if source_counts.get(source, 0) >= MAX_CHUNKS_PER_SOURCE:
            continue

        selected.append(chunk)
        source_counts[source] = source_counts.get(source, 0) + 1

        if len(selected) == top_n:
            return selected

    selected_ids = {_chunk_identity(chunk) for chunk in selected}
    for chunk in chunks:
        if _chunk_identity(chunk) in selected_ids:
            continue

        selected.append(chunk)
        if len(selected) == top_n:
            break

    return selected


def _chunk_identity(chunk: dict):
    return chunk.get("chunk_id") or (chunk.get("source"), chunk.get("text"))


def _prefer_source_matches(chunks: list[dict], top_n: int) -> list[dict]:
    source_matches = [
        chunk
        for chunk in chunks
        if chunk.get("source_boost", 0.0) > 0.0
    ]

    if len(source_matches) >= top_n:
        return source_matches

    return chunks


def _source_match_boost(query: str, source: str) -> float:
    query_terms = _terms(query)
    source_terms = _terms(source)

    if not query_terms or not source_terms:
        return 0.0

    matches = query_terms & source_terms
    if not matches:
        return 0.0

    return SOURCE_MATCH_BOOST


def _terms(text: str) -> set[str]:
    import re

    stopwords = {
        "and",
        "for",
        "from",
        "prepare",
        "should",
        "the",
        "what",
        "with",
    }
    return {
        term
        for term in re.findall(r"[a-z0-9]+", text.lower())
        if len(term) >= 3 and term not in stopwords
    }
