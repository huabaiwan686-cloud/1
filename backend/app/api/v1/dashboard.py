"""运营看板：/api/dashboard/stats（真实聚合）。"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

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
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    return ok({
        "notesTotal": db.query(func.count(Note.id)).scalar(),
        "notesByStatus": by_status,
        "todayPublishes": today_publishes or 0,
        "channelsActive": db.query(func.count(Channel.id)).filter(Channel.is_active.is_(True)).scalar(),
        "tgAccounts": db.query(func.count(TgAccount.id)).scalar(),
        "botTokens": db.query(func.count(BotToken.id)).scalar(),
        "quotaLeft": max(q.monthly_quota - q.monthly_used, 0) + max(q.extra_quota - q.extra_used, 0),
        "vipPlan": sub.plan if active else "starter",
        "vipActive": active,
    })
