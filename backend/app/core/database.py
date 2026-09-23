from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """启用 pgvector 扩展并建表（骨架阶段用 create_all，后续可切 alembic）。"""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    from app import models  # noqa: F401  确保模型已注册
    Base.metadata.create_all(engine)
    _ensure_vector_index()
    _seed_admin()


def _ensure_vector_index() -> None:
    """corpus.embedding 的 HNSW 近似索引：create_all 建不了，用原生 DDL 补齐。

    幂等（IF NOT EXISTS），换库/重建后启动自动恢复。
    不用 CONCURRENTLY：它在事务里不可用，且启动时建索引无并发写入。
    """
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_corpus_embedding "
            "ON corpus USING hnsw (embedding vector_cosine_ops)"))


def _seed_admin() -> None:
    """首次启动创建超管账号 admin / 123456。"""
    from loguru import logger

    from app.core.security import hash_password
    from app.models.user import User, UserRole

    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add(User(username="admin", display_name="管理员",
                        password_hash=hash_password("123456"),
                        role=UserRole.ADMIN))
            db.commit()
            logger.warning("已创建初始超管账号 admin / 123456，请尽快修改密码")
    finally:
        db.close()
