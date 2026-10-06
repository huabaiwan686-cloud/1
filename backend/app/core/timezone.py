"""时区工具：用户输入按 Asia/Shanghai 解释，库里统一存 naive UTC。"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc


def now_utc() -> datetime:
    """当前 UTC naive 时间（与 datetime.utcnow() 一致，用于 DB 比较）。"""
    return datetime.now(UTC).replace(tzinfo=None)


def local_to_utc_naive(dt: datetime) -> datetime:
    """用户本地时间（naive，视为 Asia/Shanghai）→ naive UTC。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(UTC).replace(tzinfo=None)


def utc_naive_to_local(dt: datetime) -> datetime:
    """naive UTC → Asia/Shanghai 本地时间（naive）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(LOCAL_TZ).replace(tzinfo=None)


def today_local_start_utc() -> datetime:
    """本地今天 0 点对应的 naive UTC（用于“今日”统计）。"""
    local_now = datetime.now(LOCAL_TZ)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(UTC).replace(tzinfo=None)
