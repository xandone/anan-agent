"""演示种子数据：覆盖流水线的各种状态和场景。

用法：cd backend && ./.venv/Scripts/python.exe scripts/seed_demo.py

场景覆盖：
- 诗歌智能体/阴阳怪气智能体/科普智能体：完整走完流水线的 indexed 数据（含语料向量，可对话检索）
- classified / asr_done / downloaded / pending：卡在流水线各阶段的任务
- failed × 2：一个 ASR 失败（演示 OCR 兜底按钮）、一个下载失败
- 未分类、人工改标、不同来源（热榜/达人/搜索/手动）、高低点赞量
"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients import embedding
from app.core.database import SessionLocal, init_db
from app.models import Category, Comment, Corpus, Video, VideoStatus

random.seed(42)

NOW = datetime.utcnow()


def days_ago(n):
    return NOW - timedelta(days=n, hours=random.randint(0, 20))


# (aweme_id, 标题, 话题, 作者, 点赞, 评论数, ASR文本, 评论列表[(文本,赞)])
POEM_DATA = [
    ("7300000000000000011", "写给你的第一百首诗｜今晚的月亮不用还", ["现代诗", "原创诗歌"], "山野诗人", 128000, 3400,
     "我把黄昏折成一只纸船，放进你眼里的河。风从远山来，带着松脂和旧雪的味道。你说月亮是借来的灯，我说没关系，今晚的月亮不用还。",
     [("读到第三句突然鼻酸，月亮不用还，那我借走的青春呢", 45200),
      ("这个up主写诗从不无病呻吟，难得", 12800),
      ("请问可以摘抄吗？想写进给奶奶的信里", 8600)]),
    ("7300000000000000012", "地铁十四行：给所有晚高峰里沉默的人", ["十四行诗", "城市"], "地铁诗人阿九", 89000, 2100,
     "我们把自己折叠进车厢，像一封封没有地址的信。隧道很黑，灯一站一站地亮，像我们心里那些不肯熄灭的东西。到站了，请把疲惫留在座位上。",
     [("把疲惫留在座位上，明天还要接着用", 38900),
      ("在地铁上刷到这个，差点哭出来", 21000),
      ("十四行写晚高峰，荒诞又准确", 9800)]),
    ("7300000000000000013", "二十四节气写诗挑战·霜降", ["节气", "诗歌挑战"], "山野诗人", 56000, 1500,
     "霜降下来的时候，柿子红得正好。奶奶说霜打过的柿子才甜，人也一样。我把这句话写进诗里，霜落在纸上，也落在我回家的脚印里。",
     [("霜打过的柿子才甜，人也一样——奶奶是哲学家", 23400),
      ("这个系列追了半年，一期不落", 11200),
      ("霜落在纸上，也落在回家的脚印里，太会写了", 8900)]),
]

SARCASM_DATA = [
    ("7300000000000000021", "如何优雅地回复领导的深夜消息", ["职场", "阴阳怪气"], "职场老阴阳", 234000, 8900,
     "领导半夜十二点发消息问在吗，你要秒回：在呢领导，刚睡下，梦到您给我安排工作，我赶紧醒了。配图一杯咖啡。第二天全公司都知道你敬业的感人事迹。",
     [("学了，领导说我阴阳他，我说您过奖了", 89300),
      ("建议配合'收到，马上办'食用，效果更佳", 45200),
      ("试过了，现在人在人才市场，谢谢up主", 38100)]),
    ("7300000000000000022", "当你有个特别'为你好'的亲戚", ["亲戚", "过年"], "嘴替小王", 187000, 6700,
     "二姑问你工资多少，你就说不多不多，刚好够给您孙子包红包。她问你什么时候结婚，你说快了快了，就等国家分配。她夸你有出息，你说都是遗传了您家好基因。",
     [("国家分配这句我用上了，全桌沉默了三秒", 67800),
      ("每句话都客气得无懈可击，又句句扎心，绝了", 34500),
      ("收藏了，过年回家全文背诵", 28900)]),
    ("7300000000000000023", "健身房里的优雅社交", ["健身", "社交"], "职场老阴阳", 96000, 3200,
     "大哥占着器械刷手机，你走过去说：哥，您这器械保养得真好，一看就是天天擦。他要还不起来，你就夸他手机里的小说真好看，看得连组间休息都忘了。",
     [("小说真好看这句绝了，骂人不带脏字", 42100),
      ("我们健身房就有这种大哥，明天就去试试", 19800),
      ("礼貌得让人无法反驳，这才是语言的艺术", 12400)]),
]

SCIENCE_DATA = [
    ("7300000000000000031", "为什么退烧药不能交替吃？药师讲透了", ["科普", "用药安全"], "药师小周", 156000, 4300,
     "对乙酰氨基酚和布洛芬交替吃并不能退烧更快，反而容易算错剂量伤肝。记住一个原则：选一种，按体重算量，间隔六小时。烧退不下来先想补液和就医，别急着加药。",
     [("家里老人就爱交替喂，已转发到家族群", 51400),
      ("讲得太清楚了，比很多说明书都明白", 23600),
      ("请问大人也是间隔六小时吗？在线等", 8900)]),
    ("7300000000000000032", "微波炉加热葡萄为什么会冒火花", ["物理", "冷知识"], "实验室小吴", 201000, 7800,
     "两颗挨在一起的葡萄在微波炉里会产生等离子体火花。因为葡萄尺寸刚好和微波波长形成共振，接触点的电场强度被放大了几千倍，空气直接被电离。千万别试，微波炉会废。",
     [("省流：千万别试，微波炉会废", 72300),
      ("所以那颗葡萄是被物理定律选中的葡萄", 31500),
      ("我是物理老师，下周课堂素材有了", 15600)]),
]

# 卡在流水线各阶段的任务
MISC_DATA = [
    ("7300000000000000041", "凌晨四点的城市环卫工", ["纪实", "城市"], "街头观察员", 67000, 1800,
     "classified", "classified", None),  # 已分类待入库
    ("7300000000000000042", "菜市场里的物价观察日记", ["生活", "物价"], "街头观察员", 45000, 1200,
     "asr_done", "asr_done", None),  # 已转写待分类
    ("7300000000000000043", "老手艺：修表匠的一天", ["手艺人", "纪实"], "时间的朋友", 88000, 2600,
     "downloaded", "downloaded", None),  # 已下载待转写
    ("7300000000000000044", "雨夜便利店速写", ["vlog", "生活"], "便利蜂", 23000, 800,
     "pending", "pending", None),  # 待下载
    ("7300000000000000045", "纯音乐｜雪山延时摄影", ["纯音乐", "风景"], "风光佬", 134000, 2100,
     "failed", "failed", "step_asr: ASR 未识别到语音内容"),  # ASR 失败，演示 OCR 兜底
    ("7300000000000000046", "某达人已删除的作品", ["日常"], "已注销用户", 1200, 60,
     "failed", "failed", "step_download: 下载失败或文件不存在"),  # 下载失败
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        cats = {c.slug: c for c in db.query(Category).all()}
        assert {"poem", "sarcasm", "science"} <= set(cats), "请先确保三个示例类别存在"

        created = 0
        indexed_videos = []

        def add_video(aweme_id, title, tags, author, digg, ccount,
                      asr_text, comments, status, source, category=None,
                      confidence=None, classify_source="llm", error=None,
                      local_path=None):
            nonlocal created
            if db.query(Video).filter_by(aweme_id=aweme_id).first():
                return None
            v = Video(
                aweme_id=aweme_id, url=f"https://www.douyin.com/video/{aweme_id}",
                title=title, hashtags=tags, author_name=author,
                author_id=f"sec_{author}", digg_count=digg, comment_count=ccount,
                share_count=digg // 20, publish_time=days_ago(random.randint(1, 60)),
                source=source, status=VideoStatus(status), error=error,
                asr_text=asr_text, local_path=local_path,
                category_id=category.id if category else None,
                classify_confidence=confidence, classify_source=classify_source if category else None,
            )
            db.add(v)
            db.flush()
            for i, (text, likes) in enumerate(comments):
                db.add(Comment(comment_id=f"{aweme_id}_c{i}", video_id=v.id,
                               text=text, digg_count=likes))
            db.flush()
            created += 1
            return v

        # --- 完整走完流水线的数据 ---
        for slug, rows, source in [("poem", POEM_DATA, "hot"),
                                   ("sarcasm", SARCASM_DATA, "account"),
                                   ("science", SCIENCE_DATA, "hot")]:
            for aweme_id, title, tags, author, digg, cc, asr_text, comments in rows:
                v = add_video(aweme_id, title, tags, author, digg, cc, asr_text,
                              comments, "indexed", source, cats[slug],
                              round(random.uniform(0.82, 0.97), 2))
                if v:
                    indexed_videos.append(v)

        # --- 各阶段的半成品 ---
        for aweme_id, title, tags, author, digg, cc, status, _, error in MISC_DATA:
            extra = {}
            if status == "classified":  # 人工改标场景：LLM 分错，人改回来了
                extra = dict(category=cats["science"], confidence=1.0,
                             classify_source="human",
                             asr_text="今天凌晨四点跟着环卫工张师傅走了一条街，他说这城市醒来之前的样子，只有他们见过。")
            elif status == "asr_done":
                extra = dict(asr_text="白菜两块八，西红柿四块五，摊主说今年雨水多，菜价就这么一点点涨上来了。")
            elif status == "downloaded":
                extra = dict(local_path=f"data/videos/{aweme_id}.mp4")
            elif status == "failed" and "step_asr" in (error or ""):
                extra = dict(local_path=f"data/videos/{aweme_id}.mp4")  # 可点 OCR 兜底
            v = add_video(aweme_id, title, tags, author, digg, cc,
                          extra.get("asr_text"), [], status, "manual",
                          category=extra.get("category"),
                          confidence=extra.get("confidence"),
                          classify_source=extra.get("classify_source", "llm"),
                          error=error, local_path=extra.get("local_path"))

        db.commit()
        print(f"视频 {created} 条，评论已随视频创建")

        # --- 为 indexed 视频生成语料向量 ---
        if indexed_videos:
            texts, owners = [], []
            for v in indexed_videos:
                texts.append(v.full_text[:2000])
                owners.append((v, "video", None))
                for c in sorted(v.comments, key=lambda x: x.digg_count, reverse=True)[:20]:
                    texts.append(c.text[:2000])
                    owners.append((v, "comment", c.id))
            print(f"生成 {len(texts)} 条语料向量…")
            try:
                vectors = embedding.embed(texts)
            except Exception as e:
                print(f"Embedding API 不可用({e})，退化为随机向量（对话检索将无语义）")
                vectors = [[random.gauss(0, 1) for _ in range(1024)] for _ in texts]
            for (v, ctype, cid), vec, content in zip(owners, vectors, texts):
                db.add(Corpus(video_id=v.id, comment_id=cid, category_id=v.category_id,
                              content=content, content_type=ctype, embedding=vec))
            db.commit()
            print(f"语料向量 {len(texts)} 条已入库")

        print("种子数据完成")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
