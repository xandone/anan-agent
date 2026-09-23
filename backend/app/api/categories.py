"""类别管理路由。"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.clients import llm
from app.core.database import get_db
from app.models import Category, Corpus, Video

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
def list_categories(db: Session = Depends(get_db)):
    cats = db.query(Category).all()
    return [{
        "id": c.id, "name": c.name, "slug": c.slug,
        "description": c.description, "system_prompt": c.system_prompt,
        "enabled": c.enabled,
        "video_count": db.query(Video).filter_by(category_id=c.id).count(),
        "corpus_count": db.query(Corpus).filter_by(category_id=c.id).count(),
    } for c in cats]


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class CategoryReq(BaseModel):
    name: str
    slug: str
    description: str | None = None
    system_prompt: str | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("名称不能为空")
        if len(v) > 64:
            raise ValueError("名称不能超过 64 字")
        return v

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("slug 不能为空")
        if not _SLUG_RE.fullmatch(v):
            raise ValueError("slug 只能由小写字母、数字、- 和 _ 组成，且以字母或数字开头")
        return v


class AIDraftReq(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("请先填写名称")
        return v


_DRAFT_PROMPT = """你在为一个「短视频内容分类智能体」系统设计新人格。根据用户给的智能体名称，输出 JSON：
{"slug": "...", "description": "...", "system_prompt": "..."}

要求：
- slug：英文小写标识，只能含小写字母、数字、-、_，以字母开头，简短表意，如 poem、snarky-comment、science-talk
- description：30~80 字，说明什么样的内容属于这一类，供分类模型判断打标用，描述内容特征而非人格
- system_prompt：100~200 字的人格设定，以"你是…"开头，包含说话风格、口吻、常用表达和禁忌
只输出 JSON，不要其他内容。"""


@router.post("/ai-draft")
def ai_draft(req: AIDraftReq):
    """根据名称用 LLM 生成 slug、类别定义和人格 Prompt 草稿。"""
    try:
        data = llm.chat_json([
            {"role": "system", "content": _DRAFT_PROMPT},
            {"role": "user", "content": f"智能体名称：{req.name}"},
        ])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "AI 生成失败，请稍后重试")
    # slug 兜底清洗：非法字符转 -，清洗后仍不合法则留空让用户手填
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(data.get("slug") or "").lower()).strip("-_")
    if not _SLUG_RE.fullmatch(slug):
        slug = ""
    return {
        "slug": slug,
        "description": str(data.get("description") or "").strip(),
        "system_prompt": str(data.get("system_prompt") or "").strip(),
    }


@router.post("")
def create_category(req: CategoryReq, db: Session = Depends(get_db)):
    if db.query(Category).filter((Category.name == req.name) | (Category.slug == req.slug)).first():
        raise HTTPException(400, "名称或 slug 已存在")
    cat = Category(**req.model_dump())
    db.add(cat)
    db.commit()
    return {"id": cat.id}


@router.put("/{category_id}")
def update_category(category_id: int, req: CategoryReq, db: Session = Depends(get_db)):
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(404)
    dup = db.query(Category).filter(
        (Category.name == req.name) | (Category.slug == req.slug),
        Category.id != category_id,
    ).first()
    if dup:
        raise HTTPException(400, "名称或 slug 已存在")
    for k, v in req.model_dump().items():
        setattr(cat, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """删除智能体：连带删除其语料，关联视频归为未分类，历史对话保留。"""
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(404)
    db.query(Corpus).filter_by(category_id=category_id).delete(synchronize_session=False)
    db.query(Video).filter_by(category_id=category_id).update(
        {"category_id": None}, synchronize_session=False)
    db.delete(cat)
    db.commit()
    return {"ok": True}
