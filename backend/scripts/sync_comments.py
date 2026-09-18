"""把模型里的表/字段注释同步到现有数据库（COMMENT ON TABLE / COLUMN）。

create_all 不会修改已存在的表，PostgreSQL 需要显式 COMMENT ON。
幂等，可重复执行。

用法：cd backend && ./.venv/Scripts/python.exe scripts/sync_comments.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app import models  # noqa: F401  确保模型已注册
from app.core.database import Base, engine


def main():
    count = 0
    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            if table.comment:
                conn.execute(
                    text(f'COMMENT ON TABLE "{table.name}" IS :c'),
                    {"c": table.comment})
                count += 1
            for col in table.columns:
                if col.comment:
                    conn.execute(
                        text(f'COMMENT ON COLUMN "{table.name}"."{col.name}" IS :c'),
                        {"c": col.comment})
                    count += 1
    print(f"已同步 {count} 条注释")


if __name__ == "__main__":
    main()
