# Enterprise Agentic RAG

A governed Retrieval-Augmented Generation system for a synthetic wealth-management operations workflow. The application combines semantic policy search with an LLM agent that can inspect operational requests, select tools, explain decisions with evidence, and propose actions that require explicit human approval.

This repository extends the original [Native RAG Pipeline](https://github.com/ironpateli/RAG) with agent orchestration, operational tools, approval controls, a FastAPI agent interface, browser-based review controls, synthetic banking data, and an evaluation suite.

> This is a portfolio demonstration built with synthetic policies and records. It is not connected to a bank, customer data, or a production ticketing system.

## Business use case

A banking operations employee can ask questions such as:

- Why is request `REQ-104` incomplete?
- Which policy applies to the missing document?
- What knowledge-base documents are available?
- Create a follow-up ticket for the missing documentation.

The agent decides which tool or tools are needed. Read-only tools execute immediately. A tool that changes operational state produces a frozen proposal and stops until a human reviewer approves or rejects it.

## RAG versus agentic RAG

The original RAG path always follows a fixed sequence:

```text
Question -> vector retrieval -> reranking -> prompt -> LLM answer
```

The agentic path selects a workflow according to the request:

```text
Employee request
      |
      v
LLM agent (bounded tool-selection loop)
      |
      +--> get_request_status ---------> synthetic operational record
      |
      +--> list_knowledge_documents ---> deterministic document inventory
      |
      +--> search_knowledge_base ------> embeddings -> Qdrant -> reranker
      |
      +--> create_followup_ticket -----> validation -> human approval
                                                    |
                                           approve / reject
                                                    |
                                      controlled runtime write
```

The LLM does not directly access files or write tickets. It can only request registered tools with validated arguments.

## Key capabilities

- Local sentence-transformer embeddings and Qdrant vector search
- Cross-encoder reranking before answer generation
- Groq-hosted LLM generation and tool calling
- Bounded agent loop with a maximum of five steps
- Strict Pydantic tool schemas and unknown-tool rejection
- Policy-grounded answers with source citations
- Deterministic routing for document-inventory questions
- Human-in-the-loop approval for state-changing actions
- Frozen approval proposals with a 30-minute expiry
- Approval and execution audit metadata
- Duplicate-ticket and risk-flag guardrails
- FastAPI endpoints and a browser approval interface
- Observable action traces without exposing private model reasoning
- Unit tests and scenario-based agent evaluations

## Synthetic demonstration data

The repository includes a fictional `Synthetic_Wealth_Management` knowledge base:

- Account-opening documentation policy
- Document-verification procedure
- Exception and escalation policy
- Ticket and service-level policy
- Responsible-AI usage policy

Synthetic request records such as `REQ-104` represent operational work items, not user prompts. For example, a request can contain documents received, missing-document issues, status, and risk flags. The agent reads these records through `get_request_status`.

A follow-up ticket is a synthetic operations task assigned after a request is found to be incomplete. Creating one changes application state, so the agent must present its exact proposed arguments for human approval before execution.

## Quick start

Detailed setup instructions are available in [HOW_TO_RUN.md](HOW_TO_RUN.md).

1. Copy `.env.example` to `.env`.
2. Run `npm install`, or create a Python virtual environment and install `requirements.txt`.
3. Add `GROQ_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION` to `.env`.
4. Run ingestion.
5. Start the API/browser interface or use the CLI.

```powershell
npm install
npm run ingest
npm run api
```

Open `http://127.0.0.1:8000/` after the API starts.

The first ingestion or query downloads the embedding and reranker models. Hugging Face authentication is optional but increases download rate limits.

## Demonstrating the agent

Ask a read-only operational question:

```powershell
venv\Scripts\python.exe main.py --agent "Check request REQ-104 and explain which policy applies."
```

Request a governed action:

```powershell
venv\Scripts\python.exe main.py --agent "Check REQ-105, find the applicable policy, and create a follow-up ticket for the invalid document."
```

The second command returns an approval ID instead of immediately writing a ticket. Review the frozen proposal and then make an explicit decision:

```powershell
venv\Scripts\python.exe main.py --approve APR-EXAMPLE --reviewer aayush
venv\Scripts\python.exe main.py --reject APR-EXAMPLE --reviewer aayush
```

Replace `APR-EXAMPLE` with the approval ID printed by the agent. An approval can execute only once.

## Original RAG mode

The fixed RAG pipeline remains available:

```powershell
npm run query -- "What documents are required for an individual account-opening request?"
```

In the browser, use the Mode selector to switch between Operations agent and RAG only.

## Evaluation

Run the deterministic unit-test suite:

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run one live agent scenario:

```powershell
venv\Scripts\python.exe evals\run_evals.py --scenario request_status_lookup
```

Run the complete scenario suite:

```powershell
venv\Scripts\python.exe evals\run_evals.py
```

The live evaluations measure public behavior rather than chain-of-thought:

- Required and forbidden tool usage
- Completion versus approval-required stop conditions
- Presence of a human approval boundary
- Risk-flag enforcement
- Non-empty final answers

Live evaluations call the configured Groq model, so exact tool paths can vary. Safety invariants are scored separately from optional extra read-only calls.

## Project structure

```text
agent/             Agent orchestrator, tools, validation, and approvals
api/               FastAPI routes for RAG, agent queries, and decisions
config/            Models, paths, and environment-backed configuration
data/
  raw/             Source documents, including the synthetic policy set
  operations/      Synthetic request and ticket seed records
  runtime/         Ignored local approvals and created tickets
evals/             Live agent scenarios and observable-behavior scorer
generation/        Prompt construction and Groq LLM client
ingestion/         Loading, chunking, embedding, and ingestion pipeline
rag/               RAG orchestration and deterministic catalog routing
retrieval/         Qdrant search and cross-encoder reranking
scripts/           Cross-platform Node.js setup and execution helpers
tests/             Unit and integration-style tests
web/               Browser chat, traces, citations, and approval controls
main.py            CLI entry point
```

## API endpoints

The FastAPI application includes:

| Endpoint | Purpose |
| --- | --- |
| `POST /agent/query` | Run the bounded operations agent |
| `POST /agent/approvals/{id}/approve` | Approve and execute a frozen proposal |
| `POST /agent/approvals/{id}/reject` | Reject a proposal without executing it |

The project also retains the original RAG query and streaming endpoints used by the browser interface.

## npm scripts

| Command | Purpose |
| --- | --- |
| `npm install` | Create `venv/` and install Python dependencies |
| `npm run ingest` | Load, chunk, embed, and store documents in Qdrant |
| `npm run api` | Start the local API and browser application |
| `npm run query -- "..."` | Run the fixed RAG pipeline |
| `npm run delete-index` | Delete the configured Qdrant collection |

Use the project virtual environment or the npm helpers. System Python may not contain the required packages.

## Technology stack

| Layer | Default |
| --- | --- |
| API and validation | FastAPI and Pydantic |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | Qdrant Cloud |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM and tool calling | Groq `openai/gpt-oss-120b` |
| Frontend | HTML, CSS, and JavaScript |
| Evaluation | Python `unittest` and live scenario assertions |

Configuration lives in `config/settings.py` and environment variables.

## Deployment mode

For a hosted read-only demonstration, set:

```env
QUERY_ONLY_MODE=true
```

Query-only mode disables approval execution and document mutation through the application. Ingest documents locally and store their chunks in Qdrant before deploying the query service.

## Safety boundaries and limitations

- All included policies, request records, and tickets are synthetic.
- Reviewer names are demonstration metadata, not authenticated identities.
- Runtime JSON files demonstrate controlled state changes but are not a transactional production database.
- Approval state is local to one application deployment.
- LLM outputs can vary and must remain subject to validation and human review.
- Production use would require authentication, role-based authorization, encrypted audit storage, concurrency control, monitoring, prompt-injection testing, and integration with approved banking systems.
- Secrets belong only in `.env`; never commit API keys.

## Attribution and author

Agentic upgrade and portfolio implementation: [Aayush Mewada](https://github.com/aayushMewada)

Based on the [Native RAG Pipeline](https://github.com/ironpateli/RAG) by its original contributor. The upstream project supplied the initial RAG foundation; this repository documents the additional agent, governance, API, UI, synthetic workflow, tests, and evaluations built on top of it.
