"""类别发现：对未分类/全部语料做 embedding 聚类，辅助发现新类目。

骨架阶段先留接口，后续可用 HDBSCAN 实现：
  embeddings -> HDBSCAN 聚类 -> 每簇抽样给 LLM 命名 -> 生成候选 Category
"""
from sqlalchemy.orm import Session


def discover_categories(db: Session, sample_size: int = 500) -> list[dict]:
    """返回候选新类别列表（名称、描述、样本）。骨架实现：占位。"""
    # TODO: HDBSCAN 聚类 + LLM 命名
    return []
