# anan-agent

抖音视频批量采集 → 内容提取（ASR 为主，OCR 兜底）→ LLM 分类 → 按类别构建 AI 智能体。

## 技术栈

- **后端**：FastAPI + PostgreSQL(pgvector) + LangGraph + SSE 流式对话
- **采集**：TikTokDownloader（Web API 模式，独立容器）
- **ASR**：faster-whisper（本地运行，字幕主来源）
- **OCR**：RapidOCRAPI（本地 Docker，ASR 失败时手动兜底）
- **前端**：Vue3 + Ant Design Vue + Sass（深色/浅色双主题）

## 快速开始

```bash
# 0. 准备配置（首次）
cp backend/.env.example backend/.env   # 填入 LLM/Embedding/数据库等配置

# 1. 启动基础设施（PostgreSQL+pgvector / RapidOCR / TikTokDownloader）
docker compose up -d

# 2. 一键启动前后端（开发模式）
./dev.sh        # Git Bash
dev.bat         # 或 CMD / 双击
```

> TikTokDownloader 首次启动需交互配置（语言/免责声明/运行模式），本仓库已
> 通过 Volume 持久化预置为 Web API 模式（5555）。采集抖音数据前需先写入
> Cookie（参考其 Wiki 的 Cookie 获取教程）。

首次运行需先装依赖：

```bash
cd backend && python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cd ../frontend && npm install
```

- 前端 http://localhost:5173 ，后端 API 文档 http://localhost:8000/docs
- **登录**：首次启动自动创建超管账号 `admin / 123456`（请尽快修改）
- 后端也可单独启动：`cd backend && .venv/Scripts/activate && python run.py`

### 演示数据

```bash
cd backend && ./.venv/Scripts/python.exe scripts/seed_demo.py
```

幂等脚本，覆盖流水线各状态（pending/downloaded/asr_done/classified/indexed/failed）、
三个示例智能体（诗歌/阴阳怪气/科普）、高赞评论和真实语料向量，种子后对话页即可体验 RAG 检索。

## 流水线

```
pending → downloaded → asr_done → classified → indexed
```

- 字幕统一走 ASR（faster-whisper）；识别为空视为失败进入 `failed`
- **OCR 是手动兜底**：在视频库对 ASR 失败的视频点「OCR 补字幕」或顶部「批量 OCR」，
  成功后自动接力后续分类和入库
- 每步独立可重试，失败可通过 `POST /api/collect/retry/{video_id}` 重跑

## 智能体对话

- 每个类别对应一个智能体（人格 Prompt + 类别隔离的 RAG 语料检索）
- `POST /api/chat/stream`：SSE 流式返回，支持多轮上下文（最近 20 条），
  返回耗时和 token 用量；消息持久化，支持历史会话列表
- `POST /api/chat`：非流式接口（简单调用/测试用）

## 目录结构

```
backend/app/
├── api/         # 路由：auth / collect / videos / categories / chat(SSE) / conversations / config
├── clients/     # 外部服务封装：douyin / ocr / asr / llm / embedding
├── pipeline/    # 流水线：orchestrator(状态机) / classifier / indexer
├── agents/      # LangGraph：graph(路由+RAG+生成) / discovery(类别发现，待实现)
├── models/      # SQLAlchemy：video / comment / category / corpus / conversation / user
├── core/        # config(动态配置) / database / security(认证)
└── scripts/     # seed_demo.py 演示数据

frontend/src/
├── views/       # Login / Collect / Videos / Categories / Chat(三栏) / Settings
├── composables/ # auth(登录态) / theme(深浅色切换)
└── api/         # axios 封装（自动带 token，401 自动登出）
```

## 注意

- `backend/app/clients/douyin.py` 中的 API 路径为占位，需对照 TikTokDownloader 运行时的
  `/docs` 页面微调。
- 需要本机安装 ffmpeg 并加入 PATH（抽帧和抽音轨都依赖它）。
- `backend/.env` 含密钥，已在 .gitignore 中排除；生产部署请修改 `SECRET_KEY` 和管理员密码。
