"""faster-whisper ASR 客户端：模型懒加载，进程内单例。"""
import subprocess
from pathlib import Path

from loguru import logger

from app.core.config import get_settings

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        s = get_settings()
        device = s.whisper_device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        logger.info(f"加载 Whisper 模型 {s.whisper_model_size} on {device}")
        _model = WhisperModel(s.whisper_model_size, device=device,
                              compute_type=s.whisper_compute_type)
    return _model


def extract_audio(video_path: str | Path) -> Path:
    """ffmpeg 抽音轨转 16k 单声道 wav，whisper 友好格式。"""
    video_path = Path(video_path)
    wav_path = video_path.with_suffix(".wav")
    if wav_path.exists():
        return wav_path
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-i", str(video_path),
         "-vn", "-ac", "1", "-ar", "16000", str(wav_path)],
        check=True)
    return wav_path


def transcribe(video_path: str | Path) -> str:
    """视频 -> 语音文本。"""
    model = _get_model()
    audio = extract_audio(video_path)
    segments, info = model.transcribe(str(audio), language="zh",
                                      vad_filter=True, beam_size=5)
    text = "".join(seg.text for seg in segments).strip()
    logger.debug(f"ASR 完成 ({info.duration:.1f}s 音频): {video_path}")
    return text
