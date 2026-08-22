import os

from dotenv import load_dotenv

load_dotenv()

# Groq LLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 3000))

# Embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # must match your embedding model output size

# Chunking
CHUNK_SIZE = 900
CHUNK_OVERLAP = 100

# Retrieval
TOP_K = 40
RERANK_TOP_N = 8
MAX_CHUNKS_PER_SOURCE = 2
SOURCE_MATCH_BOOST = 1.5
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "rag_chunks")

# Paths
DATA_RAW_DIR = "data/raw"
DATA_PROCESSED_DIR = "data/processed"
DATA_CHUNKS_DIR = "data/chunks"
INGEST_MANIFEST_PATH = "data/processed/ingest_manifest.json"
INGEST_PIPELINE_VERSION = 4
