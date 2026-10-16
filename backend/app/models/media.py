"""图片处理数据模型：背景素材库 / 处理任务 / 全局设置。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base




class GlobalSetting(Base):
    """全局键值设置（如全局抠图模式开关/背景）。"""

    __tablename__ = "global_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


