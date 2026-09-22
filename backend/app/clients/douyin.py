"""TikTokDownloader Web API 客户端。

注意：TikTokDownloader 的 API 路径/参数以其运行时文档为准
（启动后访问 http://127.0.0.1:5555/docs）。以下封装按常见模式编写，
集成时对照实际接口微调即可。
"""
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings


def _base() -> str:
    return get_settings().douyin_api_url.rstrip("/")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def _get(path: str, **params) -> dict:
    resp = httpx.get(f"{_base()}{path}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def _post(path: str, json: dict) -> dict:
    resp = httpx.post(f"{_base()}{path}", json=json, timeout=300)
    resp.raise_for_status()
    return resp.json()


# ---------- 采集入口 ----------

def fetch_hot_board(board: str = "热榜") -> list[dict]:
    """热榜采集：返回榜单条目（含作品链接/ID）。"""
    # TODO: 对照 TikTokDownloader /docs 确认实际路径与参数
    data = _get("/douyin/hot", board=board)
    return data.get("data", [])


def fetch_account_posts(sec_uid: str, count: int = 50,
                        earliest: str | None = None) -> list[dict]:
    """按达人采集作品列表。"""
    data = _get("/douyin/account", sec_uid=sec_uid, count=count,
                earliest=earliest or "")
    return data.get("data", [])


class LikesUnavailableError(RuntimeError):
    """用户点赞列表不可用：未公开（无权限）或平台拒绝返回。"""


def fetch_user_likes(sec_uid: str, count: int = 50) -> list[dict]:
    """按用户采集其点赞过的视频列表。

    点赞列表属隐私数据：用户未公开或平台拒绝时，下游一般返回错误信息
    或空数据，统一转成 LikesUnavailableError，由接口层给出明确报错。
    """
    # TODO: 对照 TikTokDownloader /docs 确认点赞采集的实际路径与参数
    data = _get("/douyin/like", sec_uid=sec_uid, count=count)
    err = data.get("message") or data.get("error")
    if err:
        raise LikesUnavailableError(f"无法采集该用户的点赞列表：{err}")
    items = data.get("data") or []
    if not items:
        raise LikesUnavailableError(
            "未采集到点赞视频：该用户的点赞列表可能未公开（无权限访问），或暂无点赞内容")
    return items


def search_videos(keyword: str, count: int = 30) -> list[dict]:
    """关键词搜索采集。"""
    data = _get("/douyin/search", keyword=keyword, count=count, type="video")
    return data.get("data", [])


def fetch_comments(aweme_id: str, count: int = 50) -> list[dict]:
    """采集作品评论。调用方按 digg_count 排序取 TopN。"""
    data = _get("/douyin/comment", aweme_id=aweme_id, count=count)
    return data.get("data", [])


def download_video(aweme_id: str, save_dir: str) -> str | None:
    """触发下载单个作品，返回本地文件路径。"""
    try:
        data = _post("/douyin/detail", {"aweme_id": aweme_id,
                                        "download": True, "path": save_dir})
        return data.get("path")  # TODO: 以实际返回字段为准
    except Exception as e:
        logger.error(f"下载失败 {aweme_id}: {e}")
        return None
