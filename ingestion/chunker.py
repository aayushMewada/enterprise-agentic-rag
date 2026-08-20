import json
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import CHUNK_SIZE, CHUNK_OVERLAP, DATA_CHUNKS_DIR


def chunk_documents(documents: list[dict]) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    Path(DATA_CHUNKS_DIR).mkdir(parents=True, exist_ok=True)

    all_chunks = []
    for doc in documents:
        chunks = _chunk_pages(doc, splitter)
        if not chunks:
            chunks = _chunk_text(doc, splitter)

        _save_chunks(doc["source"], chunks)
        all_chunks.extend(chunks)
        print(f" Chunked: {doc['source']} -> {len(chunks)} chunks")

    return all_chunks


def _chunk_pages(doc: dict, splitter: RecursiveCharacterTextSplitter) -> list[dict]:
    chunks = []
    metadata = _source_metadata(doc["source"])

    for page in doc.get("pages", []):
        for split in splitter.split_text(page["text"]):
            chunks.append(
                {
                    "id": f"{doc['source']}_{len(chunks)}",
                    "text": split,
                    "source": doc["source"],
                    "page_start": page["page_number"],
                    **metadata,
                }
            )

    return chunks


def _chunk_text(doc: dict, splitter: RecursiveCharacterTextSplitter) -> list[dict]:
    metadata = _source_metadata(doc["source"])
    return [
        {
            "id": f"{doc['source']}_{i}",
            "text": split,
            "source": doc["source"],
            "page_start": None,
            **metadata,
        }
        for i, split in enumerate(splitter.split_text(doc["text"]))
    ]


def _source_metadata(source: str) -> dict:
    parts = Path(source).parts
    year = parts[0] if parts and re.fullmatch(r"\d{4}", parts[0]) else None
    company = _normalize_company(parts[1]) if len(parts) > 1 else None

    return {
        "year": year,
        "company": company,
    }


def _normalize_company(company: str) -> str:
    company = company.replace("_", " ")
    company = re.sub(r"\b\d{4}\b", "", company)
    company = re.sub(r"\s+", " ", company)
    return company.strip()


def _save_chunks(source: str, chunks: list[dict]):
    source_path = Path(source)
    out = Path(DATA_CHUNKS_DIR) / source_path.with_name(
        f"{source_path.stem}_chunks.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
