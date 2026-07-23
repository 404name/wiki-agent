"""本地 AI 适配层。

DeepSeek 不提供 embedding / rerank API：
- embedding 用 fastembed 本地中文模型（ONNX，无需 GPU）
- rerank 用直通实现（相关度交给 Graphiti 的 向量+BM25 混合检索）
"""
from fastembed import TextEmbedding
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.embedder.client import EmbedderClient


class LocalEmbedder(EmbedderClient):
    def __init__(self, model_name: str):
        self._model = TextEmbedding(model_name)

    async def create(self, input_data) -> list[float]:
        text = input_data if isinstance(input_data, str) else str(input_data)
        return list(self._model.embed([text]))[0].tolist()

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(input_data_list)]


class PassthroughReranker(CrossEncoderClient):
    """保持检索原顺序的重排器，本地 demo 够用；生产可换 bge-reranker。"""

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        n = max(len(passages), 1)
        return [(p, (n - i) / n) for i, p in enumerate(passages)]
