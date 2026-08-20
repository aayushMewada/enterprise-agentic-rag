from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk
import re

from ingestion.embedder import get_embedding_model
from config.settings import (
    OPENSEARCH_HOST,
    OPENSEARCH_PORT,
    OPENSEARCH_INDEX,
    EMBEDDING_DIM,
    TOP_K,
)


def _client():
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        use_ssl=False,
    )


SOURCE_FIELDS = [
    "text",
    "source",
    "page_start",
    "year",
    "company",
]
RRF_K = 60


def create_index():
    c = _client()
    if c.indices.exists(index=OPENSEARCH_INDEX):
        print(" Index already exists — skipping")
        return

    # Exact KNN — no method block needed
    c.indices.create(
        index=OPENSEARCH_INDEX,
        body={
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "source": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "page_start": {"type": "integer"},
                    "year": {"type": "keyword"},
                    "company": {"type": "keyword"},
                    "vector": {
                        "type": "knn_vector",
                        "dimension": EMBEDDING_DIM,
                        # no method block = exact KNN search
                    },
                }
            },
        },
    )
    print(f" Index '{OPENSEARCH_INDEX}' created with exact KNN")


def add_chunks(chunks: list[dict]):
    if not chunks:
        print(" 0 chunks to store in OpenSearch")
        return

    c = _client()
    model = get_embedding_model()
    texts = [ch["text"] for ch in chunks]
    print(f" Embedding {len(chunks)} chunk(s)")
    vectors = model.embed_documents(texts)
    print(" Writing chunks to OpenSearch with bulk indexing")

    actions = (
        {
            "_op_type": "index",
            "_index": OPENSEARCH_INDEX,
            "_id": chunk["id"],
            "_source": {
                "chunk_id": chunk["id"],
                "text": chunk["text"],
                "source": chunk["source"],
                "page_start": chunk.get("page_start"),
                "year": chunk.get("year"),
                "company": chunk.get("company"),
                "vector": vector,
            },
        }
        for chunk, vector in zip(chunks, vectors)
    )

    bulk(c, actions, chunk_size=500, request_timeout=120)
    c.indices.refresh(index=OPENSEARCH_INDEX)
    print(f" {len(chunks)} chunks stored in OpenSearch")


def vector_search(query: str, k: int = TOP_K, filters: dict | None = None) -> list[dict]:
    c = _client()
    model = get_embedding_model()
    vector = model.embed_query(query)
    knn_query = {"knn": {"vector": {"vector": vector, "k": k}}}

    res = c.search(
        index=OPENSEARCH_INDEX,
        body={
            "size": k,
            "query": _with_filters(knn_query, filters),
            "_source": SOURCE_FIELDS,
        },
    )

    return _format_hits(res, search_type="vector")


def keyword_search(query: str, k: int = TOP_K, filters: dict | None = None) -> list[dict]:
    c = _client()
    match_query = {
        "match": {
            "text": {
                "query": query,
                "operator": "or",
            }
        }
    }

    res = c.search(
        index=OPENSEARCH_INDEX,
        body={
            "size": k,
            "query": _with_filters(match_query, filters),
            "_source": SOURCE_FIELDS,
        },
    )

    return _format_hits(res, search_type="keyword")


def search(
    query: str,
    k: int = TOP_K,
    filters: dict | None = None,
) -> list[dict]:
    return hybrid_search(query, k=k, filters=filters)


def hybrid_search(
    query: str,
    k: int = TOP_K,
    filters: dict | None = None,
) -> list[dict]:
    filters = _merge_filters(_extract_filters(query), filters)
    if filters:
        print(f"  Applying metadata filters: {filters}")

    vector_results = vector_search(query, k=k, filters=filters)
    keyword_results = keyword_search(query, k=k, filters=filters)
    fused = {}

    for results in (vector_results, keyword_results):
        for rank, result in enumerate(results, start=1):
            chunk_id = result["chunk_id"]
            if chunk_id not in fused:
                fused[chunk_id] = {
                    **result,
                    "score": 0.0,
                    "vector_score": None,
                    "keyword_score": None,
                }

            fused[chunk_id]["score"] += 1 / (RRF_K + rank)
            if result["search_type"] == "vector":
                fused[chunk_id]["vector_score"] = result["score"]
            elif result["search_type"] == "keyword":
                fused[chunk_id]["keyword_score"] = result["score"]

    ranked = sorted(fused.values(), key=lambda item: item["score"], reverse=True)
    for result in ranked:
        result["score"] = round(result["score"], 6)
        result.pop("search_type", None)

    return ranked[:k]


def _format_hits(res, search_type: str) -> list[dict]:
    return [
        {
            "chunk_id": h["_id"],
            "text": h["_source"]["text"],
            "source": h["_source"]["source"],
            "page_start": h["_source"].get("page_start"),
            "year": h["_source"].get("year"),
            "company": h["_source"].get("company"),
            "score": round(h["_score"], 4),
            "search_type": search_type,
        }
        for h in res["hits"]["hits"]
    ]


def _with_filters(query: dict, filters: dict | None) -> dict:
    if not filters:
        return query

    filter_clauses = []
    if filters.get("year"):
        filter_clauses.append({"term": {"year": filters["year"]}})
    if filters.get("company"):
        filter_clauses.append({"term": {"company": filters["company"]}})

    if not filter_clauses:
        return query

    return {
        "bool": {
            "must": query,
            "filter": filter_clauses,
        }
    }


def _extract_filters(query: str) -> dict:
    filters = {}
    year_match = re.search(r"\b(20\d{2})\b", query)
    if year_match:
        filters["year"] = year_match.group(1)

    company = _extract_company(query)
    if company:
        filters["company"] = company

    return filters


def _merge_filters(parsed: dict, explicit: dict | None) -> dict:
    merged = dict(parsed)
    for key, value in (explicit or {}).items():
        if value:
            merged[key] = value
    return merged


def _extract_company(query: str) -> str | None:
    c = _client()
    res = c.search(
        index=OPENSEARCH_INDEX,
        body={
            "size": 0,
            "aggs": {
                "companies": {
                    "terms": {
                        "field": "company",
                        "size": 1000,
                    }
                }
            },
        },
    )

    query_norm = _normalize_for_match(query)
    matches = []
    for bucket in res["aggregations"]["companies"]["buckets"]:
        company = bucket["key"]
        company_norm = _normalize_for_match(company)
        if company_norm and company_norm in query_norm:
            matches.append(company)

    if not matches:
        return None

    return max(matches, key=len)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def delete_index():
    c = _client()
    if c.indices.exists(index=OPENSEARCH_INDEX):
        c.indices.delete(index=OPENSEARCH_INDEX)
        print(" Index deleted")


def delete_sources(sources: list[str]):
    if not sources:
        return

    c = _client()
    if not c.indices.exists(index=OPENSEARCH_INDEX):
        return

    res = c.delete_by_query(
        index=OPENSEARCH_INDEX,
        body={"query": {"terms": {"source": sources}}},
        refresh=True,
        conflicts="proceed",
    )
    print(f" Deleted {res.get('deleted', 0)} stale chunk(s) from OpenSearch")
