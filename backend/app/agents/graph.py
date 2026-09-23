"""LangGraph 智能体：类别路由 -> 类别 RAG 检索 -> 风格化生成。

每个类别一个 Agent 人格，由 Category.system_prompt 定义风格，
语料从 pgvector 按 category_id 隔离检索。
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients import embedding, llm
from app.core.config import get_settings
from app.models import Category, Corpus

TOP_K = 8

CONTEXT_RULES = """以下是知识库中与本问题最相关的语料。
回答规则（按优先级）：
1. 语料能直接回答用户问题时，直接引用语料原文作答，保持原汁原味——不要改写、不要扩写，也不要加寒暄和解释；
2. 语料只能部分覆盖时，先引用相关原文，再按你的人格风格简要补充；
3. 语料与问题无关时，说明知识库暂无相关内容，再按人格风格自由回答。
回答统一使用 Markdown 格式。

参考语料：
{contexts}"""


class AgentState(TypedDict):
    question: str
    category_slug: str
    category: dict | None
    contexts: list[str]
    answer: str


def route_category(state: AgentState, db: Session) -> AgentState:
    cat = db.query(Category).filter_by(slug=state["category_slug"], enabled=True).first()
    state["category"] = (
        {"id": cat.id, "name": cat.name, "system_prompt": cat.system_prompt}
        if cat else None
    )
    return state


def retrieve(state: AgentState, db: Session) -> AgentState:
    if not state["category"]:
        state["contexts"] = []
        return state
    state["contexts"] = retrieve_contexts(db, state["category"]["id"],
                                          state["question"])
    return state


def generate(state: AgentState, db: Session) -> AgentState:
    if not state["category"]:
        state["answer"] = "该类别不存在或未启用。"
        return state
    system = state["category"]["system_prompt"] or (
        f"你是「{state['category']['name']}」领域的内容专家，"
        f"请参考给定的同类语料风格和内容回答问题。"
    )
    context_text = "\n---\n".join(state["contexts"]) or "（暂无相关语料）"
    messages = [
        {"role": "system", "content": system},
        {"role": "system", "content": CONTEXT_RULES.format(contexts=context_text)},
        {"role": "user", "content": state["question"]},
    ]
    state["answer"] = llm.chat(messages)
    return state


def build_graph(db: Session):
    """构建一次对话用的图。db 通过闭包注入。"""
    g = StateGraph(AgentState)
    g.add_node("route", lambda s: route_category(s, db))
    g.add_node("retrieve", lambda s: retrieve(s, db))
    g.add_node("generate", lambda s: generate(s, db))
    g.set_entry_point("route")
    g.add_edge("route", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()


def chat_with_category(db: Session, category_slug: str, question: str) -> dict:
    graph = build_graph(db)
    result = graph.invoke({
        "question": question,
        "category_slug": category_slug,
        "category": None,
        "contexts": [],
        "answer": "",
    })
    return {
        "answer": result["answer"],
        "category": result["category"],
        "context_count": len(result["contexts"]),
    }


# ---------- 多轮对话（供流式接口复用） ----------

def get_category(db: Session, slug: str) -> dict | None:
    cat = db.query(Category).filter_by(slug=slug, enabled=True).first()
    return ({"id": cat.id, "name": cat.name, "system_prompt": cat.system_prompt}
            if cat else None)


def retrieve_contexts(db: Session, category_id: int, question: str) -> list[str]:
    """类别内向量检索 Top-K，过滤掉相似度不足的语料。

    余弦距离超过阈值（默认 0.45）视为无关——宁可不注入，
    也不让模型拿"挨边但无关"的语料强行引用。
    """
    vec = embedding.embed_one(question)
    dist = Corpus.embedding.cosine_distance(vec).label("d")
    stmt = (
        select(Corpus.content, dist)
        .where(Corpus.category_id == category_id)
        .order_by(dist)
        .limit(TOP_K)
    )
    max_d = get_settings().retrieval_max_distance
    return [content for content, d in db.execute(stmt) if d <= max_d]


def build_messages(category: dict, contexts: list[str],
                   history: list, question: str) -> list[dict]:
    """组装多轮消息：人格 system + 语料 system + 历史 + 当前问题。"""
    system = category["system_prompt"] or (
        f"你是「{category['name']}」领域的内容专家，"
        f"请参考给定的同类语料风格和内容回答问题。"
    )
    context_text = "\n---\n".join(contexts) or "（暂无相关语料）"
    messages = [
        {"role": "system", "content": system},
        {"role": "system", "content": CONTEXT_RULES.format(contexts=context_text)},
    ]
    messages += [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": question})
    return messages
