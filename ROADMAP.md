# anan-agent 下一阶段优化与拓展方案

> 生成时间：2026-09-18；上次审查更新：2026-09-24
> 状态说明：⬜ 未开始 / 🔶 进行中 / ✅ 完成
> 本文档为下一阶段 TODO 参照，完成后更新状态。

---

## 本期已完成（自 2026-09-18 起）

- ✅ **#3 pgvector 向量索引**：`init_db()` 启动时幂等创建 HNSW 索引（`ix_corpus_embedding`，cosine ops）（[database.py:33-42](backend/app/core/database.py#L33-L42)，commit bd97524）
- ✅ **③ 数据看板**：`GET /api/dashboard/summary` 聚合接口 + Dashboard 首页（状态分布、来源分布、14 天采集趋势、类别分布、语料/评论统计）（commit 6bd7c52）
- ✅ **用户系统/登录**（ROADMAP 外新增）：User 模型 + JWT 登录页 + 初始超管 admin
- ✅ **智能体编辑/删除 + AI 草稿**：`PUT/DELETE /api/categories/{id}`、`POST /api/categories/ai-draft`（LLM 生成 slug/描述/人格 Prompt）（commit f44ddfa、8ef00c1）
- ✅ **点赞采集**：`POST /api/collect/likes`，未公开时返回 403 明确报错（commit 19f253c）
- ✅ **下载共享卷**：tiktok-downloader 与 backend 挂载同一 `video-data` 卷，容器内路径互通（commit 2c5d367）
- ✅ **对话深度思考开关 + 停止生成**：SSE 转发 reasoning 事件，停止时半成品落库

---

## 一、后端优化

### P0 — 影响核心链路可用性

- [ ] **1. 采集层联调（最大风险）** 🔶
  - 现状：`backend/app/clients/douyin.py` 的接口路径仍是占位（多个 `# TODO: 对照 /docs 确认`），从未和真实 TikTokDownloader 逐字段验证；基础设施已就位（compose 共享卷、路径映射 `_file_url`），具备联调条件
  - 方案：启动 TikTokDownloader 后对照 `/docs` 逐字段联调；封装层加响应字段适配器；加联调测试脚本
  - 文件：`backend/app/clients/douyin.py`

- [ ] **2. 任务队列**
  - 现状：`api/collect.py` 仍用 FastAPI `BackgroundTasks` 逐条 `bg.add_task(run_video, vid)`，热榜 50 个视频瞬间并发 50 条流水线；进程重启任务全丢；无限速（风控硬伤）
  - 方案：Dramatiq/RQ + Redis（比 Celery 轻）；过渡方案：任务表 + APScheduler + 并发信号量，先做到串行化 + 可恢复 + 限速

- [ ] **8. 会话与用户关联（升级：登录已上线，现为数据隔离漏洞）**
  - 现状：用户系统已落地，但 `conversations` 表无 user_id，`GET /api/conversations` 把**全部用户的会话**返回给任何登录用户
  - 方案：conversations/chat_messages 加 user_id 外键，所有会话查询按当前用户过滤；存量数据归 admin

### P1 — 影响可维护性和数据质量

- [ ] **4. 流水线并发锁**
  - 现状：retry/批量采集/OCR 接力可重复触发同一条视频并发处理；`run_video` 无任何占用标记
  - 方案：加 `processing` 状态或分布式锁（可随 #2 任务队列一并解决）

- [ ] **5. 数据库迁移机制**
  - 现状：仍是 `create_all` + 启动时手写 DDL 补丁（`_ensure_vector_index`、`_seed_admin`），表结构演进靠手工；#8 加字段即需要迁移能力
  - 方案：引入 Alembic（requirements 已装），把现有补丁式 DDL 收口为迁移脚本

- [ ] **6. 类别/模型变更后的重跑能力**
  - 现状：改类别定义、新增类别后老视频分类不更新；改 embedding 模型（dim 变化）corpus 不兼容；`api/videos.py` 只有单条 relabel，无批量重分类/重建索引接口
  - 方案：「批量重分类」「重建向量库」管理接口 + embedding 模型版本字段

- [ ] **7. 低置信度复核流程**
  - 现状：`classify_confidence_threshold=0.7` 仍只躺在配置里；`classifier.py` 存了 confidence 但不判断阈值；videos 表无 `needs_review` 标记，视频库无"待复核"筛选
  - 方案：`classified` 增加 `needs_review` 标记，低于阈值自动置位；视频库加"待复核"筛选；人工 relabel 时清除标记

