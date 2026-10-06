"""分发数据模型：频道 / 消息模板 / 推送计划 / 快速推送 / 关键字监听。"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Channel(Base):
    """频道配置：上架/下架分组，绑定推送 Bot。"""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    username: Mapped[str] = mapped_column(String(128), default="")  # @username
    tg_channel_id: Mapped[str] = mapped_column(String(64), default="")
    bot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 推送 Bot
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 上架/下架
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # 默认选中
    cycle_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 循环 N 天
    anti_scan_mode: Mapped[str] = mapped_column(String(16), default="original")
    # original=原图 / replace_bg=替换背景 / light_perturb=轻量随机扰动
    variation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # 循环重发变体（防 TG 判重）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MessageTemplate(Base):
    """消息模板：群聊推送文案。"""

    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)  # 模板代码
    name: Mapped[str] = mapped_column(String(128), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    media: Mapped[list] = mapped_column(JSON, default=list)  # [{url, type}]
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PushPlan(Base):
    """推送计划：按天/时间点自动推送。"""

    __tablename__ = "push_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 推送账号
    template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("message_templates.id"), nullable=True)
    target_groups: Mapped[list] = mapped_column(JSON, default=list)  # 目标群组
    interval_days: Mapped[int] = mapped_column(Integer, default=1)  # 执行间隔 X 天
    interval_hours: Mapped[int] = mapped_column(Integer, default=0)  # 执行间隔 X 小时（>0 时优先按小时）
    times: Mapped[list] = mapped_column(JSON, default=list)  # 执行时间点 ["09:00"]
    multi_interval_seconds: Mapped[int] = mapped_column(Integer, default=0)  # 群组之间发送间隔 X 秒
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 上次执行
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuickPushTarget(Base):
    """快速推送目标：Bot 内一键群推。"""

    __tablename__ = "quick_push_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    target: Mapped[str] = mapped_column(String(255), default="")  # 群组标识
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ListenPlan(Base):
    """关键字监听计划。"""

    __tablename__ = "listen_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 监听账号
    targets: Mapped[list] = mapped_column(JSON, default=list)  # 监听群聊/频道
    keywords: Mapped[list] = mapped_column(JSON, default=list)  # 关键词
    bind_id: Mapped[str] = mapped_column(String(16), default="")  # 8 位绑定 ID
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    keyword_city_map: Mapped[dict] = mapped_column(JSON, default=dict)  # 自定义关键词→城市，如 {"京妞": "北京"}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ListenHit(Base):
    """监听命中记录：谁在哪个群触发了哪个城市，做了去重冷却。"""

    __tablename__ = "listen_hits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, index=True)
    tg_user_id: Mapped[int] = mapped_column(Integer, index=True)  # 触发者的 TG id
    tg_username: Mapped[str] = mapped_column(String(128), default="")
    city_id: Mapped[int | None] = mapped_column(Integer, index=True)
    city_name: Mapped[str] = mapped_column(String(64), default="")
    keyword: Mapped[str] = mapped_column(String(64), default="")  # 命中的关键词
    chat_title: Mapped[str] = mapped_column(String(255), default="")  # 触发群
    notes_sent: Mapped[int] = mapped_column(Integer, default=0)  # 发出的素材组数
    result: Mapped[str] = mapped_column(String(16), default="success")  # success/failed/skipped/claimed(发送中占位)
    detail: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # 同一键同一时间只允许一个 claimed 占位（防并发重复 DM）；
    # 完成后更新为 success/failed/skipped 即释放名额
    __table_args__ = (
        Index("uq_listen_hit_claimed", "plan_id", "tg_user_id", "city_id",
              unique=True,
              sqlite_where=(result == "claimed"),
              postgresql_where=(result == "claimed")),
    )


class PublishRule(Base):
    """智能频道推荐规则：按关键词/标签/城市/省份/价格区间自动匹配发布频道。"""

    __tablename__ = "publish_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    keyword: Mapped[str] = mapped_column(String(128), default="")  # 标题+正文包含
    tag: Mapped[str] = mapped_column(String(64), default="")  # 标签匹配
    city: Mapped[str] = mapped_column(String(64), default="")  # 正文"城市：北京"标注行
    province: Mapped[str] = mapped_column(String(64), default="")  # 正文"省份：xx"标注行
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)  # 价格区间
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    channel_ids: Mapped[list] = mapped_column(JSON, default=list)  # 命中的频道
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
