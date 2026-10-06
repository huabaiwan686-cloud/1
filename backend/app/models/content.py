"""内容流数据模型：标签 / 城市 / 笔记 / 媒体 / 采集规则 / 采集频道 / 任务日志。"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Tag(Base):
    """标签：新建需审核。"""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="approved")  # pending/approved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class City(Base):
    """城市级联（省/市）。"""

    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cities.id"), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)  # 1=省 2=市


class Note(Base):
    """笔记/资料：内容库核心。status: draft/pending/published/offline"""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)  # 标签名列表
    city_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cities.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual/collect
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 所属上架账号
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)  # 创建人（采集端内容/记录用）
    channel_ids: Mapped[list] = mapped_column(JSON, default=list)  # 目标频道 id 列表
    service_remark: Mapped[str] = mapped_column(Text, default="")  # 客服备注（仅后台可见）
    number_code: Mapped[str] = mapped_column(String(64), default="")  # 编号/标识
    fee_text: Mapped[str] = mapped_column(String(255), default="")  # 介绍费文案
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 定时上架
    scheduled_sent: Mapped[bool] = mapped_column(Boolean, default=False)  # 定时已由 worker 发送（幂等）
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collect_rule_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("collect_rules.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NoteMedia(Base):
    """笔记媒体：展示资料(show)/验证资料(verify)，可拖拽排序。"""

    __tablename__ = "note_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[int] = mapped_column(Integer, ForeignKey("notes.id"), index=True)
    url: Mapped[str] = mapped_column(String(512))
    media_type: Mapped[str] = mapped_column(String(16), default="image")  # image/video
    kind: Mapped[str] = mapped_column(String(16), default="show")  # show/verify
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CollectRule(Base):
    """代理采集规则：文案处理 / 文本替换 / 图文去重 / 屏蔽规则。"""

    __tablename__ = "collect_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    target_channels: Mapped[list] = mapped_column(JSON, default=list)  # 目标频道 id
    global_apply: Mapped[bool] = mapped_column(Boolean, default=False)  # 全局应用
    need_review: Mapped[bool] = mapped_column(Boolean, default=True)  # 采集后需审核
    # 文案处理
    prefix_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    prefix_text: Mapped[str] = mapped_column(Text, default="")
    suffix_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    suffix_text: Mapped[str] = mapped_column(Text, default="")
    # 文本替换
    replace_rules: Mapped[list] = mapped_column(JSON, default=list)  # [{from, to}]
    clean_identifiers: Mapped[bool] = mapped_column(Boolean, default=False)  # 清理编号和介绍费标识
    fee_suffix_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    fee_suffix_text: Mapped[str] = mapped_column(String(255), default="")
    delete_texts: Mapped[list] = mapped_column(JSON, default=list)  # 命中删除的文本
    delete_line_keywords: Mapped[list] = mapped_column(JSON, default=list)  # 命中删整行的关键词
    # 图文去重
    dedup_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    dedup_window_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    dedup_days: Mapped[int] = mapped_column(Integer, default=30)
    # 屏蔽规则
    block_links: Mapped[bool] = mapped_column(Boolean, default=True)
    block_usernames: Mapped[bool] = mapped_column(Boolean, default=True)
    block_plain_text: Mapped[bool] = mapped_column(Boolean, default=True)
    block_texts: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CollectChannel(Base):
    """采集频道：来源为账号/BOT/好友关注。"""

    __tablename__ = "collect_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    source_type: Mapped[str] = mapped_column(String(16), default="account")  # account/bot/friend
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 采集账号
    source_target: Mapped[str] = mapped_column(String(255), default="")  # 来源频道/群
    rule_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("collect_rules.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_msg_id: Mapped[int] = mapped_column(Integer, default=0)  # 采集水位：已处理的最大消息 id
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TaskLog(Base):
    """任务记录：推送/采集/上下架等动作日志。"""

    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("notes.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(32), index=True)  # publish/offline/collect/push/...
    executor: Mapped[str] = mapped_column(String(64), default="")  # 执行方
    result: Mapped[str] = mapped_column(String(16), default="success")  # success/fail/processing
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Announcement(Base):
    """系统公告：登录后弹窗展示。"""

    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
