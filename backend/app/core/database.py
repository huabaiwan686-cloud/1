"""数据库会话。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import logging

log = logging.getLogger(__name__)

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
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
    _seed_provinces()


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


def _seed_provinces() -> None:
    """幂等：逐个补齐 34 省级地区（旧库有部分数据时也不漏种）。"""
    from app.models.content import City

    db = SessionLocal()
    try:
        existing = {r[0] for r in db.query(City.name).all()}
        added = 0
        for name in PROVINCES:
            if name not in existing:
                db.add(City(name=name, level=1))
                added += 1
        if added:
            db.commit()
            log.info("补种省级地区 %d 个", added)
    finally:
        db.close()
