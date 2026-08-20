import os

from dotenv import load_dotenv

load_dotenv()

# LLM
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = "llama3.1:8b"
LLM_TEMPERATURE = 0.0
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", 8192))
LLM_NUM_GPU = os.getenv("LLM_NUM_GPU")

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

# OpenSearch
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
OPENSEARCH_INDEX = "rag_index"

# Paths
DATA_RAW_DIR = "data/raw"
DATA_PROCESSED_DIR = "data/processed"
DATA_CHUNKS_DIR = "data/chunks"
INGEST_MANIFEST_PATH = "data/processed/ingest_manifest.json"
INGEST_PIPELINE_VERSION = 3
