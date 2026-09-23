# anan-agent 后端镜像
FROM python:3.12-slim

# ffmpeg：ASR 抽音轨依赖（app/clients/asr.py 调用 ffmpeg 子进程）
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖再吃镜像缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 采集产物（视频等）落在这里，compose 里挂共享卷到下载器容器
ENV DATA_DIR=/data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
