from retrieval.vector_store import search
from config.settings import TOP_K
from opensearchpy.exceptions import NotFoundError


def retrieve_chunks(
    query: str,
    k: int = TOP_K,
    filters: dict | None = None,
) -> list[dict]:
    try:
        print(f"  Querying OpenSearch: '{query}'")
        results = search(query, k=k, filters=filters)
        print(f"  Retrieved {len(results)} chunk(s)")
        return results
    except NotFoundError:
        print("  ERROR: No index found. Run --ingest first.")
        return []
