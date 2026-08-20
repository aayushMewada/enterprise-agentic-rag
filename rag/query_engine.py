from rag.catalog_router import answer_catalog_query
from generation.llm_client import get_answer, stream_answer
from generation.prompt_builder import build_prompt
from retrieval.reranker import rerank_chunks
from retrieval.retriever import retrieve_chunks
from config.settings import RERANK_TOP_N, TOP_K


def run_query(
    question: str,
    filters: dict | None = None,
    chat_history: list[dict] | None = None,
    include_prompt: bool = False,
) -> dict:
    direct = answer_catalog_query(question, filters)
    if direct:
        return direct

    raw = retrieve_chunks(question, k=TOP_K, filters=filters)
    ranked = rerank_chunks(question, raw, top_n=RERANK_TOP_N)
    prompt = build_prompt(question, ranked, chat_history=chat_history)

    answer = get_answer(prompt)
    answer = _fallback_if_false_refusal(answer, ranked)
    response = {
        "answer": answer,
        "sources": _sources_from_chunks(ranked),
        "chunks": ranked,
    }

    if include_prompt:
        response["prompt"] = prompt

    return response


def prepare_query(
    question: str,
    filters: dict | None = None,
    chat_history: list[dict] | None = None,
) -> dict:
    direct = answer_catalog_query(question, filters)
    if direct:
        return {
            **direct,
            "prompt": [],
        }

    raw = retrieve_chunks(question, k=TOP_K, filters=filters)
    ranked = rerank_chunks(question, raw, top_n=RERANK_TOP_N)
    prompt = build_prompt(question, ranked, chat_history=chat_history)
    return {
        "prompt": prompt,
        "sources": _sources_from_chunks(ranked),
        "chunks": ranked,
    }


def stream_query_answer(prompt: list[dict]):
    yield from stream_answer(prompt)


def answer_from_chunks_if_needed(answer: str, chunks: list[dict]) -> str:
    return _fallback_if_false_refusal(answer, chunks)


def build_debug_payload(
    question: str,
    filters: dict | None = None,
    chat_history: list[dict] | None = None,
) -> dict:
    return prepare_query(question, filters=filters, chat_history=chat_history)


def _sources_from_chunks(chunks: list[dict]) -> list[dict]:
    seen = set()
    sources = []

    for chunk in chunks:
        key = (chunk.get("source"), chunk.get("page_start"))
        if key in seen:
            continue

        seen.add(key)
        sources.append(
            {
                "source": chunk.get("source"),
                "page": chunk.get("page_start"),
                "year": chunk.get("year"),
                "company": chunk.get("company"),
                "score": chunk.get("score"),
                "rerank_score": chunk.get("rerank_score"),
            }
        )

    return sources


def _fallback_if_false_refusal(answer: str, chunks: list[dict]) -> str:
    if chunks and "don't have enough information" in answer.lower():
        chunk = chunks[0]
        citation = "[1]"
        return f"Based on the available source, {chunk.get('text', '').strip()} {citation}"

    return answer
