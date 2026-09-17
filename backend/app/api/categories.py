"""类别管理路由。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

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


class CategoryReq(BaseModel):
    name: str
    slug: str
    description: str | None = None
    system_prompt: str | None = None
    enabled: bool = True


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
    for k, v in req.model_dump().items():
        setattr(cat, k, v)
    db.commit()
    return {"ok": True}
