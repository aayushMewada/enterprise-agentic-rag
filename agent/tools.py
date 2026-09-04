import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from rag.documents import list_documents
from retrieval.reranker import rerank_chunks
from retrieval.retriever import retrieve_chunks


ROOT = Path(__file__).resolve().parents[1]
REQUESTS_PATH = ROOT / "data" / "operations" / "requests.json"
TICKETS_SEED_PATH = ROOT / "data" / "operations" / "tickets_seed.json"
RUNTIME_TICKETS_PATH = ROOT / "data" / "runtime" / "tickets.json"


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


PolicyCitation = Annotated[
    str,
    Field(
        pattern=r"^SYN-[A-Z]{2,4}-\d{3} section \d+(?:\.\d+)?$",
        max_length=60,
    ),
]


class CreateFollowupTicketArguments(StrictToolArguments):
    request_id: str = Field(pattern=r"^REQ-\d{3,6}$")
    category: Literal["Documentation Follow-up"]
    priority: Literal["Normal", "High"]
    reason: str = Field(min_length=10, max_length=500)
    policy_citations: list[PolicyCitation] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def require_followup_policy_foundations(self):
        required = {
            "SYN-AO-001 section 2",
            "SYN-EX-003 section 1",
            "SYN-SLA-004 section 1",
            "SYN-SLA-004 section 2",
        }
        missing = sorted(required - set(self.policy_citations))
        if missing:
            raise ValueError(
                "A documentation follow-up proposal is missing required policy "
                f"citations: {', '.join(missing)}"
            )
        return self


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


def create_followup_ticket(
    request_id: str,
    category: str,
    priority: str,
    reason: str,
    policy_citations: list[str],
    _approval: dict,
) -> dict:
    """Create a synthetic ticket after the executor supplies approval context."""

    request_result = get_request_status(request_id)
    if not request_result["found"]:
        raise ValueError(f"Synthetic request {request_id} does not exist.")

    request = request_result["request"]
    if request.get("risk_flags"):
        raise ValueError(
            "A standard follow-up ticket cannot be created for a request with "
            "risk flags; human compliance escalation is required."
        )
    if request.get("status") != "Incomplete":
        raise ValueError(
            "A documentation follow-up ticket can be created only for an "
            "Incomplete request."
        )

    tickets = _load_runtime_tickets()
    duplicate = next(
        (
            ticket
            for ticket in tickets
            if ticket.get("request_id") == request_id
            and ticket.get("category") == category
            and ticket.get("status") in {"Open", "In Progress"}
        ),
        None,
    )
    if duplicate:
        raise ValueError(
            f"Open ticket {duplicate['ticket_id']} already exists for {request_id}."
        )

    ticket = {
        "ticket_id": _next_ticket_id(tickets),
        "request_id": request_id,
        "category": category,
        "priority": priority,
        "reason": reason,
        "policy_citations": policy_citations,
        "status": "Open",
        "approval_id": _approval["approval_id"],
        "approved_by": _approval["approved_by"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    tickets.append(ticket)
    _write_json(RUNTIME_TICKETS_PATH, tickets)
    return {
        "created": True,
        "ticket": ticket,
        "message": f"Synthetic ticket {ticket['ticket_id']} created.",
    }


def _load_runtime_tickets() -> list[dict]:
    if RUNTIME_TICKETS_PATH.exists():
        return json.loads(RUNTIME_TICKETS_PATH.read_text(encoding="utf-8"))
    return json.loads(TICKETS_SEED_PATH.read_text(encoding="utf-8"))


def _next_ticket_id(tickets: list[dict]) -> str:
    numbers = []
    for ticket in tickets:
        ticket_id = ticket.get("ticket_id", "")
        if ticket_id.startswith("TKT-") and ticket_id[4:].isdigit():
            numbers.append(int(ticket_id[4:]))
    return f"TKT-{max(numbers, default=1000) + 1}"


def _write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


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
    "create_followup_ticket": ToolSpec(
        name="create_followup_ticket",
        description=(
            "Prepare a Documentation Follow-up ticket for an Incomplete "
            "synthetic request with no risk flags. Supply the request ID, "
            "priority, concise reason, and supporting policy citations. This "
            "tool accepts only stable citations formatted like "
            "'SYN-AO-001 section 5'; never pass temporary evidence numbers. "
            "For this synthetic workflow include SYN-AO-001 section 2, "
            "SYN-EX-003 section 1, SYN-SLA-004 section 1, and SYN-SLA-004 "
            "section 2. "
            "This is a write operation: calling it creates a frozen proposal and "
            "requires separate explicit human approval before execution."
        ),
        arguments_model=CreateFollowupTicketArguments,
        handler=create_followup_ticket,
        requires_approval=True,
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


def execute_tool(
    name: str,
    arguments: dict[str, Any] | None,
    approval_context: dict | None = None,
) -> dict:
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

    validated_arguments = validated.model_dump(exclude_none=True)
    if spec.requires_approval and not approval_context:
        return {
            "ok": True,
            "executed": False,
            "status": "approval_required",
            "tool": name,
            "requires_approval": True,
            "proposal": validated_arguments,
        }

    try:
        handler_arguments = dict(validated_arguments)
        if spec.requires_approval:
            handler_arguments["_approval"] = approval_context
        data = spec.handler(**handler_arguments)
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
        "executed": True,
        "status": "completed",
        "tool": name,
        "requires_approval": spec.requires_approval,
        "data": data,
    }
