"""向量索引器：把已分类视频的文本和高赞评论写入语料向量表。"""
from sqlalchemy.orm import Session

from app.clients import embedding
from app.models import Corpus, Video, VideoStatus


def index_video(db: Session, video: Video) -> None:
    if video.category_id is None:
        return  # 未分类不入库

    texts: list[tuple[str, str, int | None]] = []  # (content, type, comment_id)
    if video.full_text.strip():
        texts.append((video.full_text, "video", None))

    top = sorted(video.comments, key=lambda c: c.digg_count, reverse=True)
    from app.core.config import get_settings
    for c in top[: get_settings().top_comments]:
        if c.text.strip():
            texts.append((c.text, "comment", c.id))

    if not texts:
        return

    vectors = embedding.embed([t[0][:2000] for t in texts])
    for (content, ctype, cid), vec in zip(texts, vectors):
        db.add(Corpus(video_id=video.id, comment_id=cid,
                      category_id=video.category_id,
                      content=content, content_type=ctype,
                      embedding=vec))
    video.status = VideoStatus.INDEXED
