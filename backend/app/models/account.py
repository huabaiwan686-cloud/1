"""账号体系数据模型：TG 协议号 / Bot Token / 双向机器人 / 好友关系 / 平台绑定与合作。"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TgAccount(Base):
    """TG 协议号（MTProto）：采集/监听/推送的执行身份。"""

    __tablename__ = "tg_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[str] = mapped_column(String(128), default="")
    tg_user_id: Mapped[str] = mapped_column(String(64), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    session_secret: Mapped[str] = mapped_column(Text, default="")  # 加密后的 session
    status: Mapped[str] = mapped_column(String(16), default="offline")  # online/offline/expired
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)  # 所属人（空=公共）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BotToken(Base):
    """Bot Token：频道发布与通知。"""

    __tablename__ = "bot_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    username: Mapped[str] = mapped_column(String(128), default="")
    token_secret: Mapped[str] = mapped_column(Text, default="")  # 加密存储
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TwoWayBot(Base):
    """双向机器人：TG 账号 + Bot Token 绑定管理群。"""

    __tablename__ = "two_way_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_token_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("bot_tokens.id"), nullable=True)
    tg_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tg_accounts.id"), nullable=True)
    group_id: Mapped[str] = mapped_column(String(64), default="")
    group_name: Mapped[str] = mapped_column(String(128), default="")
    invite_link: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FriendRelation(Base):
    """好友关注关系。direction: following/follower/request/blocked/public"""

    __tablename__ = "friend_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tg_accounts.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(128), index=True)
    direction: Mapped[str] = mapped_column(String(16), default="following")
    profile: Mapped[dict] = mapped_column(JSON, default=dict)  # 简介/笔记数/粉丝数等
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PlatformBinding(Base):
    """平台绑定：租户资料展示平台授权。"""

    __tablename__ = "platform_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bind_code: Mapped[str] = mapped_column(String(128))
    platform_name: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CooperationApplication(Base):
    """平台合作：合作机器人申请。"""

    __tablename__ = "cooperation_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    applicant: Mapped[str] = mapped_column(String(128), default="")
    bot_username: Mapped[str] = mapped_column(String(128), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    review_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    join_status: Mapped[str] = mapped_column(String(16), default="pending")
    channel_result: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CooperationConfig(Base):
    """合作配置：合作机器人 + 上架频道 + 是否需要审核。"""

    __tablename__ = "cooperation_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    two_way_bot_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("two_way_bots.id"), nullable=True)
    notify_mode: Mapped[str] = mapped_column(String(32), default="two_way_group")
    channel_ids: Mapped[list] = mapped_column(JSON, default=list)
    need_review: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class TgDialog(Base):
    """TG 会话缓存：协议号可见的群组/频道列表，推送目标选择用（刷新缓存更新）。"""

    __tablename__ = "tg_dialogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)
    chat_id: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(String(256), default="")
    username: Mapped[str] = mapped_column(String(128), default="")
    kind: Mapped[str] = mapped_column(String(16), default="group")  # group/channel/user
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ManagedBotRequest(Base):
    """官方一键创建（Managed Bots）待办：用户在手机上点确认后，worker 拉取 token 入库。"""

    __tablename__ = "managed_bot_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)  # 要建的子机器人用户名
    name: Mapped[str] = mapped_column(String(128), default="")
    requested_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/done/failed
    bot_token_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("bot_tokens.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
