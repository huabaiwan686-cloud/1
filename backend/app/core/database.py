"""数据库会话。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import logging

log = logging.getLogger(__name__)

from app.core.config import settings

connect_args = {"check_same_thread": False, "timeout": 30} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
# SQLite WAL 模式：读写不互堵，解决"database is locked"导致发布失败
# WAL 让读和写可以并发，写锁等待 30 秒而不是 5 秒
if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 秒等待锁
        cursor.execute("PRAGMA synchronous=NORMAL")  # WAL 模式下安全且更快
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401 触发模型注册

    Base.metadata.create_all(bind=engine)


# 34 个省级行政区：监听关键词（北京/广东…）直接映射，无需手动录入
PROVINCES = [
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省", "上海市", "江苏省",
    "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区",
    "海南省", "重庆市", "四川省", "贵州省", "云南省",
    "西藏自治区", "陕西省", "甘肃省", "青海省", "宁夏回族自治区",
    "新疆维吾尔自治区", "香港特别行政区", "澳门特别行政区", "台湾省",
]


