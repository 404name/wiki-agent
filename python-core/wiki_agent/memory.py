"""Graphiti 封装：专家记忆的写入（抽取）、检索与反思回写。"""
import os

os.environ.setdefault('EMBEDDING_DIM', '512')  # 必须先于 graphiti_core 导入

import json
from datetime import datetime

from pydantic import BaseModel, Field

from graphiti_core import Graphiti
from graphiti_core.driver import falkordb_driver as _fd
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.nodes import EpisodeType

from . import config
from .embedder import LocalEmbedder, PassthroughReranker


# ---- FalkorDB 写入兼容 shim ----
# DeepSeek（json_object 模式，无 schema 强约束）抽取自定义实体属性时，
# 会模仿 JSON Schema 结构把字段包进 'properties' dict；FalkorDB 不允许
# 嵌套 map 作为属性值（Neo4j 同样），导致写入报
# "Property values can only be of primitive types..."。
# 这里在写入前把 'properties' 拍平，其余嵌套 dict 序列化为 JSON 字符串。
def _sanitize_properties(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == 'properties' and isinstance(v, dict):
                out.update(_sanitize_properties(v))
            elif isinstance(v, dict):
                out[k] = json.dumps(v, ensure_ascii=False)
            else:
                out[k] = _sanitize_properties(v)
        return out
    if isinstance(obj, list):
        return [_sanitize_properties(v) for v in obj]
    return obj


_orig_session_run = _fd.FalkorDriverSession.run


async def _sanitized_session_run(self, query, **kwargs):
    if isinstance(query, list):
        query = [(c, _sanitize_properties(p)) for c, p in query]
    else:
        kwargs = _sanitize_properties(kwargs)
    return await _orig_session_run(self, query, **kwargs)


_fd.FalkorDriverSession.run = _sanitized_session_run


# ---- 自定义实体类型：对应 Expert Builder 里的知识分类 ----
class Decision(BaseModel):
    """团队做出的技术决策"""

    reason: str | None = Field(None, description='做出该决策的原因')
    evidence: str | None = Field(None, description='决策证据来源，如 PR 编号、事故编号、会议日期')


class Rule(BaseModel):
    """必须遵守的规范或约束"""

    scope: str | None = Field(None, description='规范适用范围')
    owner: str | None = Field(None, description='制定者/负责人')


class Risk(BaseModel):
    """已发生的事故或潜在风险"""

    severity: str | None = Field(None, description='严重程度，如 P1/P2')
    cause: str | None = Field(None, description='根因')


class Experience(BaseModel):
    """实践中验证过的经验教训"""

    context: str | None = Field(None, description='适用场景')


ENTITY_TYPES = {
    'Decision': Decision,
    'Rule': Rule,
    'Risk': Risk,
    'Experience': Experience,
}


class ExpertMemory:
    """团队共享的专家记忆（同一个 group_id，知识集中沉淀）。"""

    def __init__(self):
        llm = OpenAIGenericClient(
            config=LLMConfig(
                api_key=config.LLM_API_KEY,
                model=config.LLM_MODEL,
                base_url=config.LLM_BASE_URL,
                small_model=config.LLM_MODEL,
            ),
            # DeepSeek 只支持 json_object，不支持 OpenAI 的 json_schema 严格模式
            structured_output_mode='json_object',
        )
        driver = FalkorDriver(
            host=config.FALKORDB_HOST,
            port=config.FALKORDB_PORT,
            # graphiti 的写入按 group_id 分图，检索则走 driver 默认图；
            # 两者必须一致，否则新进程检索会打到空图上
            database=config.GROUP_ID,
        )
        self.graphiti = Graphiti(
            graph_driver=driver,
            llm_client=llm,
            embedder=LocalEmbedder(config.EMBEDDING_MODEL),
            cross_encoder=PassthroughReranker(),
            max_coroutines=4,  # 控制对 DeepSeek 的并发
        )

    async def init(self):
        await self.graphiti.build_indices_and_constraints()

    async def ingest(
        self, name: str, body: str, source_description: str, reference_time: datetime
    ):
        """把一条语料（PR/复盘/纪要）交给 Graphiti 做实体关系抽取并入库。"""
        return await self.graphiti.add_episode(
            name=name,
            episode_body=body,
            source_description=source_description,
            reference_time=reference_time,
            source=EpisodeType.text,
            group_id=config.GROUP_ID,
            entity_types=ENTITY_TYPES,
        )

    async def recall(self, query: str, num_results: int = 10) -> list[EntityEdge]:
        """混合检索（语义 + BM25 + 图）相关记忆。"""
        return await self.graphiti.search(
            query=query, group_ids=[config.GROUP_ID], num_results=num_results
        )

    async def reflect(self, question: str, answer: str, verdict: str):
        """Reflection：把本次设计结论回写为新 Episode，知识持续积累。"""
        body = (
            f'设计问答反思。\n问题：{question}\n'
            f'结论：{answer}\n风险评审：{verdict}'
        )
        return await self.graphiti.add_episode(
            name=f'reflection-{datetime.now():%Y%m%d-%H%M%S}',
            episode_body=body,
            source_description='Expert Agent 设计反思回写',
            reference_time=datetime.now(),
            source=EpisodeType.text,
            group_id=config.GROUP_ID,
            entity_types=ENTITY_TYPES,
        )

    async def close(self):
        await self.graphiti.close()
