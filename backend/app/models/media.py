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
    """图片处理任务。mode: replace_bg/blur_bg/original"""

    __tablename__ = "image_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String(16), default="替换背景")
    # replace_bg=背景替换 / blur_bg=背景虚化 / original=原图
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


class WatermarkSetting(Base):
    """个人水印设置（P1-14）：按作者（user_id）覆盖发布时的水印。

    type: text=文字水印 / qr=二维码水印
    content: 文字内容 或 二维码数据（链接/文本）
    position: top-left/top-right/bottom-left/bottom-right/center
    """

    __tablename__ = "watermark_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(16), default="text")
    content: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[str] = mapped_column(String(16), default="bottom-right")
    opacity: Mapped[float] = mapped_column(Integer, default=70)  # 0-100 百分比，兼容 SQLite
    qr_size: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
