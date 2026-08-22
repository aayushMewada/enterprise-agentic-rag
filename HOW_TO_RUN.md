# How to Run

Step-by-step guide to set up and run this RAG pipeline locally.

## Prerequisites

Install these first:

| Tool | Notes |
|------|--------|
| **Python 3.10+** | Windows: enable **Add Python to PATH** during install |
| **Node.js** (optional) | Needed only if you want `npm` scripts |
| **Groq API key** | Needed for LLM answers |
| **Qdrant Cloud account** | Needed for hosted vector search |

## One-time setup

### 1. Clone / open the repo

```powershell
cd RAG-Pipeline
```

### 2. Create `.env`

```powershell
# Windows
Copy-Item .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

Defaults:

```
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=openai/gpt-oss-120b
LLM_MAX_TOKENS=3000
QDRANT_URL=https://your-qdrant-cluster-url
QDRANT_API_KEY=your_qdrant_api_key_here
QDRANT_COLLECTION=rag_chunks
QUERY_ONLY_MODE=false
```

### 3. Install Python dependencies

**Option A — npm (recommended)**

```bash
npm install
```

This creates `venv/` and installs packages from `requirements.txt`.

**Option B — Python only**

```powershell
# Windows
py -3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Add your Groq API key

Create a free Groq API key at https://console.groq.com/keys, then put it in `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=openai/gpt-oss-120b
LLM_MAX_TOKENS=3000
```

### 5. Add your Qdrant Cloud details

Create a free Qdrant Cloud cluster, then put these in `.env`:

```env
QDRANT_URL=https://your-qdrant-cluster-url
QDRANT_API_KEY=your_qdrant_api_key_here
QDRANT_COLLECTION=rag_chunks
QUERY_ONLY_MODE=false
```

---

## Every session — run in this order

### Terminal 1 — Ingest, query, and GUI

Put PDFs or `.txt` files in `data/raw/`.

**With npm (uses the project `venv` automatically):**

```bash
npm run ingest
npm run query -- "Your question here"
npm run api
```

**With Python (activate `venv` first):**

```powershell
# Windows
venv\Scripts\activate
python main.py --ingest
python main.py --query "Your question here"
```

```bash
# macOS / Linux
source venv/bin/activate
python main.py --ingest
python main.py --query "Your question here"
```

> **Important:** Do not run `python main.py` with system Python. You need the project `venv` (or `npm run …`), or you will get errors like `No module named 'dotenv'`.

---

## Managing documents

| Task | What to do |
|------|------------|
| Add documents | Drop files into `data/raw/`, then ingest |
| Refresh after changes | Wipe the index, then ingest again |
| Wipe index | `npm run delete-index` |

Wipe then re-ingest (avoids duplicate/stale chunks):

```bash
npm run delete-index
npm run ingest
```

Or with the venv activated:

```bash
python -c "from retrieval.vector_store import delete_index; delete_index()"
python main.py --ingest
```

---

## Common issues

| Symptom | Cause | Fix |
|---------|--------|-----|
| `No module named 'dotenv'` | System Python, not `venv` | `venv\Scripts\activate` or `npm run ingest` |
| Query fails with `GROQ_API_KEY is not set` | Missing Groq key | Add `GROQ_API_KEY=...` to `.env` |
| Query or ingest fails with `QDRANT_URL` / `QDRANT_API_KEY` | Missing Qdrant config | Add Qdrant values to `.env` |
| Groq rate limit error | Free-tier request/token limit hit | Wait and retry, or switch to a lighter Groq model |
| First ingest is slow | Downloading embedding/reranker models | One-time download; later runs are faster |

---

## Quick reference

```bash
npm run ingest
npm run api
npm run query -- "What is this document about?"
npm run delete-index
```

## Query-only deployment

For the first hosted version, set this on the hosting platform:

```env
QUERY_ONLY_MODE=true
```

Use this when Qdrant already has your indexed chunks and the hosted app should only answer questions. Upload/delete controls are disabled, and filters/document inventory are read from Qdrant metadata instead of `data/raw`.
