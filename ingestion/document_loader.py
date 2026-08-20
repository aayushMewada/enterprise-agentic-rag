from pathlib import Path
from pypdf import PdfReader
from config.settings import DATA_RAW_DIR, DATA_PROCESSED_DIR

SKIP_FILE_STEMS = {"example", "copy of example"}
SUPPORTED_SUFFIXES = {".pdf", ".txt"}


def load_documents(raw_dir: str = DATA_RAW_DIR) -> list[dict]:
    return load_documents_by_source(_iter_source_files(raw_dir).keys(), raw_dir=raw_dir)


def discover_sources(raw_dir: str = DATA_RAW_DIR) -> dict[str, dict]:
    return _iter_source_files(raw_dir)


def load_documents_by_source(
    sources: list[str] | set[str],
    raw_dir: str = DATA_RAW_DIR,
) -> list[dict]:
    documents = []
    raw_path = Path(raw_dir)

    Path(DATA_PROCESSED_DIR).mkdir(parents=True, exist_ok=True)

    for source in sorted(sources):
        file = raw_path / source

        if file.suffix.lower() == ".pdf":
            text, pages = _load_pdf(file)

        elif file.suffix.lower() == ".txt":
            text = file.read_text(encoding="utf-8")
            pages = []

        else:
            continue

        text, pages = _clean_document(text, pages)

        _save_processed(source, text)

        documents.append(
            {
                "source": source,
                "text": text,
                "pages": pages,
            }
        )

        print(f"Loaded: {source} ({len(text)} chars)")

    return documents


def _iter_source_files(raw_dir: str) -> dict[str, dict]:
    raw_path = Path(raw_dir)
    sources = {}

    for file in raw_path.rglob("*"):
        if not file.is_file():
            continue

        if file.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        source = file.relative_to(raw_path).as_posix()
        if file.stem.lower().strip() in SKIP_FILE_STEMS:
            print(f"Skipped template: {source}")
            continue

        stat = file.stat()
        sources[source] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }

    return sources


def _load_pdf(path: Path) -> tuple[str, list[dict]]:
    reader = PdfReader(str(path))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = _clean(page.extract_text() or "")
        if not page_text:
            continue

        pages.append(
            {
                "page_number": page_number,
                "text": page_text,
            }
        )

    text = "\n\n".join(page["text"] for page in pages)
    return text, pages


def _clean_document(text: str, pages: list[dict]) -> tuple[str, list[dict]]:
    if pages:
        return text, pages

    return _clean(text), pages


def _clean(text: str) -> str:
    import re

    text = text.encode("utf-8", errors="ignore").decode("utf-8")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = re.sub(r"(?<![.!?:;])\n(?!\s*(?:[-*•➢●]|\d+[.)]))", " ", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def _save_processed(source: str, text: str):
    out = Path(DATA_PROCESSED_DIR) / Path(source).with_suffix(".txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
