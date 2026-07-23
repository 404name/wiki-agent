from dataclasses import asdict, dataclass

import httpx

from . import config


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    engine: str = ""


async def search_web(query: str, limit: int = 5) -> list[dict]:
    if not config.SEARXNG_URL:
        raise RuntimeError("尚未配置 SEARXNG_URL")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{config.SEARXNG_URL}/search", params={"q": query, "format": "json"})
        response.raise_for_status()
    return [asdict(SearchResult(r.get("title", ""), r.get("url", ""), r.get("content", ""), r.get("engine", ""))) for r in response.json().get("results", [])[:limit]]
