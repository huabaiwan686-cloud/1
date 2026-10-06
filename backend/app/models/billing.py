"""变现数据模型：VIP 订单/订阅/图片额度 / 邀请码/邀请记录。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VipOrder(Base):
    """VIP 订单：100USDT/30天。"""

    __tablename__ = "vip_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(16), default="pro")  # starter/pro
    amount_usdt: Mapped[float] = mapped_column(Numeric(10, 2), default=100)
    days: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/paid/cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pay_txid: Mapped[str] = mapped_column(String(128), default="", index=True)  # 匹配到的链上转账 txid（防一笔转账开多单）


class VipSubscription(Base):
    """租户订阅：按租户开通，全团队共享。"""

    __tablename__ = "vip_subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan: Mapped[str] = mapped_column(String(16), default="starter")
    active_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ImageQuota(Base):
    """图片处理额度：按月重置。"""

    __tablename__ = "image_quotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month: Mapped[str] = mapped_column(String(7), unique=True, index=True)  # YYYY-MM
    monthly_quota: Mapped[int] = mapped_column(Integer, default=0)
    monthly_used: Mapped[int] = mapped_column(Integer, default=0)
    extra_quota: Mapped[int] = mapped_column(Integer, default=0)
    extra_used: Mapped[int] = mapped_column(Integer, default=0)


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InviteRecord(Base):
    """邀请记录：绑定 TG 送 1 天→3 天；好友首开月卡送 30 天。"""

    __tablename__ = "invite_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    invitee: Mapped[str] = mapped_column(String(128), default="")
    tg_bound: Mapped[bool] = mapped_column(Boolean, default=False)
    first_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    reward_days: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
