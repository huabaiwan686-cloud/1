"""图片处理数据模型：背景素材库 / 处理任务 / 全局设置。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BackgroundMaterial(Base):
    """背景素材库：替换背景用。"""

    __tablename__ = "background_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), default="未命名素材")
    url: Mapped[str] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(32), default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ImageJob(Base):
    """图片处理任务。mode: replace_bg/light_perturb/original"""

    __tablename__ = "image_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String(16), default="light_perturb")
    # replace_bg=背景替换 / blur_bg=背景虚化 / light_perturb=轻量扰动 / original=原图
    status: Mapped[str] = mapped_column(String(16), default="processing")
    source: Mapped[str] = mapped_column(String(512), default="")  # 原图标识/URL
    result_url: Mapped[str] = mapped_column(String(512), default="")
    background_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否降级为轻量扰动
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GlobalSetting(Base):
    """全局键值设置（如全局抠图模式开关/背景）。"""

    __tablename__ = "global_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
