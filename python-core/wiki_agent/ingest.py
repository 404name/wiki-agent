import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from . import config


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if suffix == ".docx":
        return "\n".join(p.text for p in Document(path).paragraphs)
    raise ValueError(f"不支持的文件类型: {suffix}")


def content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DocumentIngester:
    def __init__(self, memory):
        self.memory = memory
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        config.RAW_DIR.mkdir(parents=True, exist_ok=True)

    def _index(self) -> dict:
        if not config.INGEST_INDEX.exists():
            return {}
        return json.loads(config.INGEST_INDEX.read_text(encoding="utf-8"))

    async def ingest(self, path: Path) -> dict:
        digest = content_hash(path)
        index = self._index()
        if digest in index:
            return {"status": "skipped", "hash": digest, "source": index[digest]["source"]}
        target = config.RAW_DIR / f"{digest[:12]}-{path.name}"
        shutil.copy2(path, target)
        text = extract_text(target).strip()
        if not text:
            raise ValueError("文档没有可提取文本")
        result = await self.memory.ingest(path.stem, text, f"file:{target.name};sha256:{digest}", datetime.now())
        index[digest] = {"source": target.name, "ingested_at": datetime.now().isoformat()}
        config.INGEST_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "ingested", "hash": digest, "source": target.name, "nodes": len(result.nodes), "edges": len(result.edges)}
