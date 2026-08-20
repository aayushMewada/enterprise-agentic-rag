from pathlib import Path
import re

from config.settings import DATA_RAW_DIR
from ingestion.chunker import chunk_documents
from ingestion.document_loader import discover_sources, load_documents_by_source
from ingestion.manifest import diff_sources, load_manifest, save_manifest
from retrieval.vector_store import add_chunks, create_index, delete_index, delete_sources


def list_documents() -> list[dict]:
    sources = discover_sources(DATA_RAW_DIR)
    return [
        {
            "source": source,
            "year": _year_from_source(source),
            "company": _company_from_source(source),
            "size": fingerprint["size"],
            "mtime_ns": fingerprint["mtime_ns"],
        }
        for source, fingerprint in sorted(sources.items())
    ]


def metadata_options() -> dict:
    documents = list_documents()
    years = sorted({doc["year"] for doc in documents if doc["year"]})
    companies = sorted({doc["company"] for doc in documents if doc["company"]})
    return {"years": years, "companies": companies}


def ingest_changed_documents() -> dict:
    create_index()
    current_manifest = discover_sources(DATA_RAW_DIR)
    previous_manifest = load_manifest()
    changed_sources, deleted_sources = diff_sources(current_manifest, previous_manifest)

    if deleted_sources:
        delete_sources(deleted_sources)

    if changed_sources and previous_manifest:
        delete_sources(changed_sources)

    chunks = []
    if changed_sources:
        documents = load_documents_by_source(changed_sources, raw_dir=DATA_RAW_DIR)
        chunks = chunk_documents(documents)
        add_chunks(chunks)

    save_manifest(current_manifest)
    return {
        "changed_sources": changed_sources,
        "deleted_sources": deleted_sources,
        "chunks_added": len(chunks),
    }


def save_upload(filename: str, content: bytes, year: str, company: str) -> dict:
    safe_filename = _safe_filename(filename)
    safe_year = _safe_part(year)
    safe_company = _safe_part(company)
    if not safe_filename.lower().endswith((".pdf", ".txt")):
        raise ValueError("Only PDF and TXT files are supported.")
    if not safe_year or not safe_company:
        raise ValueError("Year and company are required.")

    target = Path(DATA_RAW_DIR) / safe_year / safe_company / safe_filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    result = ingest_changed_documents()
    return {"source": target.relative_to(DATA_RAW_DIR).as_posix(), **result}


def remove_document(source: str, delete_file: bool = True) -> dict:
    source = _safe_source(source)
    raw_file = Path(DATA_RAW_DIR) / source

    if delete_file and raw_file.exists():
        raw_file.unlink()

    delete_sources([source])
    current_manifest = discover_sources(DATA_RAW_DIR)
    save_manifest(current_manifest)
    return {"source": source, "deleted_file": delete_file}


def remove_all_documents(delete_files: bool = False) -> dict:
    delete_index()

    deleted_files = 0
    if delete_files:
        raw_root = Path(DATA_RAW_DIR).resolve()
        for file in raw_root.rglob("*"):
            if file.is_file() and file.suffix.lower() in {".pdf", ".txt"}:
                if raw_root not in file.resolve().parents:
                    continue
                file.unlink()
                deleted_files += 1

    save_manifest(discover_sources(DATA_RAW_DIR))
    return {"index_deleted": True, "deleted_files": deleted_files}


def _year_from_source(source: str) -> str | None:
    parts = Path(source).parts
    return parts[0] if parts and re.fullmatch(r"\d{4}", parts[0]) else None


def _company_from_source(source: str) -> str | None:
    parts = Path(source).parts
    if len(parts) < 2:
        return None
    company = parts[1].replace("_", " ")
    company = re.sub(r"\b\d{4}\b", "", company)
    return re.sub(r"\s+", " ", company).strip()


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9 ._()-]+", "_", name).strip()


def _safe_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9 _.-]+", "_", value).strip()


def _safe_source(source: str) -> str:
    source_path = Path(source)
    if source_path.is_absolute() or ".." in source_path.parts:
        raise ValueError("Invalid source path.")
    return source_path.as_posix()