### P2 — 效果增强

- [ ] **9. RAG 混合检索**
  - 现状：`graph.py retrieve_contexts` 只有向量余弦距离 + 阈值过滤
  - 方案：向量 + `tsvector` 关键词混合 + rerank + 时间衰减（热点语料有时效）

- [ ] **10. 长会话历史压缩**
  - 现状：`api/chat.py` 最近 20 条原文全塞进上下文（`HISTORY_LIMIT = 20`），token 浪费
  - 方案：超过 N 轮后对早期历史做摘要压缩

- [ ] **11. 类别发现落地**
  - 现状：`backend/app/agents/discovery.py` 仍是空实现（返回 `[]`）
  - 方案：HDBSCAN 聚类 + LLM 命名 + 一键建类（可复用 `ai-draft` 的人格生成链路）

---

## 二、前端优化

- [ ] **12. 视频详情抽屉（P1）**
  - 现状：Videos.vue 列表仍只有元数据 + 状态，OCR/ASR 文本、高赞评论、失败原因都看不到，调试分类质量等于盲调（后端详情接口 `GET /api/videos/{id}` 已有）
  - 方案：加详情抽屉，展示 full_text、评论列表、error、视频预览（`file_url` 已返回）

- [ ] **13. 任务进度反馈（P1）**
  - 现状：采集/OCR 提交后仍是一次性 `setTimeout(5000)` 刷新（Videos.vue:95/109），慢任务看不到进展
  - 方案：流水线传送带改定时轮询（进行中才轮询）或 SSE 推送状态

- [ ] **14. 配置连接测试**
  - 现状：Settings.vue 改完 LLM/Embedding 配置不知道通不通；`api/config.py` 无 ping 接口
  - 方案：配置页每个模型加"测试连接"按钮（后端加 ping 接口，顺带校验 embedding_dim 与实际返回维度）

- [ ] **15. 对话体验细节**
  - 代码块语法高亮（markdown-it 配 highlight.js）——当前无高亮
  - 历史会话重命名/搜索——`api/conversations.py` 只有 list/detail/delete，无 rename 接口
  - 导出对话

- [ ] **16. 统一加载态**
  - 各页仍是裸 `a-spin`/按钮 loading，无骨架屏，加载体验不一致

---

## 三、可拓展的新模块

- [ ] **① 内容再创作（最推荐）**
  - 价值：语料的终极用途——"用阴阳怪气风格写一条关于 XX 的评论"，类别人格 + RAG 一键生成同风格文案/视频脚本，采集数据的直接变现路径
  - 成本：低（现有 Agent 链路加个生成模式，复用 SSE 流式）

- [ ] **② 定时调度**
  - 每日热榜自动采集、盯达人更新，语料库自我增长
  - 依赖：任务队列（#2）

- [ ] **④ 语料管理页**
  - 查看/编辑/删除 corpus、人工补充优质语料、改标后重建索引
  - 成本：低（依赖 #6 的重建索引能力）

- [ ] **⑤ 数据集导出**
  - 导出 JSONL（文本+类别标签），为后期微调小模型/LoRA 做准备
  - 成本：低

- [ ] **⑥ 智能体发布**
  - 把某个智能体发布成免登录分享链接或嵌入 widget
  - 成本：中（依赖 #8 会话用户隔离先做好）

- [ ] **⑦ 评论舆情**
  - 评论情感倾向、热词统计，辅助选题（评论数据已在采集，缺分析层）
  - 成本：中

- [ ] **⑧ 视觉理解**
  - DeepSeek V4 视觉实验模型，对封面/关键帧做画面理解，补 ASR+OCR 之外的第三路信号
  - 成本：中

---

## 四、推荐路线

1. **先补地基**（顺序执行）：#1 采集联调（基础设施已就绪，唯一阻塞项）→ #8 会话用户隔离（登录已上线，越早越便宜）→ #5 Alembic（#8 依赖迁移）→ #2 任务队列
2. **再补体验**：#12 视频详情抽屉 + #14 连接测试 + #7 待复核流程 + #13 进度轮询
3. **然后做变现**：① 内容再创作（看板已✅，做完项目从"玩具"变"工具"）
4. **最后做规模**：② 定时调度、#9 混合检索、#11 类别发现、④ 语料管理
