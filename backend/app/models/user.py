"""用户模型。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # 登录账号
    display_name: Mapped[str] = mapped_column(String(64), default="")  # 账号名称
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    invited_by_code: Mapped[str] = mapped_column(String(16), default="")  # 注册时填写的邀请码
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
