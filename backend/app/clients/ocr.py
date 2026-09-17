"""RapidOCRAPI 客户端：视频抽帧 -> OCR -> 去重合并文本。"""
import io
import subprocess
from pathlib import Path

import httpx
from loguru import logger
from PIL import Image

from app.core.config import get_settings

CONFIDENCE_MIN = 0.7
# 字幕通常位于画面底部，可按需开启区域过滤
BOTTOM_BAND_ONLY = False


def extract_frames(video_path: str | Path, interval_sec: float = 2.0,
                   max_frames: int = 15) -> list[bytes]:
    """用 ffmpeg 均匀抽帧，返回 JPEG 字节列表。"""
    frames: list[bytes] = []
    # 先取时长
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True)
    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        duration = 30.0
    step = max(duration / max_frames, interval_sec)

    for i in range(max_frames):
        ts = i * step
        if ts >= duration:
            break
        result = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-ss", str(ts), "-i", str(video_path),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
            capture_output=True)
        if result.returncode == 0 and result.stdout:
            frames.append(result.stdout)
    logger.debug(f"抽帧 {len(frames)} 张: {video_path}")
    return frames


def ocr_image(image_bytes: bytes) -> list[dict]:
    """调用 RapidOCRAPI，返回 [{text, score, box}, ...]"""
    s = get_settings()
    resp = httpx.post(
        s.ocr_api_url,
        files={"file": ("frame.jpg", image_bytes, "image/jpeg")},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    # RapidOCRAPI 返回结构: {"data": [[box, text, score], ...]} （以实际部署版本为准）
    items = data.get("data") or data.get("results") or []
    out = []
    for box, text, score in items:
        if score >= CONFIDENCE_MIN:
            if BOTTOM_BAND_ONLY:
                ys = [p[1] for p in box]
                img_h = 720  # 无法得知原图高度时跳过过滤；可在调用处传真实高度
                if min(ys) < img_h * 0.75:
                    continue
            out.append({"text": text, "score": score})
    return out


def ocr_video(video_path: str | Path) -> str:
    """整条视频的画面文本：抽帧 OCR + 相邻去重合并。"""
    seen: set[str] = set()
    lines: list[str] = []
    for frame in extract_frames(video_path):
        for item in ocr_image(frame):
            t = item["text"].strip()
            if t and t not in seen:
                seen.add(t)
                lines.append(t)
    return "\n".join(lines)
