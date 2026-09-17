"""LangGraph 智能体：类别路由 -> 类别 RAG 检索 -> 风格化生成。

每个类别一个 Agent 人格，由 Category.system_prompt 定义风格，
语料从 pgvector 按 category_id 隔离检索。
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients import embedding, llm
from app.models import Category, Corpus

TOP_K = 8


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
    vec = embedding.embed_one(state["question"])
    stmt = (
        select(Corpus)
        .where(Corpus.category_id == state["category"]["id"])
        .order_by(Corpus.embedding.cosine_distance(vec))
        .limit(TOP_K)
    )
    state["contexts"] = [c.content for c in db.scalars(stmt).all()]
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
        {"role": "user", "content":
            f"参考语料：\n{context_text}\n\n用户问题：{state['question']}"},
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
    vec = embedding.embed_one(question)
    stmt = (
        select(Corpus)
        .where(Corpus.category_id == category_id)
        .order_by(Corpus.embedding.cosine_distance(vec))
        .limit(TOP_K)
    )
    return [c.content for c in db.scalars(stmt).all()]


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
        {"role": "system",
         "content": f"回答统一使用 Markdown 格式。以下是可参考的同类语料：\n{context_text}"},
    ]
    messages += [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": question})
    return messages
