"""数据看板聚合接口：一次请求返回看板所需的全部统计。

项目里第一个 group_by 聚合接口，替代前端多次 count 请求的模式。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Category, Comment, Corpus, Video, VideoStatus

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# 看板展示的流水线状态（ocr_done 是历史遗留状态，不展示）
DASHBOARD_STATUSES = [
    VideoStatus.PENDING, VideoStatus.DOWNLOADED, VideoStatus.ASR_DONE,
    VideoStatus.CLASSIFIED, VideoStatus.INDEXED, VideoStatus.FAILED,
]

DAILY_DAYS = 14  # 采集趋势天数


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    # ---- 视频：总量 / 状态分布 / 来源分布 ----
    video_total = db.query(func.count(Video.id)).scalar() or 0

    status_counts = {s.value: 0 for s in DASHBOARD_STATUSES}
    for status, n in db.query(Video.status, func.count()).group_by(Video.status):
        if status.value in status_counts:
            status_counts[status.value] = n

    source_counts = dict(
        db.query(Video.source, func.count()).group_by(Video.source).all())

    # ---- 近 14 天采集趋势（按 created_at 日期聚合，补齐无数据的日期）----
    today = datetime.utcnow().date()
    since = today - timedelta(days=DAILY_DAYS - 1)
    rows = (db.query(func.date(Video.created_at), func.count())
            .filter(Video.created_at >= datetime.combine(since, datetime.min.time()))
            .group_by(func.date(Video.created_at)).all())
    by_date = {str(d): n for d, n in rows}
    daily_counts = [
        {"date": (d.strftime("%m-%d")), "count": by_date.get(str(d), 0)}
        for d in (since + timedelta(days=i) for i in range(DAILY_DAYS))
    ]

    # ---- 类别分布：各类别的视频数 / 语料数 ----
    video_by_cat = dict(
        db.query(Video.category_id, func.count())
        .filter(Video.category_id.isnot(None))
        .group_by(Video.category_id).all())
    corpus_by_cat = dict(
        db.query(Corpus.category_id, func.count())
        .group_by(Corpus.category_id).all())
    category_stats = [
        {
            "id": c.id, "name": c.name, "slug": c.slug, "enabled": c.enabled,
            "video_count": video_by_cat.get(c.id, 0),
            "corpus_count": corpus_by_cat.get(c.id, 0),
        }
        for c in db.query(Category).order_by(Category.id).all()
    ]

    # ---- 评论与语料统计 ----
    comment_total, comment_digg_total = db.query(
        func.count(Comment.id),
        func.coalesce(func.sum(Comment.digg_count), 0),
    ).one()

    corpus_by_type = dict(
        db.query(Corpus.content_type, func.count())
        .group_by(Corpus.content_type).all())

    top_comments = [
        {"text": c.text, "digg_count": c.digg_count, "video_title": v.title}
        for c, v in (db.query(Comment, Video)
                     .join(Video, Comment.video_id == Video.id)
                     .order_by(Comment.digg_count.desc())
                     .limit(5).all())
    ]

    return {
        "video_total": video_total,
        "status_counts": status_counts,
        "source_counts": source_counts,
        "daily_counts": daily_counts,
        "category_stats": category_stats,
        "comment_total": comment_total,
        "comment_digg_total": comment_digg_total,
        "corpus_total": sum(corpus_by_type.values()),
        "corpus_by_type": corpus_by_type,
        "top_comments": top_comments,
    }
