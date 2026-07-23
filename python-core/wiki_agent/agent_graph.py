"""LangGraph 工作流：retrieve -> reason -> judge -> reflect。

带 SQLite checkpoint：同一个 thread_id 的会话跨进程续接，
演示"做到一半下班，第二天继续"。
"""
import os

os.environ.setdefault('EMBEDDING_DIM', '512')  # 必须先于 graphiti_core 导入

import aiosqlite
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from . import config
from .memory import ExpertMemory


class ExpertState(TypedDict):
    question: str
    memories: list[str]
    draft: str
    verdict: str
    answer: str


def _fmt_memories(edges) -> list[str]:
    out = []
    for e in edges:
        status = '已失效' if getattr(e, 'invalid_at', None) else '有效'
        out.append(f'[{status}] {e.fact}')
    return out


def build(memory: ExpertMemory):
    llm = ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        temperature=0,
    )

    async def retrieve(state: ExpertState):
        edges = await memory.recall(state['question'])
        return {'memories': _fmt_memories(edges)}

    async def reason(state: ExpertState):
        mem = '\n'.join(state['memories']) or '（无相关记忆）'
        resp = await llm.ainvoke([
            (
                'system',
                '你是企业知识架构师。基于知识图谱记忆回答问题，必须引用具体证据和来源，'
                '（PR 编号、事故编号、决策来源），禁止编造；标记为已失效的记忆不得作为依据。',
            ),
            ('user', f'团队记忆：\n{mem}\n\n问题：{state["question"]}'),
        ])
        return {'draft': resp.content}

    async def judge(state: ExpertState):
        mem = '\n'.join(state['memories']) or '（无相关记忆）'
        resp = await llm.ainvoke([
            (
                'system',
                '你是风险评审员。检查方案是否与团队记忆中的 Rule/Risk 冲突。'
                '输出：结论（通过/有风险）+ 具体冲突点，简洁作答。',
            ),
            ('user', f'团队记忆：\n{mem}\n\n方案：\n{state["draft"]}'),
        ])
        verdict = resp.content
        return {
            'verdict': verdict,
            'answer': f'{state["draft"]}\n\n—— 风险评审 ——\n{verdict}',
        }

    async def reflect(state: ExpertState):
        await memory.reflect(state['question'], state['draft'], state['verdict'])
        return {}

    g = StateGraph(ExpertState)
    g.add_node('retrieve', retrieve)
    g.add_node('reason', reason)
    g.add_node('judge', judge)
    g.add_node('reflect', reflect)
    g.add_edge(START, 'retrieve')
    g.add_edge('retrieve', 'reason')
    g.add_edge('reason', 'judge')
    g.add_edge('judge', 'reflect')
    g.add_edge('reflect', END)

    conn = aiosqlite.connect(config.CHECKPOINT_DB, check_same_thread=False)
    return g.compile(checkpointer=AsyncSqliteSaver(conn))
