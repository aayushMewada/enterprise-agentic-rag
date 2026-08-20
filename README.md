# Native RAG Pipeline

A Retrieval-Augmented Generation (RAG) pipeline for job interview experiences. It uses local embeddings/OpenSearch for retrieval and Groq for hosted LLM answers.

Works on **Windows**, **macOS**, and **Linux**.

## Quick start

Full step-by-step instructions (setup, Docker OpenSearch, ingest, query, troubleshooting):

**→ [HOW_TO_RUN.md](HOW_TO_RUN.md)**

Short version:

1. Copy `.env.example` → `.env`
2. `npm install` (creates `venv/` and installs deps) **or** create `venv` and `pip install -r requirements.txt`
3. Add `GROQ_API_KEY` to `.env`
4. Start OpenSearch with Docker (`DISABLE_SECURITY_PLUGIN=true`) — see [HOW_TO_RUN.md](HOW_TO_RUN.md)
5. Put PDFs/txt in `data/raw/`
6. `npm run ingest`, then `npm run api` for the GUI or `npm run query -- "Your question"`

## Project structure

```
rag-pipeline/
│
├── config/
│   └── settings.py              ← chunk size, model names, paths
│
├── data/
│   ├── raw/                     ← drop PDFs and txt files here
│   ├── processed/               ← cleaned text (generated)
│   └── chunks/                  ← chunked JSON (generated)
│
├── ingestion/
│   ├── document_loader.py       ← PDF / txt loading
│   ├── chunker.py               ← text splitting
│   ├── embedder.py              ← sentence-transformers embeddings
│   └── ingest_pipeline.py       ← load → chunk → embed → store
│
├── retrieval/
│   ├── vector_store.py          ← OpenSearch index + KNN search
│   ├── retriever.py             ← query embedding + search
│   └── reranker.py              ← cross-encoder reranking
│
├── generation/
│   ├── prompt_builder.py        ← prompt assembly
│   └── llm_client.py            ← Groq API
│
├── scripts/
│   ├── setup-python-env.js      ← creates venv + installs deps
│   └── run-python.js            ← runs Python inside venv
│
├── main.py                      ← CLI: --ingest / --query
├── HOW_TO_RUN.md                ← detailed run instructions
├── .env.example                 ← env template (copy to .env)
├── requirements.txt
└── package.json                 ← npm helpers for setup / ingest / query
```

## Prerequisites

| Tool | Purpose |
|------|---------|
| Python 3.10+ | Pipeline runtime |
| Node.js (optional) | `npm install` / `npm run ingest` convenience scripts |
| Docker Desktop | OpenSearch (HTTP on port 9200, security disabled) |
| Groq API key | Hosted LLM for answers |

## npm scripts

| Command | What it does |
|---------|----------------|
| `npm install` | Creates `venv/` and installs Python deps |
| `npm run ingest` | Load → chunk → embed → store into OpenSearch |
| `npm run api` | Start the local browser GUI/API |
| `npm run query -- "..."` | Retrieve + rerank + answer via Groq |
| `npm run delete-index` | Delete the `rag_index` OpenSearch index |

Always use the project `venv` (or these npm scripts). System Python will fail with missing packages.

## Stack

| Layer | Default |
|-------|---------|
| Embeddings | `all-MiniLM-L6-v2` (local) |
| Vector store | OpenSearch 2.x KNN |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM | Groq `openai/gpt-oss-120b` |

Config lives in `config/settings.py`. Groq model and OpenSearch host/port can be overridden in `.env`.

## Important notes

- OpenSearch must be reachable at **http://localhost:9200** (plain HTTP). A ZIP/native install with TLS/security on will not work with the default client.
- Do not start a second OpenSearch on port 9200 (e.g. `C:\opensearch-…`) while the Docker container is running.
- `GROQ_API_KEY` must be set in `.env` before asking LLM-backed questions.
- First ingest/query downloads embedding and reranker models (hundreds of MB). That is expected once.
- Wipe the index before re-ingesting if documents changed (`npm run delete-index`).

## Author

Atharva — GitHub
