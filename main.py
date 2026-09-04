from dotenv import load_dotenv
import json
import sys

from agent.approvals import approve_pending_action, reject_pending_action
from agent.orchestrator import run_agent
from ingestion.chunker import chunk_documents
from ingestion.document_loader import discover_sources, load_documents_by_source
from ingestion.manifest import diff_sources, load_manifest, save_manifest
from rag.query_engine import build_debug_payload, run_query
from retrieval.vector_store import add_chunks, create_index, delete_sources

load_dotenv()


def ingest(data_dir: str = "data/raw"):
    """
    Run once to load, chunk, embed and store your documents.
    Re-run whenever you add new documents.
    """
    print("--- Starting ingestion ---")

    create_index()

    current_manifest = discover_sources(data_dir)
    previous_manifest = load_manifest()
    changed_sources, deleted_sources = diff_sources(
        current_manifest,
        previous_manifest,
    )

    print(f"Discovered {len(current_manifest)} source file(s)")
    print(f"Changed/new: {len(changed_sources)}")
    print(f"Deleted: {len(deleted_sources)}")

    if deleted_sources:
        delete_sources(deleted_sources)

    if not changed_sources:
        save_manifest(current_manifest)
        print("No new or changed documents to ingest.\n")
        return

    if previous_manifest:
        delete_sources(changed_sources)

    documents = load_documents_by_source(changed_sources, raw_dir=data_dir)
    print(f"Loaded {len(documents)} changed/new document(s)")

    chunks = chunk_documents(documents)
    print(f"Created {len(chunks)} chunk(s)")

    add_chunks(chunks)
    save_manifest(current_manifest)

    print("Ingestion complete. Chunks stored in Qdrant.\n")


def query(question: str, show_prompt: bool = False) -> str:
    if show_prompt:
        payload = build_debug_payload(question)
        _print_debug_prompt(payload["chunks"], payload["prompt"])
        return ""

    result = run_query(question)
    answer = result["answer"]
    _safe_print(f"\nAnswer: {answer}")
    return answer


def agent_query(message: str) -> str:
    result = run_agent(message)

    _safe_print("\n--- Agent action trace ---")
    if not result["trace"]:
        _safe_print("No tools called.")
    for event in result["trace"]:
        _safe_print(json.dumps(event, ensure_ascii=False))

    for approval in result.get("pending_approvals", []):
        _safe_print("\n--- Pending approval ---")
        _safe_print(json.dumps(approval, indent=2, ensure_ascii=False))

    answer = result["answer"]
    _safe_print(f"\nAgent answer: {answer}")
    return answer


def review_action(approval_id: str, reviewer: str, approve: bool):
    if approve:
        result = approve_pending_action(approval_id, approved_by=reviewer)
    else:
        result = reject_pending_action(approval_id, rejected_by=reviewer)
    _safe_print(json.dumps(result, indent=2, ensure_ascii=False))


def _print_debug_prompt(chunks: list[dict], prompt: list[dict]):
    print("\n--- Selected chunks ---")
    for i, chunk in enumerate(chunks, 1):
        print(
            f"[{i}] source={chunk.get('source')} "
            f"page={chunk.get('page_start')} "
            f"score={chunk.get('score')} "
            f"rerank_score={chunk.get('rerank_score')} "
            f"source_boost={chunk.get('source_boost')}"
        )

    print("\n--- Prompt messages ---")
    for message in prompt:
        _safe_print(f"\n{message['role'].upper()}:\n{message['content']}")


def _safe_print(text: str):
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Native RAG Pipeline")
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Run document ingestion (do this first)",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Ask a question against your documents",
    )
    parser.add_argument(
        "--agent",
        type=str,
        help="Run the bounded operations agent with registered tools",
    )
    parser.add_argument(
        "--approve",
        type=str,
        help="Approve and execute one persisted action by approval ID",
    )
    parser.add_argument(
        "--reject",
        type=str,
        help="Reject one persisted action by approval ID",
    )
    parser.add_argument(
        "--reviewer",
        type=str,
        default="synthetic-reviewer",
        help="Synthetic reviewer name recorded with an approval decision",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Print selected chunks and prompt without calling the LLM",
    )
    args = parser.parse_args()

    if args.ingest:
        ingest()
    elif args.approve:
        review_action(args.approve, reviewer=args.reviewer, approve=True)
    elif args.reject:
        review_action(args.reject, reviewer=args.reviewer, approve=False)
    elif args.agent:
        agent_query(args.agent)
    elif args.query:
        query(args.query, show_prompt=args.show_prompt)
    else:
        print("Usage:")
        print("  python main.py --ingest")
        print("  python main.py --query 'Your question here'")
        print("  python main.py --agent 'Check request REQ-104'")
        print("  python main.py --approve APR-12345678 --reviewer demo-user")
        print("  python main.py --reject APR-12345678 --reviewer demo-user")
