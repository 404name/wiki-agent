import json
import os
from pathlib import Path

import keyring
from dotenv import load_dotenv

CORE_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = CORE_ROOT.parent
load_dotenv(Path.cwd() / ".env")
load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("EMBEDDING_DIM", "512")

DATA_DIR = Path(os.getenv("WIKI_AGENT_DATA_DIR", Path.home() / ".wiki-agent"))
RAW_DIR = Path(os.getenv("WIKI_AGENT_RAW_DIR", DATA_DIR / "raw"))
SETTINGS_FILE = DATA_DIR / "settings.json"
KEYRING_SERVICE = "com.wikiagent.llm"


def _settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


_saved = _settings()
LLM_API_KEY = keyring.get_password(KEYRING_SERVICE, "api-key") or os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
LLM_BASE_URL = _saved.get("llm_base_url") or os.getenv("LLM_BASE_URL", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
LLM_MODEL = _saved.get("llm_model") or os.getenv("LLM_MODEL", "deepseek-chat")
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "127.0.0.1")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
GROUP_ID = os.getenv("GRAPH_GROUP_ID", "wiki-agent")
SEARXNG_URL = _saved.get("searxng_url") or os.getenv("SEARXNG_URL", "").rstrip("/")
CHECKPOINT_DB = str(DATA_DIR / "checkpoints.db")
INGEST_INDEX = DATA_DIR / "ingest-index.json"


def save_llm_settings(base_url: str, model: str, api_key: str | None, searxng_url: str = "") -> None:
    global LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, SEARXNG_URL
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LLM_BASE_URL, LLM_MODEL, SEARXNG_URL = base_url.rstrip("/"), model, searxng_url.rstrip("/")
    SETTINGS_FILE.write_text(json.dumps({"llm_base_url": LLM_BASE_URL, "llm_model": LLM_MODEL, "searxng_url": SEARXNG_URL}, ensure_ascii=False, indent=2), encoding="utf-8")
    if api_key:
        keyring.set_password(KEYRING_SERVICE, "api-key", api_key)
        LLM_API_KEY = api_key


def public_config() -> dict:
    return {"llm_model": LLM_MODEL, "llm_base_url": LLM_BASE_URL, "llm_configured": bool(LLM_API_KEY), "falkordb": f"{FALKORDB_HOST}:{FALKORDB_PORT}", "graph_group_id": GROUP_ID, "searxng_url": SEARXNG_URL, "searxng_configured": bool(SEARXNG_URL)}
