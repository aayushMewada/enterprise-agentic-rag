from retrieval.vector_store import search
from config.settings import TOP_K


def retrieve_chunks(
    query: str,
    k: int = TOP_K,
    filters: dict | None = None,
) -> list[dict]:
    try:
        print(f"  Querying vector store: '{query}'")
        results = search(query, k=k, filters=filters)
        print(f"  Retrieved {len(results)} chunk(s)")
        return results
    except Exception as exc:
        print(f"  ERROR: Vector search failed: {exc}")
        return []
