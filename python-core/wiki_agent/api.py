import asyncio
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

os.environ.setdefault("EMBEDDING_DIM", "512")

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .agent_graph import build
from .ingest import DocumentIngester
from .memory import ExpertMemory
from .search_web import search_web

memory: ExpertMemory | None = None
graph = None
ingester: DocumentIngester | None = None
init_error: str | None = None


async def initialize() -> None:
    global memory, graph, ingester, init_error
    init_error = None
    try:
        if not config.LLM_API_KEY:
            raise RuntimeError("请在 .env 中配置 LLM_API_KEY")
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        memory = ExpertMemory()
        await memory.init()
        graph = build(memory)
        ingester = DocumentIngester(memory)
    except Exception as exc:
        init_error = str(exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(initialize())
    yield
    if not task.done():
        task.cancel()
    if memory:
        await memory.close()


def require_ready() -> None:
    if init_error:
        raise HTTPException(503, init_error)
    if not memory or not graph or not ingester:
        raise HTTPException(503, "知识引擎正在初始化，请稍候")


app = FastAPI(title="Wiki Agent Core", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:1420", "http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"], allow_methods=["*"], allow_headers=["*"])


class AskRequest(BaseModel):
    question: str
    thread_id: str = "desktop"


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class SettingsRequest(BaseModel):
    llm_base_url: str
    llm_model: str
    api_key: str | None = None
    searxng_url: str = ""


@app.get("/health")
async def health():
    status = "error" if init_error else "ready" if memory and graph and ingester else "initializing"
    return {"status": status, "error": init_error, "config": config.public_config()}


@app.get("/config")
async def get_config():
    return config.public_config()


@app.post("/config")
async def update_config(request: SettingsRequest):
    global memory, graph, ingester
    config.save_llm_settings(request.llm_base_url, request.llm_model, request.api_key, request.searxng_url)
    if memory:
        await memory.close()
    memory = graph = ingester = None
    asyncio.create_task(initialize())
    return config.public_config()


@app.post("/ask")
async def ask(request: AskRequest):
    require_ready()
    result = await graph.ainvoke({"question": request.question}, config={"configurable": {"thread_id": request.thread_id}})
    return {"answer": result["answer"], "memories": result["memories"], "verdict": result["verdict"]}


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    require_ready()
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
    require_ready()
    edges = await memory.recall(f"{kind} {query}".strip(), 30)
    return [{"fact": edge.fact, "valid": not bool(getattr(edge, "invalid_at", None)), "source": getattr(edge, "source_node_uuid", None)} for edge in edges]


@app.post("/search")
async def search(request: SearchRequest):
    try:
        return await search_web(request.query, request.limit)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


WEB_DIR = Path(getattr(sys, "_MEIPASS", Path.cwd())) / "web"
if not WEB_DIR.exists():
    WEB_DIR = config.PROJECT_ROOT / "dist"
if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="web-assets")

    @app.get("/web")
    @app.get("/")
    async def web_app():
        return FileResponse(WEB_DIR / "index.html")
