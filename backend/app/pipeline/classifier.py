"""LLM 分类器：零样本打标 + 置信度，低置信度进入人工复核队列。"""
from loguru import logger
from sqlalchemy.orm import Session

from app.clients import llm
from app.models import Category, Video, VideoStatus

CLASSIFY_PROMPT = """你是一个短视频内容分类器。请根据视频的标题、话题、画面文字、语音文本和高赞评论，判断它属于哪个类别。

可选类别（必须从中选择一个，都不合适时返回 "未分类"）：
{categories}

请以 JSON 输出：
{{"category": "类别名", "confidence": 0.0~1.0, "reason": "一句话理由"}}

## 视频信息
标题: {title}
话题: {hashtags}
画面文字: {ocr_text}
语音文本: {asr_text}
高赞评论:
{comments}"""


def classify_video(db: Session, video: Video) -> None:
    categories = db.query(Category).filter(Category.enabled.is_(True)).all()
    if not categories:
        logger.warning("无可用类别，跳过分类")
        return

    cat_text = "\n".join(f"- {c.name}: {c.description or '无描述'}" for c in categories)
    top_comments = sorted(video.comments, key=lambda c: c.digg_count, reverse=True)[:10]
    comments_text = "\n".join(f"- ({c.digg_count}赞) {c.text}" for c in top_comments) or "无"

    prompt = CLASSIFY_PROMPT.format(
        categories=cat_text,
        title=video.title or "无",
        hashtags=" ".join(video.hashtags or []) or "无",
        ocr_text=(video.ocr_text or "无")[:500],
        asr_text=(video.asr_text or "无")[:1500],
        comments=comments_text[:800],
    )
    try:
        result = llm.chat_json([{"role": "user", "content": prompt}])
    except Exception as e:
        logger.error(f"分类失败 video={video.id}: {e}")
        video.status = VideoStatus.FAILED
        video.error = f"classify: {e}"
        return

    name = result.get("category", "未分类")
    confidence = float(result.get("confidence", 0))
    matched = next((c for c in categories if c.name == name), None)

    video.category_id = matched.id if matched else None
    video.classify_confidence = confidence
    video.classify_source = "llm"
    video.status = VideoStatus.CLASSIFIED
    logger.info(f"分类 video={video.id} -> {name} ({confidence:.2f})")
