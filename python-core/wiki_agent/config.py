import os
from pathlib import Path

from dotenv import load_dotenv

CORE_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = CORE_ROOT.parent
load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("EMBEDDING_DIM", "512")

LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
LLM_BASE_URL = os.getenv("LLM_BASE_URL", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "127.0.0.1")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
GROUP_ID = os.getenv("GRAPH_GROUP_ID", "wiki-agent")
SEARXNG_URL = os.getenv("SEARXNG_URL", "").rstrip("/")
DATA_DIR = Path(os.getenv("WIKI_AGENT_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = Path(os.getenv("WIKI_AGENT_RAW_DIR", PROJECT_ROOT / "raw"))
CHECKPOINT_DB = str(DATA_DIR / "checkpoints.db")
INGEST_INDEX = DATA_DIR / "ingest-index.json"


def public_config() -> dict:
    return {
        "llm_model": LLM_MODEL,
        "llm_base_url": LLM_BASE_URL,
        "llm_configured": bool(LLM_API_KEY),
        "falkordb": f"{FALKORDB_HOST}:{FALKORDB_PORT}",
        "graph_group_id": GROUP_ID,
        "searxng_configured": bool(SEARXNG_URL),
    }
