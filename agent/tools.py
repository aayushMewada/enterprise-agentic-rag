import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from rag.documents import list_documents
from retrieval.reranker import rerank_chunks
from retrieval.retriever import retrieve_chunks


ROOT = Path(__file__).resolve().parents[1]
REQUESTS_PATH = ROOT / "data" / "operations" / "requests.json"


class StrictToolArguments(BaseModel):
    """Reject arguments the selected tool did not declare."""

    model_config = ConfigDict(extra="forbid")


class SearchKnowledgeBaseArguments(StrictToolArguments):
    query: str = Field(min_length=3, max_length=1000)
    year: str | None = Field(default=None, pattern=r"^20\d{2}$")
    company: str | None = Field(default=None, min_length=2, max_length=100)


class ListKnowledgeDocumentsArguments(StrictToolArguments):
    year: str | None = Field(default=None, pattern=r"^20\d{2}$")
    company: str | None = Field(default=None, min_length=2, max_length=100)


class GetRequestStatusArguments(StrictToolArguments):
    request_id: str = Field(pattern=r"^REQ-\d{3,6}$")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    arguments_model: type[StrictToolArguments]
    handler: Callable[..., dict]
    requires_approval: bool = False


def search_knowledge_base(
    query: str,
    year: str | None = None,
    company: str | None = None,
) -> dict:
    """Retrieve evidence without asking the LLM to generate an answer."""

    filters = {
        key: value
        for key, value in {"year": year, "company": company}.items()
        if value
    }
    candidates = retrieve_chunks(query, filters=filters)
    if not candidates:
        return {
            "query": query,
            "evidence": [],
            "message": "No relevant knowledge-base evidence was retrieved.",
        }

    ranked = rerank_chunks(query, candidates, top_n=5)
    evidence = [
        {
            "citation_id": index,
            "text": chunk.get("text", ""),
            "source": chunk.get("source"),
            "page": chunk.get("page_start"),
            "year": chunk.get("year"),
            "company": chunk.get("company"),
            "vector_score": chunk.get("score"),
            "rerank_score": chunk.get("rerank_score"),
        }
        for index, chunk in enumerate(ranked, start=1)
    ]
    return {
        "query": query,
        "filters": filters,
        "evidence": evidence,
        "message": f"Retrieved {len(evidence)} evidence chunk(s).",
    }


def list_knowledge_documents(
    year: str | None = None,
    company: str | None = None,
) -> dict:
    documents = list_documents()
    if year:
        documents = [doc for doc in documents if doc.get("year") == year]
    if company:
        company_normalized = company.casefold().strip()
        documents = [
            doc
            for doc in documents
            if (doc.get("company") or "").casefold() == company_normalized
        ]

    return {
        "documents": [
            {
                "source": doc.get("source"),
                "year": doc.get("year"),
                "company": doc.get("company"),
            }
            for doc in documents
        ],
        "count": len(documents),
    }


def get_request_status(request_id: str) -> dict:
    requests = json.loads(REQUESTS_PATH.read_text(encoding="utf-8"))
    normalized_id = request_id.upper()
    request = next(
        (item for item in requests if item.get("request_id") == normalized_id),
        None,
    )

    if request is None:
        return {
            "found": False,
            "request_id": normalized_id,
            "message": "No synthetic request exists with that ID.",
        }

    return {
        "found": True,
        "request": request,
        "message": f"Synthetic request {normalized_id} retrieved.",
    }


TOOL_REGISTRY = {
    "search_knowledge_base": ToolSpec(
        name="search_knowledge_base",
        description=(
            "Search the synthetic policy and procedure knowledge base. Use this "
            "for questions about required documents, verification procedures, "
            "exceptions, escalation, ticket rules, service levels, responsible "
            "AI controls, or other policy evidence."
        ),
        arguments_model=SearchKnowledgeBaseArguments,
        handler=search_knowledge_base,
    ),
    "list_knowledge_documents": ToolSpec(
        name="list_knowledge_documents",
        description=(
            "List the synthetic knowledge documents currently available. Use "
            "this only for document inventory questions, not policy questions."
        ),
        arguments_model=ListKnowledgeDocumentsArguments,
        handler=list_knowledge_documents,
    ),
    "get_request_status": ToolSpec(
        name="get_request_status",
        description=(
            "Retrieve the current status, received documents, document issues, "
            "and risk flags for a synthetic request ID such as REQ-104. This is "
            "a read-only operation."
        ),
        arguments_model=GetRequestStatusArguments,
        handler=get_request_status,
    ),
}


def get_tool_schemas() -> list[dict]:
    """Return OpenAI-compatible function schemas accepted by Groq."""

    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.arguments_model.model_json_schema(),
            },
        }
        for spec in TOOL_REGISTRY.values()
    ]


def execute_tool(name: str, arguments: dict[str, Any] | None) -> dict:
    """Validate and execute one registered tool with a stable result envelope."""

    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        return {
            "ok": False,
            "tool": name,
            "error": {
                "code": "unknown_tool",
                "message": f"Tool '{name}' is not registered.",
            },
        }

    try:
        validated = spec.arguments_model.model_validate(arguments or {})
    except ValidationError as exc:
        return {
            "ok": False,
            "tool": name,
            "error": {
                "code": "invalid_arguments",
                "message": "Tool arguments failed validation.",
                "details": exc.errors(include_url=False),
            },
        }

    try:
        data = spec.handler(**validated.model_dump(exclude_none=True))
    except Exception as exc:
        return {
            "ok": False,
            "tool": name,
            "error": {
                "code": "tool_execution_failed",
                "message": str(exc),
            },
        }

    return {
        "ok": True,
        "tool": name,
        "requires_approval": spec.requires_approval,
        "data": data,
    }
