"""运营看板：/api/dashboard/stats（真实聚合）。"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.permissions import require_member
from app.api.deps import get_current_user, ok
from app.api.v1.vip import _get_or_create_quota
from app.core.database import get_db
from app.models.account import BotToken, TgAccount
from app.models.billing import VipSubscription
from app.models.content import Note, TaskLog
from app.models.distribution import Channel
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats(user: User = Depends(require_member), db: Session = Depends(get_db)):
    from app.core.timezone import today_local_start_utc
    day_start = today_local_start_utc()  # 本地今天 0 点（UTC naive）
    by_status = dict(
        db.query(Note.status, func.count(Note.id)).group_by(Note.status).all()
    )
    today_publishes = (
        db.query(func.count(TaskLog.id))
        .filter(TaskLog.action == "publish", TaskLog.created_at >= day_start)
        .scalar()
    )
    q = _get_or_create_quota(db)
    sub = db.query(VipSubscription).order_by(VipSubscription.id.desc()).first()
    active = bool(sub and sub.active_until and sub.active_until > datetime.utcnow())
    publish_failed = (
        db.query(func.count(TaskLog.id))
        .filter(TaskLog.action == "publish", TaskLog.result == "fail",
                TaskLog.created_at >= day_start)
        .scalar()
    )
    return ok({
        "notesTotal": db.query(func.count(Note.id)).scalar(),
        "notesByStatus": by_status,
        "todayPublishes": today_publishes or 0,
        "publishFailed": publish_failed or 0,
        "channelsActive": db.query(func.count(Channel.id)).filter(Channel.is_active.is_(True)).scalar(),
        "tgAccounts": db.query(func.count(TgAccount.id)).scalar(),
        "botTokens": db.query(func.count(BotToken.id)).scalar(),
        "quotaLeft": max(q.monthly_quota - q.monthly_used, 0) + max(q.extra_quota - q.extra_used, 0),
        "vipPlan": sub.plan if active else "starter",
        "vipActive": active,
    })


@router.get("/trend")
def trend(startDate: str = "", endDate: str = "",
          user: User = Depends(require_member), db: Session = Depends(get_db)):
    """趋势图：按天统计新增资料 / 发布成功 / 下架资料 / 发布失败。
    对标原站 GET /publish-admin/dashboard/trend?startDate&endDate&accountId?
    """
    from datetime import date, timedelta
    try:
        start = date.fromisoformat(startDate) if startDate else date.today() - timedelta(days=13)
        end = date.fromisoformat(endDate) if endDate else date.today()
    except ValueError:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "日期格式错误（YYYY-MM-DD）")
    if (end - start).days > 90:
        start = end - timedelta(days=89)

    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)

    def day_count(model, day, **filters):
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)
        q = db.query(func.count(model.id)).filter(
            model.created_at >= day_start, model.created_at < day_end)
        for k, v in filters.items():
            q = q.filter(getattr(model, k) == v)
        return q.scalar() or 0

    # 发布成功/失败走 TaskLog；下架走 Note(status=offline)
    new_notes, pub_ok, pub_fail, offlined = [], [], [], []
    for day in days:
        new_notes.append(day_count(Note, day))
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)
        pub_ok.append(
            db.query(func.count(TaskLog.id)).filter(
                TaskLog.action == "publish", TaskLog.result == "success",
                TaskLog.created_at >= day_start, TaskLog.created_at < day_end).scalar() or 0)
        pub_fail.append(
            db.query(func.count(TaskLog.id)).filter(
                TaskLog.action == "publish", TaskLog.result == "fail",
                TaskLog.created_at >= day_start, TaskLog.created_at < day_end).scalar() or 0)
        # 下架：用 updated_at 近似（Note 无下架时间字段时）
        offlined.append(
            db.query(func.count(Note.id)).filter(
                Note.status == "offline",
                Note.updated_at >= day_start, Note.updated_at < day_end).scalar() or 0)

    return ok({
        "dates": [d.isoformat() for d in days],
        "series": [
            {"name": "新增资料", "data": new_notes},
            {"name": "发布成功", "data": pub_ok},
            {"name": "下架资料", "data": offlined},
            {"name": "发布失败", "data": pub_fail},
        ],
    })
