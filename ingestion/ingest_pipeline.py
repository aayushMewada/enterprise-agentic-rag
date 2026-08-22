from ingestion.chunker import chunk_documents
from ingestion.document_loader import load_documents
from retrieval.vector_store import add_chunks, create_index


def run_ingestion(data_dir: str = "data/raw"):
    print("\n=== Ingestion ===")
    docs = load_documents(data_dir)
    chunks = chunk_documents(docs)
    create_index()
    add_chunks(chunks)
    print(f"\nDone — {len(chunks)} chunks in Qdrant")


if __name__ == "__main__":
    run_ingestion()
