import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

os.environ.setdefault("EMBEDDING_DIM", "512")

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config
from .agent_graph import build
from .ingest import DocumentIngester
from .memory import ExpertMemory
from .search_web import search_web

memory: ExpertMemory | None = None
graph = None
ingester: DocumentIngester | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global memory, graph, ingester
    if not config.LLM_API_KEY:
        raise RuntimeError("请在 .env 中配置 LLM_API_KEY")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    memory = ExpertMemory()
    await memory.init()
    graph = build(memory)
    ingester = DocumentIngester(memory)
    yield
    await memory.close()


app = FastAPI(title="Wiki Agent Core", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:1420", "tauri://localhost"], allow_methods=["*"], allow_headers=["*"])


class AskRequest(BaseModel):
    question: str
    thread_id: str = "desktop"


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


@app.get("/health")
async def health():
    return {"status": "ok", "config": config.public_config()}


@app.get("/config")
async def get_config():
    return config.public_config()


@app.post("/ask")
async def ask(request: AskRequest):
    result = await graph.ainvoke({"question": request.question}, config={"configurable": {"thread_id": request.thread_id}})
    return {"answer": result["answer"], "memories": result["memories"], "verdict": result["verdict"]}


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    suffix = Path(file.filename or "document.txt").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(await file.read())
        path = Path(handle.name)
    try:
        return await ingester.ingest(path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)


@app.get("/decisions")
async def decisions(kind: str = "Decision", query: str = ""):
    edges = await memory.recall(f"{kind} {query}".strip(), 30)
    return [{"fact": edge.fact, "valid": not bool(getattr(edge, "invalid_at", None)), "source": getattr(edge, "source_node_uuid", None)} for edge in edges]


@app.post("/search")
async def search(request: SearchRequest):
    try:
        return await search_web(request.query, request.limit)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
