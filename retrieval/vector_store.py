import re
import time
import uuid
from threading import Lock

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from ingestion.embedder import get_embedding_model
from config.settings import (
    EMBEDDING_DIM,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
    TOP_K,
)

_DOCUMENT_CACHE = {
    "loaded_at": 0.0,
    "documents": None,
}
_DOCUMENT_CACHE_LOCK = Lock()
_DOCUMENT_CACHE_TTL_SECONDS = 300


def _client() -> QdrantClient:
    if not QDRANT_URL:
        raise RuntimeError("QDRANT_URL is not set. Add it to your .env file.")
    if not QDRANT_API_KEY:
        raise RuntimeError("QDRANT_API_KEY is not set. Add it to your .env file.")

    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def create_index():
    c = _client()
    if c.collection_exists(QDRANT_COLLECTION):
        _create_payload_indexes(c)
        print(" Qdrant collection already exists - skipping")
        return

    c.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    _create_payload_indexes(c)
    print(f" Qdrant collection '{QDRANT_COLLECTION}' created")


def add_chunks(chunks: list[dict]):
    if not chunks:
        print(" 0 chunks to store in Qdrant")
        return

    create_index()
    c = _client()
    model = get_embedding_model()
    texts = [ch["text"] for ch in chunks]
    print(f" Embedding {len(chunks)} chunk(s)")
    vectors = model.embed_documents(texts)
    print(" Writing chunks to Qdrant")

    points = [
        PointStruct(
            id=_point_id(chunk["id"]),
            vector=vector,
            payload={
                "chunk_id": chunk["id"],
                "text": chunk["text"],
                "source": chunk["source"],
                "page_start": chunk.get("page_start"),
                "year": chunk.get("year"),
                "company": chunk.get("company"),
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]

    c.upload_points(
        collection_name=QDRANT_COLLECTION,
        points=points,
        batch_size=256,
        wait=True,
    )
    _clear_document_cache()
    print(f" {len(chunks)} chunks stored in Qdrant")


def search(
    query: str,
    k: int = TOP_K,
    filters: dict | None = None,
) -> list[dict]:
    return vector_search(query, k=k, filters=filters)


def vector_search(query: str, k: int = TOP_K, filters: dict | None = None) -> list[dict]:
    filters = _merge_filters(_extract_filters(query), filters)
    if filters:
        print(f"  Applying metadata filters: {filters}")

    c = _client()
    model = get_embedding_model()
    vector = model.embed_query(query)

    res = c.query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        query_filter=_to_qdrant_filter(filters),
        with_payload=True,
        limit=k,
    ).points

    return [_format_point(point) for point in res]


def delete_index():
    c = _client()
    if c.collection_exists(QDRANT_COLLECTION):
        c.delete_collection(QDRANT_COLLECTION)
        _clear_document_cache()
        print(" Qdrant collection deleted")


def delete_sources(sources: list[str]):
    if not sources:
        return

    c = _client()
    if not c.collection_exists(QDRANT_COLLECTION):
        return

    c.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchAny(any=sources),
                    )
                ]
            )
        ),
        wait=True,
    )
    _clear_document_cache()
    print(f" Deleted stale chunk(s) from Qdrant for {len(sources)} source file(s)")


def list_indexed_documents() -> list[dict]:
    cached = _get_document_cache()
    if cached is not None:
        return cached

    with _DOCUMENT_CACHE_LOCK:
        cached = _get_document_cache()
        if cached is not None:
            return cached

        documents = _load_indexed_documents()
        _DOCUMENT_CACHE["loaded_at"] = time.time()
        _DOCUMENT_CACHE["documents"] = documents
        return documents


def _load_indexed_documents() -> list[dict]:
    c = _client()
    if not c.collection_exists(QDRANT_COLLECTION):
        return []

    documents = {}
    offset = None
    while True:
        points, offset = c.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=None,
            limit=1000,
            offset=offset,
            with_payload=["source", "year", "company"],
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            source = payload.get("source")
            if not source or source in documents:
                continue

            documents[source] = {
                "source": source,
                "year": payload.get("year"),
                "company": payload.get("company"),
                "size": None,
                "mtime_ns": None,
                "storage": "qdrant",
            }

        if offset is None:
            break

    return sorted(documents.values(), key=lambda doc: doc["source"])


def indexed_metadata_options() -> dict:
    documents = list_indexed_documents()
    years = sorted({doc["year"] for doc in documents if doc["year"]})
    companies = sorted({doc["company"] for doc in documents if doc["company"]})
    return {"years": years, "companies": companies}


def _format_point(point) -> dict:
    payload = point.payload or {}
    return {
        "chunk_id": payload.get("chunk_id") or str(point.id),
        "text": payload.get("text", ""),
        "source": payload.get("source"),
        "page_start": payload.get("page_start"),
        "year": payload.get("year"),
        "company": payload.get("company"),
        "score": round(float(point.score or 0.0), 6),
    }


def _to_qdrant_filter(filters: dict | None) -> Filter | None:
    if not filters:
        return None

    must = []
    if filters.get("year"):
        must.append(FieldCondition(key="year", match=MatchValue(value=filters["year"])))
    if filters.get("company"):
        must.append(
            FieldCondition(key="company", match=MatchValue(value=filters["company"]))
        )

    if not must:
        return None

    return Filter(must=must)


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
    query_norm = _normalize_for_match(query)
    matches = []
    for company in _known_companies():
        company_norm = _normalize_for_match(company)
        if company_norm and company_norm in query_norm:
            matches.append(company)

    if not matches:
        return None

    return max(matches, key=len)


def _known_companies() -> set[str]:
    return {doc["company"] for doc in list_indexed_documents() if doc.get("company")}


def _create_payload_indexes(c: QdrantClient):
    for field in ("source", "year", "company"):
        try:
            c.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=field,
                field_schema="keyword",
            )
        except Exception:
            pass


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _get_document_cache() -> list[dict] | None:
    documents = _DOCUMENT_CACHE["documents"]
    if documents is None:
        return None

    if time.time() - _DOCUMENT_CACHE["loaded_at"] > _DOCUMENT_CACHE_TTL_SECONDS:
        return None

    return documents


def _clear_document_cache():
    with _DOCUMENT_CACHE_LOCK:
        _DOCUMENT_CACHE["loaded_at"] = 0.0
        _DOCUMENT_CACHE["documents"] = None
