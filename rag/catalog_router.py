import re

from rag.documents import list_documents


def answer_catalog_query(question: str, filters: dict | None = None) -> dict | None:
    normalized = _normalize(question)
    filters = _merge_text_filters(normalized, filters or {})

    wants_companies = _is_company_catalog_query(normalized)
    wants_years = _is_year_catalog_query(normalized)
    wants_documents = _is_document_catalog_query(normalized)
    wants_count = _has_any(normalized, ["count", "how many", "number of", "total"])

    if wants_companies:
        return _company_answer(filters)

    if wants_years:
        return _year_answer(filters)

    if wants_documents:
        return _document_answer(filters, count_only=False)

    if wants_count and (filters.get("company") or filters.get("year")):
        return _document_answer(filters, count_only=True)

    return None


def _company_answer(filters: dict) -> dict:
    documents = _filter_documents(
        list_documents(),
        {"year": filters.get("year")},
    )
    companies = sorted({doc["company"] for doc in documents if doc.get("company")})
    year = filters.get("year")

    if not companies:
        scope = f" in {year}" if year else ""
        return _direct_response(f"No companies found{scope} in the document library.")

    scope = f" in {year}" if year else ""
    answer = f"Companies available{scope}:\n\n" + "\n".join(
        f"- {company}" for company in companies
    )
    return _direct_response(answer)


def _year_answer(filters: dict) -> dict:
    documents = _filter_documents(list_documents(), filters)
    years = sorted({doc["year"] for doc in documents if doc.get("year")})
    company = filters.get("company")

    if not years:
        scope = f" for {company}" if company else ""
        return _direct_response(f"No years found{scope} in the document library.")

    scope = f" for {company}" if company else ""
    answer = f"Years available{scope}:\n\n" + "\n".join(f"- {year}" for year in years)
    return _direct_response(answer)


def _document_answer(filters: dict, count_only: bool = False) -> dict:
    documents = _filter_documents(list_documents(), filters)

    if count_only:
        return _direct_response(f"Found {len(documents)} document(s) in the document library.")

    if not documents:
        return _direct_response("No matching documents found in the document library.")

    answer = "Matching documents:\n\n" + "\n".join(
        f"- {doc['source']}" for doc in documents
    )
    return _direct_response(answer)


def _filter_documents(documents: list[dict], filters: dict) -> list[dict]:
    year = filters.get("year")
    company = filters.get("company")

    if year:
        documents = [doc for doc in documents if doc.get("year") == year]
    if company:
        documents = [doc for doc in documents if doc.get("company") == company]

    return documents


def _direct_response(answer: str) -> dict:
    return {
        "answer": answer,
        "sources": [
            {
                "source": "Document library metadata",
                "page": None,
                "year": None,
                "company": None,
                "score": None,
                "rerank_score": None,
            }
        ],
        "chunks": [],
        "direct": True,
    }


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _is_company_catalog_query(text: str) -> bool:
    if _has_content_terms(text):
        return False

    return bool(
        re.search(r"\b(list|show)\s+(all\s+)?compan(y|ies)\b", text)
        or re.search(r"\b(which|what)\s+compan(y|ies)\b", text)
        or re.search(r"\bcompan(y|ies)\s+(available|present)\b", text)
    )


def _is_year_catalog_query(text: str) -> bool:
    if _has_content_terms(text):
        return False

    return bool(
        re.search(r"\b(list|show)\s+(all\s+)?years\b", text)
        or re.search(r"\b(which|what)\s+years\b", text)
        or re.search(r"\byears\s+(available|present)\b", text)
    )


def _is_document_catalog_query(text: str) -> bool:
    return bool(
        re.search(r"\b(list|show)\s+(all\s+)?(documents|pdfs|files)\b", text)
        or re.search(r"\b(which|what)\s+(documents|pdfs|files)\b", text)
    )


def _has_content_terms(text: str) -> bool:
    return _has_any(
        text,
        [
            "asked",
            "question",
            "questions",
            "dsa",
            "coding",
            "round",
            "rounds",
            "prepare",
            "interview",
            "experience",
            "hr",
            "technical",
        ],
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _merge_text_filters(normalized: str, filters: dict) -> dict:
    merged = dict(filters)
    year_match = re.search(r"\b(20\d{2})\b", normalized)
    if year_match and not merged.get("year"):
        merged["year"] = year_match.group(1)
    return merged
