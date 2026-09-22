"""采集任务路由：热榜/达人/点赞/搜索采集 + 流水线触发。"""
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.clients.douyin import LikesUnavailableError
from app.core.database import get_db
from app.pipeline import orchestrator

router = APIRouter(prefix="/api/collect", tags=["collect"])


class HotCollectReq(BaseModel):
    board: str = "热榜"
    limit: int = Field(default=50, le=200)


class AccountCollectReq(BaseModel):
    sec_uid: str
    count: int = Field(default=50, le=500)
    min_digg: int = 0  # 点赞过滤


class ManualCollectReq(BaseModel):
    aweme_id: str


class LikesCollectReq(BaseModel):
    sec_uid: str
    count: int = Field(default=50, le=200)


@router.post("/hot")
def collect_hot(req: HotCollectReq, bg: BackgroundTasks, db: Session = Depends(get_db)):
    ids = orchestrator.collect_hot(db, board=req.board, limit=req.limit)
    for vid in ids:
        bg.add_task(orchestrator.run_video, vid)
    return {"registered": len(ids), "video_ids": ids}


@router.post("/account")
def collect_account(req: AccountCollectReq, bg: BackgroundTasks, db: Session = Depends(get_db)):
    ids = orchestrator.collect_account(db, sec_uid=req.sec_uid,
                                       count=req.count, min_digg=req.min_digg)
    for vid in ids:
        bg.add_task(orchestrator.run_video, vid)
    return {"registered": len(ids), "video_ids": ids}


@router.post("/likes")
def collect_likes(req: LikesCollectReq, bg: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        ids = orchestrator.collect_likes(db, sec_uid=req.sec_uid, count=req.count)
    except LikesUnavailableError as e:
        # 点赞列表未公开/无数据：403 语义最贴切，文案直接给前端展示
        raise HTTPException(status_code=403, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"采集服务请求失败：{e}")
    for vid in ids:
        bg.add_task(orchestrator.run_video, vid)
    return {"registered": len(ids), "video_ids": ids}


@router.post("/manual")
def collect_manual(req: ManualCollectReq, bg: BackgroundTasks, db: Session = Depends(get_db)):
    video = orchestrator.register_video(db, req.aweme_id, {}, source="manual")
    bg.add_task(orchestrator.run_video, video.id)
    return {"video_id": video.id}


@router.post("/retry/{video_id}")
def retry_video(video_id: int, bg: BackgroundTasks):
    bg.add_task(orchestrator.run_video, video_id)
    return {"ok": True}
