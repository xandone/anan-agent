"""用户表：角色 admin（超管，全部权限）/ user（预留，当前未启用）。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole:
    ADMIN = "admin"
    USER = "user"


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"comment": "用户表：登录账号，当前仅超管 admin 一个角色"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主键")
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True,
                                          comment="登录用户名")
    display_name: Mapped[str | None] = mapped_column(String(64), comment="显示名称")
    password_hash: Mapped[str] = mapped_column(String(256),
                                               comment="密码哈希（PBKDF2-SHA256，格式：salt$hash）")
    role: Mapped[str] = mapped_column(String(16), default=UserRole.USER,
                                      comment="角色：admin超管/user普通用户（预留）")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
