# How to Run

Step-by-step guide to set up and run this RAG pipeline locally.

## Prerequisites

Install these first:

| Tool | Notes |
|------|--------|
| **Python 3.10+** | Windows: enable **Add Python to PATH** during install |
| **Node.js** (optional) | Needed only if you want `npm` scripts |
| **Docker Desktop** | Must be running before you start OpenSearch |
| **Ollama** | Needed for `--query` answers |

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
OLLAMA_BASE_URL=http://localhost:11434
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
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

### 4. Pull the LLM model (once)

```bash
ollama pull llama3.2
```

The default model name is set in `config/settings.py` (`LLM_MODEL = "llama3.2"`).

---

## Every session — run in this order

### Terminal 1 — OpenSearch (Docker)

**Do not use a ZIP/native OpenSearch install with security enabled.** This project expects plain **HTTP** on port 9200 with the security plugin disabled.

Make sure Docker Desktop is running, then:

**First time only** (create the container):

```powershell
# Windows PowerShell — if `docker` is not found, prepend Docker to PATH:
# $env:Path = "C:\Program Files\Docker\Docker\resources\bin;" + $env:Path

docker run -d --name native-rag-pipeline `
  -p 9200:9200 -p 9600:9600 `
  -e "discovery.type=single-node" `
  -e "DISABLE_SECURITY_PLUGIN=true" `
  -e "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m" `
  opensearchproject/opensearch:2
```

```bash
# macOS / Linux
docker run -d --name native-rag-pipeline \
  -p 9200:9200 -p 9600:9600 \
  -e "discovery.type=single-node" \
  -e "DISABLE_SECURITY_PLUGIN=true" \
  -e "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m" \
  opensearchproject/opensearch:2
```

**Later sessions:**

```bash
docker start native-rag-pipeline
```

**Verify:** open **http://localhost:9200** (not `https://`).

You should see JSON with `"cluster_name" : "docker-cluster"`.

If the browser says “secure connection” / invalid response, it is forcing HTTPS. Use `http://localhost:9200` explicitly. Chrome may remember HTTPS from an older OpenSearch; clear HSTS for `localhost` at `chrome://net-internals/#hsts` if needed.

### Terminal 2 — Ollama

```bash
ollama serve
```

On Windows, Ollama often already runs in the background after install. Confirm with:

```bash
curl http://localhost:11434
```

### Terminal 3 — Ingest and query

Put PDFs or `.txt` files in `data/raw/`.

**With npm (uses the project `venv` automatically):**

```bash
npm run ingest
npm run query -- "Your question here"
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
| OpenSearch `ConnectionError` / connection closed | HTTPS + security OpenSearch, or wrong install | Use the Docker command above with `DISABLE_SECURITY_PLUGIN=true` |
| Browser “can’t provide a secure connection” | Opening `https://localhost:9200` | Use **http://**localhost:9200 |
| Port 9200 already in use | Another OpenSearch (e.g. ZIP install) still running | Stop that process, then `docker start native-rag-pipeline` |
| Query fails / model not found | Wrong or missing Ollama model | `ollama pull llama3.2` |
| First ingest is slow | Downloading embedding/reranker models | One-time download; later runs are faster |

---

## Quick reference

```bash
# Services
docker start native-rag-pipeline
ollama serve   # if not already running

# Pipeline
npm run ingest
npm run query -- "What is this document about?"
npm run delete-index
```
