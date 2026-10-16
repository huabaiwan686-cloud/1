"""账号体系数据模型：TG 协议号 / Bot Token / 双向机器人 / 好友关系 / 平台绑定与合作。"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, BigInteger, Index, String, Text
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
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 最后检测时间


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
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)  # 所属用户（多租户隔离）
    submission_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # 投稿 Bot：收混合媒体+验证视频，自动建资料并按网站设置发布
    webhook_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Webhook secret_token，防止伪造 POST
    submission_channel_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 投稿目标频道（空=该用户全部启用频道）


class BotSubmission(Base):
    """投稿 Bot 收到的内容：混合媒体+文字 + 验证视频，分步收集后自动建资料发布。"""

    __tablename__ = "bot_submissions"
    __table_args__ = (Index("ix_bot_submissions_lookup", "bot_token_id", "state", "chat_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_token_id: Mapped[int] = mapped_column(Integer, ForeignKey("bot_tokens.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))  # 网站用户（Bot 所属）
    tg_user_id: Mapped[int] = mapped_column(BigInteger)  # 发送人的 TG 用户 ID（64 位）
    tg_username: Mapped[str] = mapped_column(String(128), default="")
    chat_id: Mapped[int] = mapped_column(BigInteger)  # TG chat_id 是 64 位
    state: Mapped[str] = mapped_column(String(16), default="waiting_show")  # waiting_show/waiting_verify/done/failed
    show_media: Mapped[list] = mapped_column(JSON, default=list)  # [{url, media_type}]
    verify_media: Mapped[list] = mapped_column(JSON, default=list)  # [{url, media_type}]
    caption: Mapped[str] = mapped_column(Text, default="")  # 混合媒体的文字
    note_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 建好的资料 ID
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



class PlatformBinding(Base):
    """平台绑定：租户资料展示平台授权。"""

    __tablename__ = "platform_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 归属用户（隔离）
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
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 归属用户（隔离）
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
